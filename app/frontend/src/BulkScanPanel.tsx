import type { ScanSongEntry } from "./types";

type Props = {
  dirPath: string;
  entries: ScanSongEntry[];
  checked: Set<string>;
  onToggle: (path: string) => void;
  onAddSelected: () => void;
  onClose: () => void;
};

function fileNameOf(path: string): string {
  return path.replace(/\\/g, "/").split("/").pop() ?? path;
}

/** US-V3-001 GUI 보강: 폴더 하위 .song 파일을 스캔해 파일별 트랙/버스 현황을
 * 보여주고 대상 곡으로 선택 추가할 수 있게 하는 프레젠테이셔널 패널.
 * 데이터 조회(scan)와 dstPaths 반영은 BulkApplyDialog가 소유한다. */
export function BulkScanPanel({ dirPath, entries, checked, onToggle, onAddSelected, onClose }: Props) {
  return (
    <div className="bulk-scan-panel">
      <div className="bulk-scan-header">
        <span>{dirPath} — {entries.length}개 발견</span>
        <div className="bulk-scan-actions">
          <button type="button" disabled={checked.size === 0} onClick={onAddSelected}>
            선택 추가 ({checked.size})
          </button>
          <button type="button" onClick={onClose}>닫기</button>
        </div>
      </div>
      <p className="bulk-hint">History 폴더의 자동저장/스냅샷은 제외하고 원본 곡만 표시합니다.</p>
      <ul className="bulk-scan-list">
        {entries.length === 0 && (
          <li className="bulk-empty">이 폴더 하위에서 .song 파일을 찾지 못했습니다.</li>
        )}
        {entries.map((entry) => (
          <li key={entry.path}>
            <label>
              <input type="checkbox" disabled={entry.status === "error"}
                    checked={checked.has(entry.path)}
                    onChange={() => onToggle(entry.path)} />
              {fileNameOf(entry.path)}
            </label>
            {entry.status === "ok" ? (
              <span className="bulk-scan-summary">
                트랙 {entry.trackLabels?.length ?? 0}개 · 버스 {entry.busCount ?? 0}개
              </span>
            ) : (
              <span className="bulk-scan-summary bulk-error">읽기 실패: {entry.message}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
