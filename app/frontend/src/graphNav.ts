/** 그래프 키보드 내비게이션용 순수 함수 — React/DOM 의존 없음(리뷰·테스트 용이). */

export interface NavNode {
  id: string;
  x: number;
  y: number;
}

export type NavDirection = "up" | "down" | "left" | "right";

/** x좌표(반올림)로 열 그룹화 후, 각 열은 y로, 열 자체는 x로 정렬한다.
 * dagre LR 레이아웃은 같은 랭크(열)의 노드에 동일한 x를 배정하므로 반올림만으로 충분하다. */
export function buildColumns(nodes: NavNode[]): NavNode[][] {
  const byX = new Map<number, NavNode[]>();
  for (const n of nodes) {
    const key = Math.round(n.x);
    const list = byX.get(key) ?? [];
    list.push(n);
    byX.set(key, list);
  }
  return [...byX.entries()]
    .sort(([a], [b]) => a - b)
    .map(([, list]) => [...list].sort((a, b) => a.y - b.y));
}

/** 방향키 입력에 따른 다음 노드 id. 열의 끝/그래프의 좌우 끝에서는 이동하지 않는다(clamp). */
export function nextNode(columns: NavNode[][], currentId: string | null,
                          direction: NavDirection): string | null {
  if (columns.length === 0) return null;
  if (currentId === null) return columns[0][0]?.id ?? null;

  let colIdx = -1;
  let rowIdx = -1;
  for (let c = 0; c < columns.length; c++) {
    const r = columns[c].findIndex((n) => n.id === currentId);
    if (r !== -1) { colIdx = c; rowIdx = r; break; }
  }
  if (colIdx === -1) return columns[0][0]?.id ?? null;

  if (direction === "up") return columns[colIdx][Math.max(0, rowIdx - 1)].id;
  if (direction === "down") {
    return columns[colIdx][Math.min(columns[colIdx].length - 1, rowIdx + 1)].id;
  }

  const targetCol = direction === "left" ? colIdx - 1 : colIdx + 1;
  if (targetCol < 0 || targetCol >= columns.length) return currentId;

  const currentY = columns[colIdx][rowIdx].y;
  let best = columns[targetCol][0];
  let bestDist = Math.abs(best.y - currentY);
  for (const n of columns[targetCol]) {
    const d = Math.abs(n.y - currentY);
    if (d < bestDist) { best = n; bestDist = d; }
  }
  return best.id;
}
