import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import type { ChannelNodeData } from "./layout";
import type { DragPayload } from "./types";

export const KIND_COLORS: Record<string, string> = {
  track: "#1e3a5f",
  group: "#4a2d5f",
  effect: "#5f452d",
  output: "#2d5f3a",
};

export function ChannelNode({ data }: NodeProps<Node<ChannelNodeData>>) {
  const ch = data.channel;
  const draggable = ch.kind === "group" || ch.kind === "effect" || ch.kind === "track";

  const onDragStart = (e: React.DragEvent) => {
    const payload: DragPayload = {
      docId: data.docId ?? "",
      srcPath: data.songPath ?? "",
      rootUid: ch.uid,
      label: ch.label,
      mode: ch.kind === "track" ? "track" : "subtree",
    };
    e.dataTransfer.setData("application/x-song-transfer", JSON.stringify(payload));
    e.dataTransfer.effectAllowed = "copy";
  };

  return (
    // nodrag/nopan: React Flow가 포인터를 가로채 패닝하는 것을 막아
    // HTML5 네이티브 드래그가 시작되게 한다
    <div
      className={`channel-node kind-${ch.kind} nodrag nopan`}
      style={{ background: KIND_COLORS[ch.kind] ?? "#333" }}
      draggable={draggable}
      onDragStart={draggable ? onDragStart : undefined}
      title={draggable
        ? "드래그 또는 우클릭=복사 → 대상 패널 빈 곳 우클릭=붙여넣기"
        : ch.label}
    >
      <Handle type="target" position={Position.Left} />
      <div className="node-label">
        {ch.label || ch.name}
        {draggable && <span className="drag-hint">⠿</span>}
      </div>
      {ch.inserts.length > 0 && (
        <ol className="insert-badges">
          {ch.inserts.slice(0, 6).map((ins) => (
            <li key={ins.uid} className="insert-badge">
              <span className="insert-order">{ins.order + 1}</span> {ins.pluginName}
            </li>
          ))}
          {ch.inserts.length > 6 && <li className="insert-more">+{ch.inserts.length - 6}</li>}
        </ol>
      )}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
