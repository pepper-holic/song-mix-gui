import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./bridge";
import { BulkApplyDialog } from "./BulkApplyDialog";
import { ComparePanel } from "./ComparePanel";
import { KIND_COLORS } from "./ChannelNode";
import { IconClock, IconColumns, IconFolderOpen, IconKeyboard, IconLayers,
        IconUndo } from "./Icons";
import { SongPane } from "./SongPane";
import type { ChannelInfo, CompareRow, DragPayload, PrewarmStatus, SongDoc, SongModel,
             TransferResponse } from "./types";

interface ConflictState {
  payload: DragPayload;
  dstDoc: SongDoc;
  labels: string[];
}

interface CompareBaseline {
  doc: SongDoc;
  channel: ChannelInfo;
}

interface CompareResultState {
  leftLabel: string;
  rightLabel: string;
  rows: CompareRow[];
}

interface ChainPasteConfirm {
  payload: DragPayload;
  dstDoc: SongDoc;
  dstChannel: ChannelInfo;
}

interface TrackTransferConfirm {
  payload: DragPayload;
  dstDoc: SongDoc;
}

const LEGEND: { kind: string; label: string }[] = [
  { kind: "track", label: "트랙" },
  { kind: "group", label: "버스" },
  { kind: "effect", label: "FX" },
  { kind: "output", label: "아웃" },
];

function fileNameOf(path: string): string {
  return path.replace(/\\/g, "/").split("/").pop() ?? path;
}

/** 열려있는 문서 목록에서 전송 페이로드의 소스 경로를 찾는다(문서가 닫혔으면 페이로드 값으로 대체). */
function resolveSrcPath(docs: SongDoc[], payload: DragPayload): string | undefined {
  return docs.find((d) => d.id === payload.docId)?.path ?? payload.srcPath;
}

let docSeq = 0;

export default function App() {
  const [docs, setDocs] = useState<SongDoc[]>([]);
  const [leftDocId, setLeftDocId] = useState<string | null>(null);
  const [rightDocId, setRightDocId] = useState<string | null>(null);
  const [isSplit, setIsSplit] = useState(false);
  const [conflict, setConflict] = useState<ConflictState | null>(null);
  const [statusMsg, setStatusMsg] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const [focusedPaneId, setFocusedPaneId] = useState<"left" | "right">("left");
  const [recentFiles, setRecentFiles] = useState<string[]>([]);
  const [showRecentMenu, setShowRecentMenu] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [compareBaseline, setCompareBaseline] = useState<CompareBaseline | null>(null);
  const [compareResult, setCompareResult] = useState<CompareResultState | null>(null);
  const [prewarmStatus, setPrewarmStatus] = useState<PrewarmStatus | null>(null);
  const [chainPasteConfirm, setChainPasteConfirm] = useState<ChainPasteConfirm | null>(null);
  const [trackTransferConfirm, setTrackTransferConfirm] = useState<TrackTransferConfirm | null>(null);
  const [includeEvents, setIncludeEvents] = useState(false);
  const [preserveSends, setPreserveSends] = useState(false);
  const [showBulkApply, setShowBulkApply] = useState(false);
  const clipboard = useRef<DragPayload | null>(null);
  const autoOpened = useRef(false);

  const leftDoc = docs.find((d) => d.id === leftDocId) ?? null;
  const rightDoc = docs.find((d) => d.id === rightDocId) ?? null;

  const refreshRecent = useCallback(async () => {
    try {
      const list = await api.getRecent();
      setRecentFiles(list);
    } catch {
      // Qt 브리지가 없는 dev 브라우저 모드 — 조용히 무시
    }
  }, []);

  const addDoc = useCallback((path: string, model: SongModel) => {
    const existing = docs.find((d) => d.path === path);
    const id = existing?.id ?? `doc${++docSeq}`;
    if (existing) {
      setDocs((prev) => prev.map((d) => (d.path === path ? { ...d, model } : d)));
    } else {
      const fileName = fileNameOf(path);
      setDocs((prev) => [...prev, { id, path, fileName, model }]);
    }
    if (!leftDocId || !isSplit) setLeftDocId(id);
    else setRightDocId(id);
  }, [docs, leftDocId, isSplit]);

  const handleOpen = useCallback(async () => {
    setStatusMsg("파일 선택 중…");
    setIsBusy(true);
    try {
      const res = await api.openSongDialog();
      if (res.status === "ok" && res.path && res.model) {
        addDoc(res.path, res.model);
        setStatusMsg(`열림: ${res.path}`);
        void refreshRecent();
      } else if (res.status === "cancelled") {
        setStatusMsg("");
      } else {
        setStatusMsg(`오류: ${res.message ?? "알 수 없음"}`);
      }
    } catch (e) {
      setStatusMsg(`오류: ${(e as Error).message}`);
    } finally {
      setIsBusy(false);
    }
  }, [addDoc, refreshRecent]);

  const openFromRecent = useCallback(async (path: string) => {
    setShowRecentMenu(false);
    setStatusMsg(`여는 중: ${path}…`);
    setIsBusy(true);
    try {
      const res = await api.openSong(path);
      if (res.status === "ok" && res.path && res.model) {
        addDoc(res.path, res.model);
        setStatusMsg(`열림: ${res.path}`);
        void refreshRecent();
      } else {
        setStatusMsg(`오류: ${res.message ?? "알 수 없음"}`);
      }
    } catch (e) {
      setStatusMsg(`오류: ${(e as Error).message}`);
    } finally {
      setIsBusy(false);
    }
  }, [addDoc, refreshRecent]);

  const refreshDoc = useCallback(async (path: string) => {
    const res = await api.openSong(path);
    if (res.status === "ok" && res.model) {
      setDocs((prev) => prev.map((d) => (d.path === path ? { ...d, model: res.model! } : d)));
    }
  }, []);

  const runTransfer = useCallback(async (payload: DragPayload, dstDoc: SongDoc,
                                         confirmed: boolean) => {
    const srcPath = resolveSrcPath(docs, payload);
    if (!srcPath) { setStatusMsg("소스 문서를 찾을 수 없음"); return; }
    if (srcPath === dstDoc.path) { setStatusMsg("같은 문서로는 전송할 수 없습니다"); return; }
    setStatusMsg(`전송 중: ${payload.label} → ${dstDoc.fileName}…`);
    setIsBusy(true);
    try {
      const res: TransferResponse =
        await api.transferSubtree(srcPath, payload.rootUid, dstDoc.path, confirmed, preserveSends);
      if (res.status === "conflict") {
        setConflict({ payload, dstDoc, labels: (res.conflicts ?? []).map((c) => c.label) });
        setStatusMsg("");
      } else if (res.status === "ok") {
        const dropped = res.droppedSends?.length
          ? ` (제거된 외부 send: ${res.droppedSends.join(", ")})` : "";
        setStatusMsg(`전송 완료 — 백업: ${res.savedBackup ?? "-"}${dropped}`);
        await refreshDoc(dstDoc.path);
      } else {
        setStatusMsg(`전송 실패: ${res.message ?? "알 수 없음"}`);
      }
    } finally {
      setIsBusy(false);
    }
  }, [docs, refreshDoc, preserveSends]);

  // S4b/S4d 트랙 전송(AC-6): 트랙 채널은 전송 전 "이벤트 포함" 여부를 묻는 확인 다이얼로그를 거친다.
  const runTrackTransfer = useCallback(async (payload: DragPayload, dstDoc: SongDoc,
                                              withEvents: boolean) => {
    const srcPath = resolveSrcPath(docs, payload);
    if (!srcPath) { setStatusMsg("소스 문서를 찾을 수 없음"); return; }
    if (srcPath === dstDoc.path) { setStatusMsg("같은 문서로는 전송할 수 없습니다"); return; }
    setStatusMsg(`트랙 전송 중: ${payload.label} → ${dstDoc.fileName}…`);
    setIsBusy(true);
    try {
      const res = await api.transferTrack(srcPath, payload.rootUid, dstDoc.path, withEvents);
      if (res.status === "ok") {
        const warn = res.message ? ` — ${res.message}` : "";
        setStatusMsg(`트랙 전송 완료 — 백업: ${res.savedBackup ?? "-"}${warn}`);
        await refreshDoc(dstDoc.path);
      } else {
        setStatusMsg(`트랙 전송 실패: ${res.message ?? "알 수 없음"}`);
      }
    } catch (e) {
      setStatusMsg(`트랙 전송 실패: ${(e as Error).message}`);
    } finally {
      setIsBusy(false);
    }
  }, [docs, refreshDoc]);

  const handleTransferDrop = useCallback((payload: DragPayload, dstDoc: SongDoc) => {
    if (payload.mode === "track") {
      setIncludeEvents(false);
      setTrackTransferConfirm({ payload, dstDoc });
      return;
    }
    void runTransfer(payload, dstDoc, false);
  }, [runTransfer]);

  const handleCopy = useCallback((doc: SongDoc, channel: ChannelInfo) => {
    if (channel.kind === "track") {
      clipboard.current = {
        docId: doc.id, srcPath: doc.path, rootUid: channel.uid,
        label: channel.label, mode: "track",
      };
      setStatusMsg(`복사됨(트랙): ${channel.label} — 대상 패널의 빈 곳을 우클릭(또는 Ctrl+V)하면 붙여넣기`);
      return;
    }
    if (channel.kind !== "group" && channel.kind !== "effect") {
      setStatusMsg(`${channel.label}: 버스/FX/트랙 채널만 전송할 수 있습니다`);
      return;
    }
    clipboard.current = {
      docId: doc.id, srcPath: doc.path, rootUid: channel.uid,
      label: channel.label, mode: "subtree",
    };
    setStatusMsg(`복사됨: ${channel.label} — 대상 패널의 빈 곳을 우클릭(또는 Ctrl+V)하면 붙여넣기`);
  }, []);

  const handlePaste = useCallback((dstDoc: SongDoc) => {
    if (!clipboard.current) {
      setStatusMsg("붙여넣을 항목 없음 — 먼저 소스 패널에서 버스를 우클릭해 복사하세요");
      return;
    }
    if (clipboard.current.mode === "track") {
      setIncludeEvents(false);
      setTrackTransferConfirm({ payload: clipboard.current, dstDoc });
      return;
    }
    void runTransfer(clipboard.current, dstDoc, false);
  }, [runTransfer]);

  // S1 체인 이식(AC-7): Ctrl+우클릭="체인 복사"(트랙 포함), 평범한 우클릭 시 클립보드가
  // 체인 모드면 그 노드를 대상으로 "체인 붙여넣기(교체)" 확인 다이얼로그. 그 외엔 기존 복사(handleCopy).
  const handleChainCopy = useCallback((doc: SongDoc, channel: ChannelInfo) => {
    clipboard.current = {
      docId: doc.id, srcPath: doc.path, rootUid: channel.uid,
      label: channel.label, mode: "chain",
    };
    setStatusMsg(`체인 복사됨: ${channel.label} — 대상 채널을 우클릭하면 체인 붙여넣기(교체)`);
  }, []);

  const handleNodeRightClick = useCallback((doc: SongDoc, channel: ChannelInfo) => {
    if (clipboard.current?.mode === "chain") {
      setChainPasteConfirm({ payload: clipboard.current, dstDoc: doc, dstChannel: channel });
    } else {
      handleCopy(doc, channel);
    }
  }, [handleCopy]);

  const runChainReplace = useCallback(async (payload: DragPayload, dstDoc: SongDoc,
                                              dstChannel: ChannelInfo) => {
    const srcPath = resolveSrcPath(docs, payload);
    if (!srcPath) { setStatusMsg("소스 문서를 찾을 수 없음"); return; }
    setStatusMsg(`체인 이식 중: ${payload.label} → ${dstChannel.label}…`);
    setIsBusy(true);
    try {
      const res = await api.replaceChain(srcPath, payload.rootUid, dstDoc.path, dstChannel.uid);
      if (res.status === "ok") {
        setStatusMsg(`체인 이식 완료 — 백업: ${res.savedBackup ?? "-"}`);
        await refreshDoc(dstDoc.path);
      } else {
        setStatusMsg(`체인 이식 실패: ${res.message ?? "알 수 없음"}`);
      }
    } catch (e) {
      setStatusMsg(`체인 이식 실패: ${(e as Error).message}`);
    } finally {
      setIsBusy(false);
    }
  }, [docs, refreshDoc]);

  const handleUndo = useCallback(async (doc: SongDoc) => {
    setStatusMsg(`실행 취소 중: ${doc.fileName}…`);
    setIsBusy(true);
    try {
      const res = await api.undoLast(doc.path);
      if (res.status === "ok" && res.model) {
        setDocs((prev) => prev.map((d) => (d.path === doc.path ? { ...d, model: res.model! } : d)));
        setStatusMsg(res.message ?? `복원됨: ${doc.fileName}`);
      } else {
        setStatusMsg(`실행 취소 실패: ${res.message ?? "알 수 없음"}`);
      }
    } catch (e) {
      setStatusMsg(`실행 취소 실패: ${(e as Error).message}`);
    } finally {
      setIsBusy(false);
    }
  }, []);

  const handleUndoToolbar = useCallback(() => {
    const target = focusedPaneId === "right" && rightDoc ? rightDoc : leftDoc;
    if (!target) { setStatusMsg("실행 취소할 문서가 없습니다"); return; }
    void handleUndo(target);
  }, [focusedPaneId, leftDoc, rightDoc, handleUndo]);

  // U4 체인 비교(AC-4): 우클릭(Shift)=A로 지정, 우클릭(Alt)=A와 비교. diff 계산은 Python(compare.py) 재사용.
  const handleSetCompareBaseline = useCallback((doc: SongDoc, channel: ChannelInfo) => {
    setCompareBaseline({ doc, channel });
    setStatusMsg(`비교 기준(A)으로 지정: ${channel.label} — 다른 채널을 Alt+우클릭하면 비교`);
  }, []);

  const handleCompareWith = useCallback(async (doc: SongDoc, channel: ChannelInfo) => {
    if (!compareBaseline) {
      setStatusMsg("먼저 비교 기준(A)을 Shift+우클릭으로 지정하세요");
      return;
    }
    setStatusMsg(`비교 중: ${compareBaseline.channel.label} ↔ ${channel.label}…`);
    setIsBusy(true);
    try {
      const res = await api.compareChannels(
        compareBaseline.doc.path, compareBaseline.channel.uid, doc.path, channel.uid);
      if (res.status === "ok") {
        setCompareResult({
          leftLabel: res.leftLabel ?? compareBaseline.channel.label,
          rightLabel: res.rightLabel ?? channel.label,
          rows: res.rows ?? [],
        });
        setStatusMsg("");
      } else {
        setStatusMsg(`비교 실패: ${res.message ?? "알 수 없음"}`);
      }
    } catch (e) {
      setStatusMsg(`비교 실패: ${(e as Error).message}`);
    } finally {
      setIsBusy(false);
    }
  }, [compareBaseline]);

  useEffect(() => {
    const testPath = new URLSearchParams(window.location.search).get("open");
    if (testPath && !autoOpened.current) {
      autoOpened.current = true;
      void api.openSong(testPath).then((res) => {
        if (res.status === "ok" && res.path && res.model) addDoc(res.path, res.model);
        void refreshRecent();
      });
    }
    void refreshRecent();
    // 헤드리스 E2E용 훅 (다이얼로그 없이 경로로 열기)
    (window as unknown as { __openSong?: (p: string) => Promise<void> }).__openSong =
      async (p: string) => {
        const res = await api.openSong(p);
        if (res.status === "ok" && res.path && res.model) addDoc(res.path, res.model);
        else throw new Error(res.message ?? "open failed");
      };
  }, [addDoc, refreshRecent]);

  // U5c 단축키 도움말(AC-10): 입력창에 포커스가 없을 때 '?' 토글
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const isTyping = !!target &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
      if (e.key === "?" && !isTyping) {
        e.preventDefault();
        setShowShortcuts((s) => !s);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // P3 프리웜 진행률 폴링(AC-5): 그룹 단위 진행률을 폴링해 상태바에 노출, 완료 시 자동 소거
  useEffect(() => {
    if (docs.length === 0) { setPrewarmStatus(null); return; }
    let cancelled = false;
    const poll = async () => {
      try {
        const s = await api.prewarmStatus();
        if (!cancelled) setPrewarmStatus(s.total > 0 && s.done < s.total ? s : null);
      } catch {
        // Qt 브리지가 없는 dev 브라우저 모드 — 조용히 무시
      }
    };
    void poll();
    const id = setInterval(poll, 800);
    return () => { cancelled = true; clearInterval(id); };
  }, [docs.length]);

  // 창 제목에 현재 좌측 문서를 반영(상용 데스크톱 앱 관례)
  useEffect(() => {
    api.setWindowTitle(leftDoc
      ? `${leftDoc.fileName} — Song Mix GUI`
      : "Song Mix GUI — Studio One .song 믹스 분석/전송");
  }, [leftDoc]);

  // 상태바 색상: 메시지 문자열에서 성공/실패를 유추(별도 상태 없이 파생 — 기존 setStatusMsg
  // 호출부를 전부 건드리지 않고도 실패 메시지를 눈에 띄게 만든다)
  const statusKind = statusMsg.includes("실패") || statusMsg.includes("오류") ? "error"
    : statusMsg.includes("완료") || statusMsg.includes("복원됨") || statusMsg.includes("복사됨")
      || statusMsg.includes("열림") ? "success" : "info";

  // Esc로 열려있는 모달/드롭다운을 전부 닫음(입력창 타이핑 중에는 무시)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
      setShowRecentMenu(false);
      setShowShortcuts(false);
      setCompareResult(null);
      setChainPasteConfirm(null);
      setTrackTransferConfirm(null);
      setConflict(null);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // 최근 파일 드롭다운: 바깥을 클릭하면 닫힘
  useEffect(() => {
    if (!showRecentMenu) return;
    const handler = (e: MouseEvent) => {
      if (!(e.target as HTMLElement)?.closest(".recent-dropdown")) setShowRecentMenu(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showRecentMenu]);

  return (
    <div className="app">
      <header className="toolbar">
        <div className="toolbar-group">
          <button type="button" onClick={() => void handleOpen()}>
            <span className="icon"><IconFolderOpen /></span>song 열기…
          </button>
          <div className="recent-dropdown">
            <button type="button" onClick={() => setShowRecentMenu((s) => !s)}>
              <span className="icon"><IconClock /></span>최근 파일
            </button>
            {showRecentMenu && (
              <ul className="recent-menu">
                {recentFiles.length === 0 && <li className="recent-empty">없음</li>}
                {recentFiles.map((p) => (
                  <li key={p}>
                    <button type="button" onClick={() => void openFromRecent(p)}>
                      {fileNameOf(p)}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
        <div className="toolbar-divider" />
        <div className="toolbar-group">
          <button type="button" onClick={() => setIsSplit((s) => !s)}>
            <span className="icon"><IconColumns /></span>
            {isSplit ? "단일 뷰" : "좌우 스플릿"}
          </button>
          <button type="button" onClick={handleUndoToolbar} title="Ctrl+Z">
            <span className="icon"><IconUndo /></span>실행 취소
          </button>
          <button type="button" onClick={() => setShowShortcuts(true)} title="?">
            <span className="icon"><IconKeyboard /></span>단축키
          </button>
        </div>
        <div className="toolbar-divider" />
        <div className="toolbar-group">
          <button type="button" onClick={() => setShowBulkApply(true)}>
            <span className="icon"><IconLayers /></span>레시피 일괄 적용…
          </button>
          <label className="preserve-sends-toggle" title="서브트리 밖 send 대상과 동명 채널이 대상에 있으면 연결 유지(옵션 off 시 기존대로 제거+기록)">
            <input
              type="checkbox"
              checked={preserveSends}
              onChange={(e) => setPreserveSends(e.target.checked)}
            />
            외부 send 보존
          </label>
        </div>
        <div className="toolbar-divider" />
        <div className="legend" title="채널 종류 범례">
          {LEGEND.map((l) => (
            <span key={l.kind} className="legend-item">
              <span className="legend-swatch" style={{ background: KIND_COLORS[l.kind] }} />
              {l.label}
            </span>
          ))}
        </div>
        <nav className="tabs">
          {docs.map((d) => (
            <button
              type="button"
              key={d.id}
              className={d.id === leftDocId ? "tab active" : "tab"}
              onClick={() => setLeftDocId(d.id)}
              onContextMenu={(e) => { e.preventDefault(); setRightDocId(d.id); setIsSplit(true); }}
              title="클릭: 좌측에 표시 / 우클릭: 우측에 표시"
            >
              {d.fileName}
            </button>
          ))}
        </nav>
      </header>
      <main className={isSplit ? "panes split" : "panes"}>
        {leftDoc ? (
          <SongPane
            doc={leftDoc} paneId="left"
            onTransferDrop={handleTransferDrop}
            onCopyRequest={handleNodeRightClick}
            onChainCopyRequest={handleChainCopy}
            onPasteRequest={handlePaste}
            onUndoRequest={handleUndo}
            onSetCompareBaseline={handleSetCompareBaseline}
            onCompareWith={(doc, channel) => void handleCompareWith(doc, channel)}
            onFocusPane={() => setFocusedPaneId("left")}
          />
        ) : (
          <div className="empty-pane">
            <div className="empty-pane-content">
              <span className="empty-pane-icon"><IconFolderOpen /></span>
              <p className="empty-pane-title">열려 있는 song 파일이 없습니다</p>
              <button type="button" className="empty-cta" onClick={() => void handleOpen()}>
                <span className="icon"><IconFolderOpen /></span>song 열기…
              </button>
              {recentFiles.length > 0 && (
                <ul className="recent-list">
                  {recentFiles.map((p) => (
                    <li key={p}>
                      <button type="button" onClick={() => void openFromRecent(p)}>
                        {fileNameOf(p)}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
        {isSplit && (rightDoc ? (
          <SongPane
            doc={rightDoc} paneId="right"
            onTransferDrop={handleTransferDrop}
            onCopyRequest={handleNodeRightClick}
            onChainCopyRequest={handleChainCopy}
            onPasteRequest={handlePaste}
            onUndoRequest={handleUndo}
            onSetCompareBaseline={handleSetCompareBaseline}
            onCompareWith={(doc, channel) => void handleCompareWith(doc, channel)}
            onFocusPane={() => setFocusedPaneId("right")}
          />
        ) : (
          <div className="empty-pane">
            <div className="empty-pane-content">
              <span className="empty-pane-icon"><IconColumns /></span>
              <p className="empty-pane-title">탭을 우클릭하면 이 패널에 표시됩니다</p>
            </div>
          </div>
        ))}
      </main>
      <footer className={`statusbar status-${statusKind}`}>
        {isBusy && <span className="spinner" aria-label="처리 중" />}
        {statusMsg}
        {prewarmStatus && (
          <span className="prewarm-indicator">
            프리웜 {prewarmStatus.done}/{prewarmStatus.total}
          </span>
        )}
      </footer>
      {showShortcuts && (
        <div className="modal-backdrop" onClick={() => setShowShortcuts(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>단축키</h3>
            <ul className="shortcut-list">
              <li><kbd>Ctrl</kbd>+<kbd>C</kbd> 복사 (버스/FX 채널 우클릭 또는 선택 후)</li>
              <li><kbd>Ctrl</kbd>+<kbd>V</kbd> 붙여넣기 (대상 패널)</li>
              <li><kbd>Ctrl</kbd>+<kbd>Z</kbd> 실행 취소</li>
              <li>드래그 앤 드롭으로 채널 전송</li>
              <li><kbd>Shift</kbd>+우클릭: 비교 기준(A) 지정</li>
              <li><kbd>Alt</kbd>+우클릭: 지정된 기준과 비교</li>
              <li><kbd>Ctrl</kbd>+우클릭: 체인 복사 (트랙 포함) → 대상 채널 우클릭 시 교체</li>
              <li><kbd>?</kbd> 이 도움말 열기/닫기</li>
            </ul>
            <div className="modal-actions">
              <button type="button" onClick={() => setShowShortcuts(false)}>닫기</button>
            </div>
          </div>
        </div>
      )}
      {compareResult && (
        <div className="modal-backdrop" onClick={() => setCompareResult(null)}>
          <div onClick={(e) => e.stopPropagation()}>
            <ComparePanel
              leftLabel={compareResult.leftLabel}
              rightLabel={compareResult.rightLabel}
              rows={compareResult.rows}
              onClose={() => setCompareResult(null)}
            />
          </div>
        </div>
      )}
      {chainPasteConfirm && (
        <div className="modal-backdrop" onClick={() => setChainPasteConfirm(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>체인 붙여넣기(교체)</h3>
            <p>
              <strong>{chainPasteConfirm.dstChannel.label}</strong>의 인서트 체인을
              <strong> {chainPasteConfirm.payload.label}</strong>의 체인으로 교체합니다.
            </p>
            <p>기존 체인/세팅은 사라집니다 (실행 취소로 복원 가능).</p>
            <div className="modal-actions">
              <button
                type="button"
                onClick={() => {
                  const c = chainPasteConfirm;
                  setChainPasteConfirm(null);
                  // 체인 클립보드 소모 — 안 그러면 이후의 평범한 우클릭이 계속
                  // "체인 붙여넣기"로 오인식되어 서브트리 복사가 막힌다
                  clipboard.current = null;
                  void runChainReplace(c.payload, c.dstDoc, c.dstChannel);
                }}
              >
                교체
              </button>
              <button type="button" onClick={() => setChainPasteConfirm(null)}>취소</button>
            </div>
          </div>
        </div>
      )}
      {trackTransferConfirm && (
        <div className="modal-backdrop" onClick={() => setTrackTransferConfirm(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>트랙 채널 전송</h3>
            <p>
              <strong>{trackTransferConfirm.payload.label}</strong>을(를)
              <strong> {trackTransferConfirm.dstDoc.fileName}</strong>(으)로 전송합니다.
            </p>
            <label className="preserve-sends-toggle">
              <input
                type="checkbox"
                checked={includeEvents}
                onChange={(e) => setIncludeEvents(e.target.checked)}
              />
              이벤트 포함(오디오 클립) — 미디어 경로가 대상 폴더 밖이면 경고 표시
            </label>
            <div className="modal-actions">
              <button
                type="button"
                onClick={() => {
                  const c = trackTransferConfirm;
                  setTrackTransferConfirm(null);
                  // 이 다이얼로그는 클립보드 붙여넣기(handlePaste)뿐 아니라 드래그앤드롭
                  // (handleTransferDrop, clipboard와 무관)으로도 열릴 수 있다 — 클립보드가
                  // 실제로 이 payload를 보관 중일 때만 소모해야, 무관한 드롭 전송이
                  // 사용자가 이미 복사해둔 다른 항목을 조용히 지우지 않는다
                  if (clipboard.current === c.payload) clipboard.current = null;
                  void runTrackTransfer(c.payload, c.dstDoc, includeEvents);
                }}
              >
                전송
              </button>
              <button type="button" onClick={() => setTrackTransferConfirm(null)}>취소</button>
            </div>
          </div>
        </div>
      )}
      {showBulkApply && (
        <BulkApplyDialog
          docs={docs}
          defaultSrcPath={leftDoc?.path ?? null}
          onClose={() => setShowBulkApply(false)}
        />
      )}
      {conflict && (
        <div className="modal-backdrop" onClick={() => setConflict(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>이름 충돌</h3>
            <p>
              대상에 같은 이름의 채널/버스가 있습니다:
              <strong> {conflict.labels.join(", ")}</strong>
            </p>
            <p>덮어쓰면 대상의 인서트 체인·세팅·라우팅이 교체됩니다.</p>
            <div className="modal-actions">
              <button
                type="button"
                onClick={() => {
                  const c = conflict;
                  setConflict(null);
                  void runTransfer(c.payload, c.dstDoc, true);
                }}
              >
                덮어쓰기
              </button>
              <button type="button" onClick={() => setConflict(null)}>취소</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
