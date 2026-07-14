"""채널→버스→MIXOUT 라우팅 그래프 빌드."""
from dataclasses import dataclass, field

from .mixer_parser import Channel, MixerModel


@dataclass(frozen=True)
class Edge:
    source_uid: str
    target_uid: str
    kind: str  # "output" | "send"


@dataclass
class RoutingGraph:
    nodes: dict[str, Channel] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)

    def children_of(self, uid: str) -> list[str]:
        return [e.source_uid for e in self.edges
                if e.target_uid == uid and e.kind == "output"]

    def subtree_uids(self, root_uid: str) -> set[str]:
        """root로 output-라우팅되는 채널 전체 (root 포함)."""
        seen: set[str] = set()
        stack = [root_uid]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(self.children_of(cur))
        return seen

    def path_to_terminal(self, uid: str) -> list[str]:
        """uid에서 output 체인을 따라 종단(MIXOUT/메인)까지의 라벨 경로."""
        path = []
        cur = uid
        visited = set()
        while cur and cur not in visited:
            visited.add(cur)
            node = self.nodes.get(cur)
            if node is None:
                break
            path.append(node.label)
            cur = node.destination_uid
        return path

    def to_dict(self) -> dict:
        return {
            "nodes": [{"uid": c.uid, "label": c.label, "kind": c.kind,
                       "group": c.group,
                       "insertCount": len(c.inserts)} for c in self.nodes.values()],
            "edges": [{"source": e.source_uid, "target": e.target_uid,
                       "kind": e.kind} for e in self.edges],
        }


def build_graph(model: MixerModel) -> RoutingGraph:
    graph = RoutingGraph(nodes=model.by_uid())
    for ch in model.channels:
        if ch.destination_uid and ch.destination_uid in graph.nodes:
            graph.edges.append(Edge(ch.uid, ch.destination_uid, "output"))
        for send in ch.sends:
            if send.destination_uid in graph.nodes:
                graph.edges.append(Edge(ch.uid, send.destination_uid, "send"))
    return graph
