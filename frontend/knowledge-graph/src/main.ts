import Graph from "graphology";
import Sigma from "sigma";

type GraphNode = { node_id: string; node_type?: string; payload?: Record<string, unknown> };
type GraphEdge = { edge_id: string; source_id: string; target_id: string; relation?: string };

const MAX_NODES = 500;
const colors: Record<string, string> = {
  person: "#2563eb",
  team: "#0f766e",
  task: "#7c3aed",
  workflow: "#b45309",
  sop: "#b45309",
  event: "#be123c",
  action: "#0369a1",
  evidence: "#15803d",
};

function title(node: GraphNode): string {
  return String(node.payload?.title || "연결된 항목");
}

function position(index: number, total: number, depth = 1): { x: number; y: number } {
  if (index === 0) return { x: 0, y: 0 };
  const angle = (Math.PI * 2 * (index - 1)) / Math.max(1, total - 1);
  const radius = Math.max(2, depth * 2);
  return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
}

async function load(panel: HTMLElement, sourceRef: string): Promise<{ nodes: GraphNode[]; edges: GraphEdge[] }> {
  const url = new URL(panel.dataset.exploreUrl || "/api/v2/knowledge-graph/explore", window.location.origin);
  url.searchParams.set("view", "neighbors");
  url.searchParams.set("source_ref", sourceRef);
  url.searchParams.set("depth", "1");
  url.searchParams.set("limit", "80");
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error("연결 관계를 불러오지 못했습니다.");
  return response.json();
}

async function render(panel: HTMLElement): Promise<void> {
  const container = panel.querySelector<HTMLElement>(".knowledge-graph-canvas");
  if (!container || container.dataset.ready === "true") return;
  container.dataset.ready = "true";
  const graph = new Graph({ multi: true, type: "directed" });
  const rootRef = panel.dataset.sourceRef || "";
  const addPayload = (payload: { nodes: GraphNode[]; edges: GraphEdge[] }) => {
    payload.nodes.slice(0, MAX_NODES - graph.order).forEach((node, index) => {
      if (graph.hasNode(node.node_id)) return;
      const point = position(graph.order + index, graph.order + payload.nodes.length);
      graph.addNode(node.node_id, {
        label: title(node),
        size: node.node_id === rootRef ? 12 : 8,
        color: colors[node.node_type || ""] || "#64748b",
        x: point.x,
        y: point.y,
        url: String(node.payload?.url || ""),
      });
    });
    payload.edges.forEach((edge) => {
      if (!graph.hasNode(edge.source_id) || !graph.hasNode(edge.target_id) || graph.hasEdge(edge.edge_id)) return;
      graph.addDirectedEdgeWithKey(edge.edge_id, edge.source_id, edge.target_id, {
        label: edge.relation || "related",
        color: "#94a3b8",
        size: 1.5,
      });
    });
  };
  try {
    addPayload(await load(panel, rootRef));
    const renderer = new Sigma(graph, container, { renderEdgeLabels: false, labelDensity: 0.1, labelGridCellSize: 120 });
    const status = panel.querySelector<HTMLElement>(".knowledge-explorer-status");
    if (status) status.textContent = "노드를 선택하면 주변 관계를 이어서 봅니다. 원문은 오른쪽 버튼으로 엽니다.";
    renderer.on("clickNode", async ({ node }) => {
      if (graph.order >= MAX_NODES) return;
      try {
        addPayload(await load(panel, node));
        renderer.refresh();
      } catch (_error) {
        if (status) status.textContent = "이 항목의 추가 관계를 불러오지 못했습니다.";
      }
    });
    panel.querySelector<HTMLButtonElement>("[data-knowledge-open-node]")?.addEventListener("click", () => {
      const selected = renderer.getCustomBBox() ? rootRef : rootRef;
      const url = String(graph.getNodeAttribute(selected, "url") || "");
      if (url) window.location.href = url;
    });
  } catch (error) {
    container.dataset.ready = "false";
    container.textContent = error instanceof Error ? error.message : "그래프를 표시하지 못했습니다.";
  }
}

document.addEventListener("boi:knowledge-graph-open", (event) => {
  const panel = (event as CustomEvent).detail?.panel as HTMLElement | undefined;
  if (panel) void render(panel);
});
