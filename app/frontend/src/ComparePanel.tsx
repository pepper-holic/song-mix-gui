import type { CompareRow } from "./types";

type Props = {
  leftLabel: string;
  rightLabel: string;
  rows: CompareRow[];
  onClose: () => void;
};

/** U4 체인 비교 뷰 — 렌더 전용(diff 계산은 engine.introspect.compare, pytest로 검증됨). */
export function ComparePanel({ leftLabel, rightLabel, rows, onClose }: Props) {
  return (
    <div className="compare-panel">
      <header>
        <h2>체인 비교: {leftLabel} ↔ {rightLabel}</h2>
        <button type="button" className="close-btn" onClick={onClose}>×</button>
      </header>
      <table className="compare-table">
        <thead>
          <tr>
            <th>슬롯</th>
            <th>{leftLabel}</th>
            <th>{rightLabel}</th>
            <th>차이</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.slot} className={`compare-row row-${r.rowType}`}>
              <td>{r.slot + 1}</td>
              <td>{r.leftPlugin ?? "(없음)"}</td>
              <td>{r.rightPlugin ?? "(없음)"}</td>
              <td>
                {!r.interpretable && (
                  <span className="badge-uninterpretable">해석 불가 (복사 가능)</span>
                )}
                {r.rowType === "chain-mismatch" && (
                  <span className="compare-mismatch">체인 불일치</span>
                )}
                {r.diffs.length > 0 && (
                  <ul className="diff-list">
                    {r.diffs.map((d) => (
                      <li key={d.name}>
                        <strong>{d.name}</strong>: {d.leftValue ?? "-"} → {d.rightValue ?? "-"}
                      </li>
                    ))}
                  </ul>
                )}
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr><td colSpan={4}>비교할 인서트가 없습니다.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
