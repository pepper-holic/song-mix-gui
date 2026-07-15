import { Fragment, useEffect, useRef, useState } from "react";
import { IconFolderOpen } from "./Icons";
import { SongPane } from "./SongPane";
import type { LeafPane, PaneNode, SplitDirection, SplitPosition } from "./paneLayout";
import type { ChannelInfo, DragPayload, SongDoc } from "./types";

type Zone = "left" | "right" | "top" | "bottom" | "center";

interface TabDragPayload {
  docId: string;
  fromLeafId: string;
}

const TAB_MOVE_MIME = "application/x-tab-move";
const EDGE_FRACTION = 0.25;

function fileNameOf(path: string): string {
  return path.replace(/\\/g, "/").split("/").pop() ?? path;
}

function zoneOf(clientX: number, clientY: number, rect: DOMRect): Zone {
  const fx = (clientX - rect.left) / rect.width;
  const fy = (clientY - rect.top) / rect.height;
  if (fx < EDGE_FRACTION) return "left";
  if (fx > 1 - EDGE_FRACTION) return "right";
  if (fy < EDGE_FRACTION) return "top";
  if (fy > 1 - EDGE_FRACTION) return "bottom";
  return "center";
}

interface SongPaneHandlers {
  onTransferDrop: (payload: DragPayload, dstDoc: SongDoc) => void;
  onCopyRequest: (doc: SongDoc, channel: ChannelInfo) => void;
  onChainCopyRequest: (doc: SongDoc, channel: ChannelInfo) => void;
  onPasteRequest: (dstDoc: SongDoc) => void;
  onUndoRequest: (doc: SongDoc) => void;
  onSetCompareBaseline: (doc: SongDoc, channel: ChannelInfo) => void;
  onCompareWith: (doc: SongDoc, channel: ChannelInfo) => void;
}

interface Props extends SongPaneHandlers {
  node: PaneNode;
  docs: SongDoc[];
  recentFiles: string[];
  onOpenFromRecent: (path: string) => void;
  onFocusLeaf: (leafId: string) => void;
  onOpenDoc: () => void;
  onCloseTab: (docId: string) => void;
  onMoveTab: (docId: string, toLeafId: string, atIndex?: number) => void;
  onSplitTab: (targetLeafId: string, docId: string, direction: SplitDirection,
              position: SplitPosition) => void;
  onSelectTab: (leafId: string, docId: string) => void;
  onResizeSplit: (splitId: string, sizes: number[]) => void;
}

export function PaneGroup(props: Props) {
  return props.node.type === "split"
    ? <SplitContainer {...props} node={props.node} />
    : <LeafGroup {...props} node={props.node} />;
}

function SplitContainer(props: Props & { node: Extract<PaneNode, { type: "split" }> }) {
  const { node } = props;
  const containerRef = useRef<HTMLDivElement>(null);

  const handleResizeStart = (index: number) => (e: React.MouseEvent) => {
    e.preventDefault();
    const container = containerRef.current;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    const total = node.direction === "row" ? rect.width : rect.height;
    const startPos = node.direction === "row" ? e.clientX : e.clientY;
    const startSizes = [...node.sizes];
    const sizeSum = startSizes.reduce((a, b) => a + b, 0);
    const minSize = sizeSum * 0.1;

    const onMove = (ev: MouseEvent) => {
      const pos = node.direction === "row" ? ev.clientX : ev.clientY;
      const delta = ((pos - startPos) / total) * sizeSum;
      const next = [...startSizes];
      next[index - 1] = Math.max(minSize, startSizes[index - 1] + delta);
      next[index] = Math.max(minSize, startSizes[index] - delta);
      props.onResizeSplit(node.id, next);
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  return (
    <div ref={containerRef} className={`pane-split pane-split-${node.direction}`}>
      {node.children.map((child, i) => (
        <Fragment key={child.id}>
          {i > 0 && (
            <div
              className={`resize-handle resize-handle-${node.direction}`}
              onMouseDown={handleResizeStart(i)}
            />
          )}
          <div className="pane-split-child" style={{ flexGrow: node.sizes[i] }}>
            <PaneGroup {...props} node={child} />
          </div>
        </Fragment>
      ))}
    </div>
  );
}

interface CtxMenuState {
  docId: string;
  x: number;
  y: number;
}

function LeafGroup(props: Props & { node: LeafPane }) {
  const { node, docs } = props;
  const [dropZone, setDropZone] = useState<Zone | null>(null);
  const [ctxMenu, setCtxMenu] = useState<CtxMenuState | null>(null);
  const bodyRef = useRef<HTMLDivElement>(null);

  const tabs = node.docIds
    .map((id) => docs.find((d) => d.id === id))
    .filter((d): d is SongDoc => !!d);
  const activeDoc = tabs.find((d) => d.id === node.activeDocId) ?? tabs[0] ?? null;

  const handleTabDragStart = (docId: string) => (e: React.DragEvent) => {
    const payload: TabDragPayload = { docId, fromLeafId: node.id };
    e.dataTransfer.setData(TAB_MOVE_MIME, JSON.stringify(payload));
    e.dataTransfer.effectAllowed = "move";
  };

  const handleBodyDragOver = (e: React.DragEvent) => {
    if (!e.dataTransfer.types.includes(TAB_MOVE_MIME)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    const rect = bodyRef.current?.getBoundingClientRect();
    if (rect) setDropZone(zoneOf(e.clientX, e.clientY, rect));
  };

  const handleBodyDragLeave = (e: React.DragEvent) => {
    if (!e.currentTarget.contains(e.relatedTarget as globalThis.Node | null)) setDropZone(null);
  };

  const handleBodyDrop = (e: React.DragEvent) => {
    const raw = e.dataTransfer.getData(TAB_MOVE_MIME);
    setDropZone(null);
    if (!raw) return;
    e.preventDefault();
    const payload = JSON.parse(raw) as TabDragPayload;
    // dragover가 세팅한 dropZone state에 의존하지 않고 drop 이벤트 자체의 좌표로 다시
    // 계산한다 — 상태 갱신이 아직 반영되기 전에 drop이 발생하는 레이스를 원천 차단.
    const rect = bodyRef.current?.getBoundingClientRect();
    const zone = rect ? zoneOf(e.clientX, e.clientY, rect) : "center";
    if (zone === "center") {
      props.onMoveTab(payload.docId, node.id);
    } else {
      const direction: SplitDirection = zone === "left" || zone === "right" ? "row" : "column";
      const position: SplitPosition = zone === "left" || zone === "top" ? "before" : "after";
      props.onSplitTab(node.id, payload.docId, direction, position);
    }
  };

  const handleTabDrop = (targetIndex: number) => (e: React.DragEvent) => {
    const raw = e.dataTransfer.getData(TAB_MOVE_MIME);
    if (!raw) return;
    e.preventDefault();
    e.stopPropagation();
    const payload = JSON.parse(raw) as TabDragPayload;
    props.onMoveTab(payload.docId, node.id, targetIndex);
  };

  return (
    <div className="pane-leaf">
      <nav className="tabs">
        {tabs.map((d, i) => (
          <button
            type="button"
            key={d.id}
            draggable
            onDragStart={handleTabDragStart(d.id)}
            onDragOver={(e) => { if (e.dataTransfer.types.includes(TAB_MOVE_MIME)) e.preventDefault(); }}
            onDrop={handleTabDrop(i)}
            className={d.id === node.activeDocId ? "tab active" : "tab"}
            onClick={() => props.onSelectTab(node.id, d.id)}
            onContextMenu={(e) => {
              e.preventDefault();
              setCtxMenu({ docId: d.id, x: e.clientX, y: e.clientY });
            }}
            title="드래그: 이동/분할 · 우클릭: 분할 메뉴"
          >
            {d.fileName}
            <span
              className="tab-close"
              onClick={(e) => { e.stopPropagation(); props.onCloseTab(d.id); }}
            >
              ×
            </span>
          </button>
        ))}
      </nav>
      <div
        ref={bodyRef}
        className="pane-leaf-body"
        onDragOver={handleBodyDragOver}
        onDragLeave={handleBodyDragLeave}
        onDrop={handleBodyDrop}
      >
        {activeDoc ? (
          <SongPane
            doc={activeDoc} paneId={node.id}
            onTransferDrop={props.onTransferDrop}
            onCopyRequest={props.onCopyRequest}
            onChainCopyRequest={props.onChainCopyRequest}
            onPasteRequest={props.onPasteRequest}
            onUndoRequest={props.onUndoRequest}
            onSetCompareBaseline={props.onSetCompareBaseline}
            onCompareWith={props.onCompareWith}
            onFocusPane={() => props.onFocusLeaf(node.id)}
          />
        ) : (
          <div className="empty-pane">
            <div className="empty-pane-content">
              <span className="empty-pane-icon"><IconFolderOpen /></span>
              <p className="empty-pane-title">열려 있는 song 파일이 없습니다</p>
              <button type="button" className="empty-cta" onClick={props.onOpenDoc}>
                <span className="icon"><IconFolderOpen /></span>song 열기…
              </button>
              {props.recentFiles.length > 0 && (
                <ul className="recent-list">
                  {props.recentFiles.map((p) => (
                    <li key={p}>
                      <button type="button" onClick={() => props.onOpenFromRecent(p)}>
                        {fileNameOf(p)}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
        {dropZone && <div className={`pane-dropzone-overlay zone-${dropZone}`} />}
      </div>
      {ctxMenu && (
        <TabContextMenu
          x={ctxMenu.x}
          y={ctxMenu.y}
          onSplit={(direction, position) => {
            props.onSplitTab(node.id, ctxMenu.docId, direction, position);
            setCtxMenu(null);
          }}
          onClose={() => { props.onCloseTab(ctxMenu.docId); setCtxMenu(null); }}
          onDismiss={() => setCtxMenu(null)}
        />
      )}
    </div>
  );
}

function TabContextMenu({ x, y, onSplit, onClose, onDismiss }: {
  x: number;
  y: number;
  onSplit: (direction: SplitDirection, position: SplitPosition) => void;
  onClose: () => void;
  onDismiss: () => void;
}) {
  useEffect(() => {
    const onMouseDown = () => onDismiss();
    const onKeyDown = (e: KeyboardEvent) => { if (e.key === "Escape") onDismiss(); };
    window.addEventListener("mousedown", onMouseDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("mousedown", onMouseDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onDismiss]);

  return (
    <ul className="tab-context-menu" style={{ left: x, top: y }} onMouseDown={(e) => e.stopPropagation()}>
      <li><button type="button" onClick={() => onSplit("row", "before")}>왼쪽으로 분할</button></li>
      <li><button type="button" onClick={() => onSplit("row", "after")}>오른쪽으로 분할</button></li>
      <li><button type="button" onClick={() => onSplit("column", "before")}>위로 분할</button></li>
      <li><button type="button" onClick={() => onSplit("column", "after")}>아래로 분할</button></li>
      <li className="tab-context-menu-divider" />
      <li><button type="button" onClick={onClose}>탭 닫기</button></li>
    </ul>
  );
}
