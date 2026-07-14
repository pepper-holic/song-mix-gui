import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Background, Controls, ReactFlow, type NodeMouseHandler, type Node,
        type ReactFlowInstance } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { api } from "./bridge";
import { ChannelNode } from "./ChannelNode";
import { DetailPanel } from "./DetailPanel";
import { buildFlow, type ChannelNodeData } from "./layout";
import type { ChannelInfo, DragPayload, SongDoc } from "./types";

const nodeTypes = { channel: ChannelNode };

type Props = {
  doc: SongDoc;
  paneId: string;
  onTransferDrop: (payload: DragPayload, dstDoc: SongDoc) => void;
  onCopyRequest: (doc: SongDoc, channel: ChannelInfo) => void;
  onChainCopyRequest: (doc: SongDoc, channel: ChannelInfo) => void;
  onPasteRequest: (dstDoc: SongDoc) => void;
  onUndoRequest: (doc: SongDoc) => void;
  onSetCompareBaseline: (doc: SongDoc, channel: ChannelInfo) => void;
  onCompareWith: (doc: SongDoc, channel: ChannelInfo) => void;
  onFocusPane?: () => void;
};

function matchesQuery(ch: ChannelInfo, query: string): boolean {
  const q = query.toLowerCase();
  if (ch.label.toLowerCase().includes(q) || ch.name.toLowerCase().includes(q)) return true;
  return ch.inserts.some((ins) => ins.pluginName.toLowerCase().includes(q));
}

export function SongPane({ doc, paneId, onTransferDrop, onCopyRequest, onChainCopyRequest,
                          onPasteRequest, onUndoRequest, onSetCompareBaseline, onCompareWith,
                          onFocusPane }: Props) {
  const [selected, setSelected] = useState<ChannelInfo | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterMode, setFilterMode] = useState(false);
  const [isDropTarget, setIsDropTarget] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const rfInstance = useRef<ReactFlowInstance<Node<ChannelNodeData>> | null>(null);
  const { nodes, edges } = useMemo(() => {
    const flow = buildFlow(doc.model);
    for (const n of flow.nodes) {
      n.data.docId = doc.id;
      n.data.songPath = doc.path;
    }
    return flow;
  }, [doc]);

  // U2 검색/필터(AC-2): 매칭 노드 하이라이트(.search-match) + 필터 모드 시 비매칭 dim(.search-dim)
  const styledNodes = useMemo(() => {
    const query = searchQuery.trim();
    if (!query) return nodes;
    return nodes.map((n) => {
      const isMatch = matchesQuery(n.data.channel, query);
      const className = isMatch ? "search-match" : filterMode ? "search-dim" : undefined;
      return { ...n, className };
    });
  }, [nodes, searchQuery, filterMode]);

  useEffect(() => {
    const query = searchQuery.trim();
    if (!query || !rfInstance.current) return;
    const first = nodes.find((n) => matchesQuery(n.data.channel, query));
    if (first) {
      const cx = first.position.x + 105;
      const cy = first.position.y + 40;
      rfInstance.current.setCenter(cx, cy, { zoom: 1, duration: 400 });
    }
  }, [searchQuery, nodes]);

  // P3 프리웜 우선순위(AC-5): 이 패널에 보이는 채널들의 플러그인 그룹을 프리웜 큐 선두로 승격
  useEffect(() => {
    const uids = doc.model.channels.map((c) => c.uid);
    void api.hintVisible(doc.path, uids).catch(() => {
      // Qt 브리지가 없는 dev 브라우저 모드 — 조용히 무시
    });
  }, [doc.path, doc.model]);

  const handleNodeClick: NodeMouseHandler<Node<ChannelNodeData>> = useCallback((_e, node) => {
    setSelected(node.data.channel);
    containerRef.current?.focus();  // Ctrl+C가 바로 먹도록 패널 포커스
  }, []);

  const handleNodeContextMenu: NodeMouseHandler<Node<ChannelNodeData>> = useCallback((e, node) => {
    e.preventDefault();
    setSelected(node.data.channel);
    const me = e as unknown as MouseEvent;
    if (me.ctrlKey) {
      onChainCopyRequest(doc, node.data.channel);  // S1: 체인 복사(트랙 포함, AC-7)
    } else if (me.shiftKey) {
      onSetCompareBaseline(doc, node.data.channel);
    } else if (me.altKey) {
      onCompareWith(doc, node.data.channel);
    } else {
      onCopyRequest(doc, node.data.channel);
    }
  }, [doc, onCopyRequest, onChainCopyRequest, onSetCompareBaseline, onCompareWith]);

  const handlePaneContextMenu = useCallback((e: React.MouseEvent | MouseEvent) => {
    e.preventDefault();
    onPasteRequest(doc);
  }, [doc, onPasteRequest]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    if (e.dataTransfer.types.includes("application/x-song-transfer")) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
      setIsDropTarget(true);
    }
  }, []);

  // 자식 노드로 이동할 때도 dragleave가 뜨므로, 실제로 패널 밖으로 나갈 때만 해제
  const handleDragLeave = useCallback((e: React.DragEvent) => {
    if (!e.currentTarget.contains(e.relatedTarget as globalThis.Node | null)) setIsDropTarget(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    setIsDropTarget(false);
    const raw = e.dataTransfer.getData("application/x-song-transfer");
    if (!raw) return;
    e.preventDefault();
    const payload = JSON.parse(raw) as DragPayload;
    onTransferDrop(payload, doc);
  }, [doc, onTransferDrop]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.ctrlKey && e.key.toLowerCase() === "c" && selected) {
      onCopyRequest(doc, selected);
      e.preventDefault();
    } else if (e.ctrlKey && e.key.toLowerCase() === "v") {
      onPasteRequest(doc);
      e.preventDefault();
    } else if (e.ctrlKey && e.key.toLowerCase() === "z") {
      onUndoRequest(doc);
      e.preventDefault();
    }
  }, [doc, selected, onCopyRequest, onPasteRequest, onUndoRequest]);

  return (
    <div
      ref={containerRef}
      className={isDropTarget ? "song-pane drop-active" : "song-pane"}
      data-pane={paneId}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onKeyDown={handleKeyDown}
      onFocus={onFocusPane}
      tabIndex={0}
    >
      <div className="pane-title">{doc.fileName}</div>
      <div className="pane-search">
        <input
          type="text"
          className="search-input"
          placeholder="채널/플러그인 검색…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        <label className="filter-toggle" title="선택 시 미매칭 노드를 흐리게 표시">
          <input
            type="checkbox"
            checked={filterMode}
            onChange={(e) => setFilterMode(e.target.checked)}
          />
          필터
        </label>
      </div>
      <ReactFlow
        nodes={styledNodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        onNodeContextMenu={handleNodeContextMenu}
        onPaneContextMenu={handlePaneContextMenu}
        onInit={(inst) => { rfInstance.current = inst; }}
        fitView
        minZoom={0.1}
        nodesDraggable={false}
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
      {selected && (
        <DetailPanel
          songPath={doc.path}
          channel={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
