import dagre from "@dagrejs/dagre";
import type { Edge, Node } from "@xyflow/react";
import type { ChannelInfo, SongModel } from "./types";

export interface ChannelNodeData extends Record<string, unknown> {
  channel: ChannelInfo;
  docId?: string;
  songPath?: string;
}

const NODE_W = 210;
const NODE_H_BASE = 44;
const INSERT_H = 18;

function nodeHeight(ch: ChannelInfo): number {
  return NODE_H_BASE + Math.min(ch.inserts.length, 6) * INSERT_H;
}

/** 채널→버스→MIXOUT 좌→우 계층 레이아웃 (dagre LR). */
export function buildFlow(model: SongModel): { nodes: Node<ChannelNodeData>[]; edges: Edge[] } {
  const visible = model.channels.filter((c) => c.group !== "AudioInput");
  const uids = new Set(visible.map((c) => c.uid));

  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", nodesep: 18, ranksep: 90 });
  g.setDefaultEdgeLabel(() => ({}));
  for (const ch of visible) {
    g.setNode(ch.uid, { width: NODE_W, height: nodeHeight(ch) });
  }
  const edges: Edge[] = [];
  for (const e of model.graph.edges) {
    if (!uids.has(e.source) || !uids.has(e.target)) continue;
    g.setEdge(e.source, e.target);
    edges.push({
      id: `${e.kind}:${e.source}->${e.target}`,
      source: e.source,
      target: e.target,
      animated: e.kind === "send",
      style: e.kind === "send"
        ? { stroke: "#c084fc", strokeDasharray: "6 3" }
        : { stroke: "#64748b" },
    });
  }
  dagre.layout(g);

  const nodes: Node<ChannelNodeData>[] = visible.map((ch) => {
    const pos = g.node(ch.uid);
    return {
      id: ch.uid,
      type: "channel",
      position: { x: pos.x - NODE_W / 2, y: pos.y - nodeHeight(ch) / 2 },
      data: { channel: ch },
    };
  });
  return { nodes, edges };
}
