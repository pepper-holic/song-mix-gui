import { useEffect, useMemo, useState } from "react";
import { api } from "./bridge";
import { BulkScanPanel } from "./BulkScanPanel";
import type { BulkApplyOutcome, BulkPreviewEntry, BusTreeNode, ScanSongEntry, SongDoc } from "./types";

type Props = {
  docs: SongDoc[];
  defaultSrcPath: string | null;
  onClose: () => void;
};

type BusMode = "all" | "none" | "custom";

function fileNameOf(path: string): string {
  return path.replace(/\\/g, "/").split("/").pop() ?? path;
}

const ACTION_LABEL: Record<string, string> = {
  "bus-subtree": "버스 전송",
  "chain-replace": "체인 교체",
  excluded: "제외됨",
  "no-match": "매칭 안 됨",
  "not-selected": "버스 미선택",
  "unknown-bus-label": "존재하지 않는 버스 라벨",
};

function summarize(plans: { action: string }[]): string {
  const counts = new Map<string, number>();
  for (const p of plans) counts.set(p.action, (counts.get(p.action) ?? 0) + 1);
  return [...counts.entries()]
    .map(([action, n]) => `${ACTION_LABEL[action] ?? action} ${n}`)
    .join(" · ");
}

/** label -> 모든 하위(자손) 라벨 목록. 상위 버스를 선택하면 서브트리 전체가 통째로
 * 전송되므로(엔진), 하위 버스를 굳이 별도로 선택 목록에 넣을 필요가 없다 —
 * 상위 선택 시 하위를 이 목록으로 자동 해제하고 "포함됨"으로만 표시한다. */
function buildDescendantsMap(tree: BusTreeNode[]): Map<string, string[]> {
  const childrenOf = new Map<string, string[]>();
  for (const node of tree) {
    if (node.parentLabel === null) continue;
    const list = childrenOf.get(node.parentLabel) ?? [];
    list.push(node.label);
    childrenOf.set(node.parentLabel, list);
  }
  const result = new Map<string, string[]>();
  const collect = (label: string): string[] => {
    const cached = result.get(label);
    if (cached) return cached;
    const direct = childrenOf.get(label) ?? [];
    const all = direct.flatMap((child) => [child, ...collect(child)]);
    result.set(label, all);
    return all;
  };
  for (const node of tree) collect(node.label);
  return result;
}

/** label -> 모든 상위(조상) 라벨 목록. 조상이 선택돼 있으면 이 버스는 이미
 * 서브트리에 포함된 것이므로 체크박스를 "포함됨"으로 표시하고 비활성화한다. */
function buildAncestorsMap(tree: BusTreeNode[]): Map<string, string[]> {
  const parentOf = new Map<string, string | null>();
  for (const node of tree) parentOf.set(node.label, node.parentLabel);
  const result = new Map<string, string[]>();
  for (const node of tree) {
    const chain: string[] = [];
    let cur = parentOf.get(node.label) ?? null;
    while (cur !== null) {
      chain.push(cur);
      cur = parentOf.get(cur) ?? null;
    }
    result.set(node.label, chain);
  }
  return result;
}

/** US-V3-001 GUI: 한 곡의 믹스 레시피(버스구조+트랙 체인)를 여러 곡에 일괄 적용.
 * 엔진(bulk_apply.py)을 그대로 재사용 — 계산은 파이썬 쪽, 여기는 입력 수집 + 결과 표시만. */
export function BulkApplyDialog({ docs, defaultSrcPath, onClose }: Props) {
  const [srcPath, setSrcPath] = useState(defaultSrcPath ?? docs[0]?.path ?? "");
  const [dstPaths, setDstPaths] = useState<string[]>([]);
  const [trackLabels, setTrackLabels] = useState<string[]>([]);
  const [excludeLabels, setExcludeLabels] = useState<Set<string>>(new Set());
  const [busMode, setBusMode] = useState<BusMode>("all");
  const [busTree, setBusTree] = useState<BusTreeNode[]>([]);
  const [customBus, setCustomBus] = useState<Set<string>>(new Set());
  const [allowNestedWarnings, setAllowNestedWarnings] = useState(false);
  const [previews, setPreviews] = useState<BulkPreviewEntry[] | null>(null);
  const [outcomes, setOutcomes] = useState<BulkApplyOutcome[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [scanDir, setScanDir] = useState("");
  const [scanEntries, setScanEntries] = useState<ScanSongEntry[] | null>(null);
  const [scanChecked, setScanChecked] = useState<Set<string>>(new Set());

  const descendantsOf = useMemo(() => buildDescendantsMap(busTree), [busTree]);
  const ancestorsOf = useMemo(() => buildAncestorsMap(busTree), [busTree]);

  // 헤드리스 E2E용 훅 — 네이티브 다중 파일 다이얼로그(pick_song_files_dialog)는
  // 자동화 스크립트로 조작 불가하므로, __openSong과 동일한 패턴으로 경로 직접 주입을 허용
  useEffect(() => {
    (window as unknown as { __bulkApplyAddDst?: (p: string) => void }).__bulkApplyAddDst =
      (p: string) => setDstPaths((prev) => (prev.includes(p) ? prev : [...prev, p]));
    return () => {
      delete (window as unknown as { __bulkApplyAddDst?: (p: string) => void }).__bulkApplyAddDst;
    };
  }, []);

  // 소스 곡이 바뀔 때마다 트랙 라벨/버스 루트를 즉시 조회 — 미리보기를 먼저 누르지
  // 않아도 제외 라벨 체크박스/버스 선택 목록을 바로 채운다.
  useEffect(() => {
    if (!srcPath) { setTrackLabels([]); setBusTree([]); return; }
    let cancelled = false;
    setExcludeLabels(new Set());
    setCustomBus(new Set());
    void api.describeSource(srcPath).then((res) => {
      if (cancelled) return;
      if (res.status === "ok") {
        setTrackLabels(res.trackLabels ?? []);
        setBusTree(res.busTree ?? []);
      }
    });
    return () => { cancelled = true; };
  }, [srcPath]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const includeBusLabels = (): string[] | null => {
    if (busMode === "all") return null;
    if (busMode === "none") return [];
    return Array.from(customBus);
  };

  const addDstFiles = async () => {
    const res = await api.pickSongFiles();
    if (res.status === "ok" && res.paths) {
      setDstPaths((prev) => [...prev, ...res.paths!.filter((p) => !prev.includes(p))]);
    }
  };

  const removeDst = (path: string) => {
    setDstPaths((prev) => prev.filter((p) => p !== path));
  };

  const runScan = async () => {
    const dirRes = await api.pickSongDirectory();
    if (dirRes.status !== "ok" || !dirRes.path) return;
    setErrorMsg("");
    setBusy(true);
    try {
      const res = await api.scanSongDirectory(dirRes.path);
      if (res.status === "ok") {
        setScanDir(dirRes.path);
        setScanEntries(res.entries ?? []);
        setScanChecked(new Set());
      } else {
        setErrorMsg(res.message ?? "폴더 스캔 실패");
      }
    } finally {
      setBusy(false);
    }
  };

  const toggleScanChecked = (path: string) => {
    setScanChecked((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path); else next.add(path);
      return next;
    });
  };

  const addSelectedFromScan = () => {
    setDstPaths((prev) => [
      ...prev,
      ...[...scanChecked].filter((p) => p !== srcPath && !prev.includes(p)),
    ]);
    setScanEntries(null);
    setScanChecked(new Set());
  };

  const runPreview = async () => {
    if (!srcPath || dstPaths.length === 0) {
      setErrorMsg("소스 곡과 대상 곡을 최소 1개씩 선택하세요.");
      return;
    }
    setErrorMsg("");
    setOutcomes(null);
    setBusy(true);
    try {
      const res = await api.previewBulkRecipe(
        srcPath, dstPaths, Array.from(excludeLabels), includeBusLabels());
      if (res.status === "ok") {
        setPreviews(res.previews ?? []);
      } else {
        setErrorMsg(res.message ?? "미리보기 실패");
      }
    } finally {
      setBusy(false);
    }
  };

  const runApply = async () => {
    if (!srcPath || dstPaths.length === 0) return;
    setErrorMsg("");
    setBusy(true);
    try {
      const res = await api.applyBulkRecipe(
        srcPath, dstPaths, Array.from(excludeLabels), includeBusLabels(), allowNestedWarnings);
      if (res.status === "ok") {
        setOutcomes(res.outcomes ?? []);
      } else {
        setErrorMsg(res.message ?? "적용 실패");
      }
    } finally {
      setBusy(false);
    }
  };

  const toggleExcludeLabel = (label: string) => {
    setExcludeLabels((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label); else next.add(label);
      return next;
    });
  };

  const toggleCustomBus = (label: string) => {
    setCustomBus((prev) => {
      const next = new Set(prev);
      if (next.has(label)) {
        next.delete(label);
      } else {
        // 상위 버스를 선택하면 서브트리 전체가 통째로 전송되므로, 그 안의 하위
        // 버스가 개별적으로 이미 선택돼 있었다면 중복/모순(엔진이 조상-자손 동시
        // 지정을 거부함)이 되지 않도록 함께 해제한다 — 렌더링에서는 ancestorsOf로
        // "포함됨" 표시만 하고 실제 선택 목록에는 상위 하나만 남긴다.
        next.add(label);
        for (const descendant of descendantsOf.get(label) ?? []) next.delete(descendant);
      }
      return next;
    });
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
        <h3>믹스 레시피 일괄 적용</h3>
        <p className="bulk-hint">
          소스 곡의 채널별 플러그인 체인 + 버스/병렬 구조를, 라벨이 정확히 일치하는 대상 곡들에
          반영합니다. 라벨 표기가 곡마다 다를 수 있으니(예: "kick" vs "1 - kick") 먼저
          미리보기로 매칭 결과를 확인하세요.
        </p>

        <label className="bulk-field">
          소스 곡
          <select value={srcPath} onChange={(e) => setSrcPath(e.target.value)}>
            {docs.length === 0 && <option value="">(열린 곡 없음 — 먼저 song을 여세요)</option>}
            {docs.map((d) => (
              <option key={d.id} value={d.path}>{d.fileName}</option>
            ))}
          </select>
        </label>

        <div className="bulk-field">
          <div className="bulk-dst-header">
            대상 곡 ({dstPaths.length}개)
            <span>
              <button type="button" onClick={() => void addDstFiles()}>파일 추가...</button>
              <button type="button" onClick={() => void runScan()}>폴더에서 스캔...</button>
            </span>
          </div>
          <ul className="bulk-dst-list">
            {dstPaths.map((p) => (
              <li key={p}>
                {fileNameOf(p)}
                <button type="button" className="close-btn" onClick={() => removeDst(p)}>×</button>
              </li>
            ))}
            {dstPaths.length === 0 && <li className="bulk-empty">없음</li>}
          </ul>
          {scanEntries && (
            <BulkScanPanel dirPath={scanDir} entries={scanEntries} checked={scanChecked}
                          onToggle={toggleScanChecked} onAddSelected={addSelectedFromScan}
                          onClose={() => setScanEntries(null)} />
          )}
        </div>

        <div className="bulk-field">
          제외할 트랙(정확 일치 — 소스에 있는 트랙 라벨 중에서 고르기)
          {trackLabels.length === 0 ? (
            <p className="bulk-hint">소스 곡을 선택하면 트랙 목록이 여기 나타납니다.</p>
          ) : (
            <div className="bulk-bus-checks bulk-track-checks">
              {trackLabels.map((label) => (
                <label key={label}>
                  <input type="checkbox" checked={excludeLabels.has(label)}
                        onChange={() => toggleExcludeLabel(label)} />
                  {label}
                </label>
              ))}
            </div>
          )}
        </div>

        <div className="bulk-field">
          버스/병렬 구조
          <div className="bulk-bus-modes">
            <label><input type="radio" checked={busMode === "all"}
                          onChange={() => setBusMode("all")} /> 전체</label>
            <label><input type="radio" checked={busMode === "none"}
                          onChange={() => setBusMode("none")} /> 건드리지 않음(트랙만)</label>
            <label><input type="radio" checked={busMode === "custom"}
                          onChange={() => setBusMode("custom")} /> 직접 선택</label>
          </div>
          <p className="bulk-hint">
            "전체"는 최상위 버스만 옮기고 그 아래 중첩된 버스는 함께 딸려가 미리보기에
            별도 항목으로 나오지 않습니다(예: MIXOUT 하나만 [버스 전송]으로 보여도
            그 아래 서브버스가 전부 포함됨). 특정 중첩 버스만 따로 옮기려면 "직접
            선택"에서 고르세요.
          </p>
          {busMode === "custom" && (
            busTree.length === 0 ? (
              <p className="bulk-hint">소스 곡에서 버스를 찾지 못했습니다.</p>
            ) : (
              <>
                <p className="bulk-hint">
                  상위 버스를 선택하면 하위 버스도 서브트리째 함께 전송되므로 자동으로
                  "포함됨" 처리되어 개별 해제할 수 없습니다. 하위 버스만 따로 옮기려면
                  상위는 선택하지 말고 해당 하위만 고르세요.
                </p>
                <div className="bulk-bus-checks bulk-bus-tree">
                  {busTree.map((node) => {
                    const impliedBy = (ancestorsOf.get(node.label) ?? [])
                      .find((ancestor) => customBus.has(ancestor));
                    const checked = customBus.has(node.label) || impliedBy !== undefined;
                    return (
                      <label key={node.label} style={{ paddingLeft: node.depth * 14 }}>
                        <input type="checkbox" checked={checked} disabled={impliedBy !== undefined}
                              onChange={() => toggleCustomBus(node.label)} />
                        {node.depth > 0 ? `└ ${node.label}` : node.label}
                        {impliedBy !== undefined && (
                          <span className="bulk-bus-implied">({impliedBy}에 포함됨)</span>
                        )}
                      </label>
                    );
                  })}
                </div>
              </>
            )
          )}
        </div>

        <label className="preserve-sends-toggle">
          <input type="checkbox" checked={allowNestedWarnings}
                onChange={(e) => setAllowNestedWarnings(e.target.checked)} />
          제외 라벨이 버스 서브트리 내부에 중첩돼 있어도 강행(기본은 안전하게 거부)
        </label>

        {errorMsg && <p className="bulk-error">{errorMsg}</p>}

        {previews && (
          <div className="bulk-results">
            {previews.map((p) => (
              <div key={p.path} className="bulk-result-block">
                <strong>{fileNameOf(p.path)}</strong>
                {p.status === "error" ? (
                  <p className="bulk-error">실패: {p.message}</p>
                ) : (
                  <>
                    <p className="bulk-summary">{summarize(p.plans ?? [])}</p>
                    <ul className="bulk-plan-list">
                      {(p.plans ?? []).map((plan) => (
                        <li key={plan.label} className={`bulk-action-${plan.action}`}>
                          [{ACTION_LABEL[plan.action] ?? plan.action}] {plan.label}
                        </li>
                      ))}
                    </ul>
                    {(p.warnings ?? []).map((w) => (
                      <p key={w} className="bulk-warning">경고: {w}</p>
                    ))}
                  </>
                )}
              </div>
            ))}
          </div>
        )}

        {outcomes && (
          <div className="bulk-results">
            {outcomes.map((o) => (
              <div key={o.path} className="bulk-result-block">
                <strong>{fileNameOf(o.path)}</strong>
                {o.status === "error" ? (
                  <p className="bulk-error">실패(파일 미변경): {o.message}</p>
                ) : (
                  <>
                    <p className="bulk-ok">적용 완료 — 백업: {o.savedBackup}</p>
                    {(o.warnings ?? []).map((w) => (
                      <p key={w} className="bulk-warning">경고: {w}</p>
                    ))}
                  </>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="modal-actions">
          <button type="button" disabled={busy} onClick={() => void runPreview()}>
            미리보기
          </button>
          <button type="button" disabled={busy || !previews} onClick={() => void runApply()}>
            적용
          </button>
          <button type="button" onClick={onClose}>닫기</button>
        </div>
      </div>
    </div>
  );
}
