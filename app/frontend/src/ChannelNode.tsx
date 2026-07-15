import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import type { ChannelNodeData } from "./layout";
import type { DragPayload } from "./types";

// C-1: 실제 색상 값은 styles.css :root 토큰이 유일한 소스 — 여기서는 var() 참조만 보관
export const KIND_COLORS: Record<string, string> = {
  track: "var(--kind-track)",
  group: "var(--kind-group)",
  effect: "var(--kind-effect)",
  output: "var(--kind-output)",
};

const KIND_LABELS_KO: Record<string, string> = {
  track: "트랙", group: "버스", effect: "FX", output: "아웃풋",
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
      id={ch.uid}
      className={`channel-node kind-${ch.kind} nodrag nopan`}
      style={{ background: KIND_COLORS[ch.kind] ?? "#333" }}
      draggable={draggable}
      onDragStart={draggable ? onDragStart : undefined}
      role="option"
      aria-label={
        `${ch.label || ch.name} — ${KIND_LABELS_KO[ch.kind] ?? ch.kind}, 인서트 ${ch.inserts.length}개`
      }
      title={draggable
        ? "드래그 또는 우클릭=복사 → 대상 패널 빈 곳 우클릭=붙여넣기"
        : ch.label}
    >
      <Handle type="target" position={Position.Left} />
      <div className="node-label">
        <span className="node-label-text" title={ch.label || ch.name}>{ch.label || ch.name}</span>
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
