/** VSCode식 자유 분할 패널 레이아웃 — 순수 함수, React/DOM 의존 없음(graphNav.ts와 동일 스타일).
 * 문서(SongDoc) 하나는 항상 정확히 하나의 leaf에만 속한다. 불변식: 비-루트 leaf는 항상
 * docIds.length >= 1, split은 항상 children.length >= 2(그 이하로 줄면 자동 평탄화). */

export type SplitDirection = "row" | "column";
export type SplitPosition = "before" | "after";

export interface LeafPane {
  type: "leaf";
  id: string;
  docIds: string[];
  activeDocId: string | null;
}

export interface SplitPane {
  type: "split";
  id: string;
  direction: SplitDirection;
  children: PaneNode[];
  sizes: number[];
}

export type PaneNode = LeafPane | SplitPane;

let idSeq = 0;
function nextId(prefix: string): string {
  return `${prefix}${++idSeq}`;
}

export function createLeaf(docId: string | null): LeafPane {
  return { type: "leaf", id: nextId("leaf"), docIds: docId ? [docId] : [], activeDocId: docId };
}

export function findLeaf(node: PaneNode, leafId: string): LeafPane | null {
  if (node.type === "leaf") return node.id === leafId ? node : null;
  for (const child of node.children) {
    const found = findLeaf(child, leafId);
    if (found) return found;
  }
  return null;
}

export function findLeafByDocId(node: PaneNode, docId: string): LeafPane | null {
  if (node.type === "leaf") return node.docIds.includes(docId) ? node : null;
  for (const child of node.children) {
    const found = findLeafByDocId(child, docId);
    if (found) return found;
  }
  return null;
}

export function collectLeafIds(node: PaneNode): string[] {
  return node.type === "leaf" ? [node.id] : node.children.flatMap(collectLeafIds);
}

export function firstLeafId(node: PaneNode): string {
  return node.type === "leaf" ? node.id : firstLeafId(node.children[0]);
}

/** node 안의 leafId를 가진 leaf를 updater 결과(leaf 또는 split)로 치환한다(불변). */
function replaceLeaf(node: PaneNode, leafId: string, updater: (leaf: LeafPane) => PaneNode): PaneNode {
  if (node.type === "leaf") {
    return node.id === leafId ? updater(node) : node;
  }
  return { ...node, children: node.children.map((c) => replaceLeaf(c, leafId, updater)) };
}

export function setActiveDoc(node: PaneNode, docId: string): PaneNode {
  if (node.type === "leaf") {
    return node.docIds.includes(docId) ? { ...node, activeDocId: docId } : node;
  }
  return { ...node, children: node.children.map((c) => setActiveDoc(c, docId)) };
}

export function openDocInLeaf(node: PaneNode, leafId: string, docId: string): PaneNode {
  return replaceLeaf(node, leafId, (leaf) => ({
    ...leaf,
    docIds: leaf.docIds.includes(docId) ? leaf.docIds : [...leaf.docIds, docId],
    activeDocId: docId,
  }));
}

/** docId를 트리 전체에서 제거한다. 제거로 leaf가 비면(루트가 아닌 한) 그 leaf 자체를
 * 부모에서 제거하고, 형제가 하나만 남으면 split을 그 형제로 치환해 자동 평탄화한다. */
export function closeDocFromLayout(node: PaneNode, docId: string): PaneNode {
  if (node.type === "leaf") {
    if (!node.docIds.includes(docId)) return node;
    const docIds = node.docIds.filter((id) => id !== docId);
    const activeDocId = node.activeDocId === docId ? (docIds[0] ?? null) : node.activeDocId;
    return { ...node, docIds, activeDocId };
  }
  const children: PaneNode[] = [];
  const sizes: number[] = [];
  for (let i = 0; i < node.children.length; i++) {
    const child = node.children[i];
    const isNowEmptyLeaf = child.type === "leaf" && child.docIds.length === 1
      && child.docIds[0] === docId;
    if (isNowEmptyLeaf) continue;
    children.push(closeDocFromLayout(child, docId));
    sizes.push(node.sizes[i]);
  }
  if (children.length === node.children.length) return { ...node, children, sizes };
  if (children.length === 1) return children[0];
  return { ...node, children, sizes };
}

/** docId를 어디에 있든 떼어내(closeDocFromLayout) toLeafId에 다시 삽입한다.
 * atIndex 지정 시 그 위치에(재정렬 포함), 생략 시 맨 뒤에 추가. */
export function moveDocToLeaf(node: PaneNode, docId: string, toLeafId: string, atIndex?: number): PaneNode {
  const detached = closeDocFromLayout(node, docId);
  return replaceLeaf(detached, toLeafId, (leaf) => {
    const without = leaf.docIds.filter((id) => id !== docId);
    const index = atIndex ?? without.length;
    const docIds = [...without.slice(0, index), docId, ...without.slice(index)];
    return { ...leaf, docIds, activeDocId: docId };
  });
}

/** targetLeafId를 새 SplitPane으로 교체하고, direction/position에 따라 docId만 담은 새
 * leaf를 그 옆에 만든다. docId는 원래 있던 곳에서 제거된다. 자기 자신의 유일한 탭을
 * 자기 자신에 분할하려는 무의미한 시도는 무시(no-op)한다. */
export function splitLeafWithDoc(
  node: PaneNode, targetLeafId: string, docId: string,
  direction: SplitDirection, position: SplitPosition,
): PaneNode {
  const sourceLeaf = findLeafByDocId(node, docId);
  if (sourceLeaf && sourceLeaf.id === targetLeafId && sourceLeaf.docIds.length === 1) {
    return node;
  }
  const detached = closeDocFromLayout(node, docId);
  const newLeaf = createLeaf(docId);
  return replaceLeaf(detached, targetLeafId, (leaf) => ({
    type: "split",
    id: nextId("split"),
    direction,
    children: position === "before" ? [newLeaf, leaf] : [leaf, newLeaf],
    sizes: [1, 1],
  }));
}

export function resizeSplit(node: PaneNode, splitId: string, sizes: number[]): PaneNode {
  if (node.type === "leaf") return node;
  if (node.id === splitId) return { ...node, sizes };
  return { ...node, children: node.children.map((c) => resizeSplit(c, splitId, sizes)) };
}
