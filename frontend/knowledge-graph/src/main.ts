import Graph from "graphology";
import Sigma from "sigma";

type GraphNode = { node_id: string; node_type?: string; payload?: Record<string, unknown> };
type GraphEdge = { edge_id: string; source_id: string; target_id: string; relation?: string; payload?: Record<string, unknown> };
type GraphPayload = {
  view?: string;
  nodes?: GraphNode[];
  edges?: GraphEdge[];
  steps?: Array<{ order?: number; ref?: string; node_ref?: string; title?: string; reason?: string }>;
  tour_steps?: Array<{ order?: number; node_ref?: string; title?: string; reason?: string }>;
  timeline?: Array<{ occurred_at?: string; title?: string }>;
  affected_refs?: string[];
  status?: string;
};

const MAX_NODES = 500;
const colors: Record<string, string> = {
  person: "#2563eb", team: "#0f766e", role: "#475569", task: "#7c3aed",
  workflow: "#b45309", sop: "#b45309", event: "#be123c", action: "#0369a1",
  evidence: "#15803d", data_artifact: "#047857", completion_record: "#166534",
};

const nodeTitle = (node: GraphNode): string => String(node.payload?.title || "연결된 항목");

function position(index: number, total: number): { x: number; y: number } {
  if (index === 0) return { x: 0, y: 0 };
  const angle = (Math.PI * 2 * (index - 1)) / Math.max(1, total - 1);
  const radius = 2 + Math.floor(index / 18) * 1.5;
  return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
}

function endpoint(panel: HTMLElement, view: string, sourceRef: string, targetRef = ""): URL {
  const url = new URL(panel.dataset.exploreUrl || "/api/v2/knowledge-graph/explore", window.location.origin);
  url.searchParams.set("view", view === "explorer" ? "neighbors" : view);
  url.searchParams.set("source_ref", sourceRef);
  url.searchParams.set("depth", view === "path" ? "6" : "3");
  url.searchParams.set("limit", view === "explorer" ? "80" : "120");
  if (targetRef) url.searchParams.set("target_ref", targetRef);
  return url;
}

async function load(panel: HTMLElement, view: string, sourceRef: string, targetRef = ""): Promise<GraphPayload> {
  const response = await fetch(endpoint(panel, view, sourceRef, targetRef), { headers: { Accept: "application/json" } });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(String(payload.detail || "연결 관계를 불러오지 못했습니다."));
  }
  return response.json();
}

function renderTextResult(panel: HTMLElement, payload: GraphPayload, view: string): void {
  const content = panel.querySelector<HTMLElement>(".knowledge-explorer-content");
  const graphLayout = panel.querySelector<HTMLElement>(".knowledge-graph-hub-layout");
  if (!content || !graphLayout) return;
  graphLayout.hidden = view !== "explorer" && view !== "path" && view !== "impact";
  content.hidden = !graphLayout.hidden;
  if (!graphLayout.hidden) return;
  const rows = payload.tour_steps || payload.steps || payload.timeline || [];
  if (!rows.length) {
    content.innerHTML = '<p class="muted">조건에 맞는 관계를 찾지 못했습니다.</p>';
    return;
  }
  const heading = view === "tour" ? "이 순서로 살펴보기" : view === "timeline" ? "시간에 따른 변화" : "관계 결과";
  content.innerHTML = `<h2>${heading}</h2><ol>${rows.map((row) => {
    const title = String(row.title || "연결된 항목");
    const detail = "occurred_at" in row ? String(row.occurred_at || "") : String(row.reason || "");
    return `<li><strong>${title.replace(/[<>&]/g, "")}</strong>${detail ? `<span>${detail.replace(/[<>&]/g, "")}</span>` : ""}</li>`;
  }).join("")}</ol>`;
}

async function render(panel: HTMLElement, initialPayload?: GraphPayload): Promise<void> {
  const container = panel.querySelector<HTMLElement>(".knowledge-graph-canvas");
  if (!container || container.dataset.ready === "true") return;
  container.dataset.ready = "true";
  const graph = new Graph({ multi: true, type: "directed" });
  const rootRef = panel.dataset.sourceRef || "";
  let selectedRef = rootRef;
  let activeView = "explorer";
  let targetRef = "";
  let renderer: Sigma | null = null;
  const details = panel.querySelector<HTMLElement>("[data-knowledge-node-details]");
  const status = panel.querySelector<HTMLElement>(".knowledge-explorer-status");
  const pathSearch = panel.querySelector<HTMLElement>(".knowledge-path-search");

  const showDetails = (nodeRef: string) => {
    if (!graph.hasNode(nodeRef) || !details) return;
    selectedRef = nodeRef;
    const attributes = graph.getNodeAttributes(nodeRef);
    details.querySelector<HTMLElement>("[data-knowledge-node-title]")!.textContent = String(attributes.label || "연결된 항목");
    details.querySelector<HTMLElement>("[data-knowledge-node-summary]")!.textContent = String(attributes.summary || "이 항목과 직접 연결된 업무 맥락입니다.");
    details.querySelector<HTMLElement>("[data-knowledge-node-kind]")!.textContent = String(attributes.kind || "업무 지식");
    details.querySelector<HTMLElement>("[data-knowledge-node-degree]")!.textContent = `${graph.degree(nodeRef)}개 관계`;
    details.querySelector<HTMLElement>("[data-knowledge-node-provenance]")!.textContent = String(attributes.provenance || "근거가 확인된 관계");
    const openElement = details.querySelector<HTMLAnchorElement>("[data-knowledge-open-node]");
    if (openElement) {
      const url = String(attributes.url || "");
      openElement.hidden = !url;
      if (url) openElement.href = url;
    }
  };

  const replaceGraph = (payload: GraphPayload) => {
    graph.clear();
    const nodes = (payload.nodes || []).slice(0, MAX_NODES);
    nodes.forEach((node, index) => {
      const point = position(index, nodes.length);
      graph.addNode(node.node_id, {
        label: nodeTitle(node), size: node.node_id === rootRef ? 12 : 8,
        color: colors[node.node_type || ""] || "#64748b", x: point.x, y: point.y,
        url: String(node.payload?.url || ""), summary: String(node.payload?.summary || node.payload?.description || ""),
        kind: String(node.node_type || "업무 지식"), provenance: String(node.payload?.provenance || "근거가 확인된 관계"),
      });
    });
    (payload.edges || []).forEach((edge) => {
      if (!graph.hasNode(edge.source_id) || !graph.hasNode(edge.target_id) || graph.hasEdge(edge.edge_id)) return;
      graph.addDirectedEdgeWithKey(edge.edge_id, edge.source_id, edge.target_id, { label: edge.relation || "related", color: "#94a3b8", size: 1.5 });
    });
    renderer?.refresh();
    if (graph.hasNode(rootRef)) showDetails(rootRef);
  };

  const switchView = async (view: string) => {
    activeView = view;
    panel.querySelectorAll<HTMLButtonElement>("[data-knowledge-view]").forEach((button) => {
      const active = button.dataset.knowledgeView === view;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
    if (pathSearch) pathSearch.hidden = view !== "path";
    if (view === "path" && !targetRef) {
      renderTextResult(panel, {}, "path");
      if (status) status.textContent = "도착 항목을 검색해 선택하면 실제 연결 경로를 계산합니다.";
      return;
    }
    if (status) status.textContent = "관계 근거를 확인하고 있습니다.";
    const payload = await load(panel, view, rootRef, targetRef);
    renderTextResult(panel, payload, view);
    if (["explorer", "path", "impact"].includes(view)) replaceGraph(payload);
    if (status) status.textContent = payload.status === "not_connected" ? "두 항목 사이에서 확인된 경로가 없습니다." : "근거가 확인된 관계만 표시합니다.";
  };

  try {
    replaceGraph(initialPayload || await load(panel, "explorer", rootRef));
    renderer = new Sigma(graph, container, { renderEdgeLabels: false, labelDensity: 0.1, labelGridCellSize: 120 });
    renderer.on("clickNode", async ({ node }) => {
      showDetails(node);
      if (activeView !== "explorer" || graph.order >= MAX_NODES) return;
      const payload = await load(panel, "explorer", node);
      const existing = new Set(graph.nodes());
      const combined = { nodes: [...graph.nodes().map((id) => ({ node_id: id, node_type: String(graph.getNodeAttribute(id, "kind") || ""), payload: { title: graph.getNodeAttribute(id, "label"), url: graph.getNodeAttribute(id, "url"), summary: graph.getNodeAttribute(id, "summary") } })), ...(payload.nodes || []).filter((item) => !existing.has(item.node_id))], edges: [...graph.edges().map((id) => ({ edge_id: id, source_id: graph.source(id), target_id: graph.target(id), relation: String(graph.getEdgeAttribute(id, "label") || "related") })), ...(payload.edges || [])] };
      replaceGraph(combined);
      showDetails(node);
    });
    panel.querySelectorAll<HTMLButtonElement>("[data-knowledge-view]").forEach((button) => button.addEventListener("click", () => void switchView(button.dataset.knowledgeView || "explorer")));
    panel.querySelector<HTMLButtonElement>("[data-knowledge-search]")?.addEventListener("click", async () => {
      const query = panel.querySelector<HTMLInputElement>("#knowledge-path-query")?.value.trim() || "";
      const candidates = panel.querySelector<HTMLElement>(".knowledge-path-candidates");
      if (!query || !candidates) return;
      const url = endpoint(panel, "ranked", rootRef);
      url.searchParams.set("q", query);
      const response = await fetch(url, { headers: { Accept: "application/json" } });
      const payload = await response.json();
      const items = (payload.items || []).slice(0, 5);
      candidates.innerHTML = items.map((item: Record<string, unknown>) => `<button type="button" class="button secondary" data-target-ref="${String(item.evidence_id || "").replace(/[\"<>]/g, "")}">${String(item.title || "연결된 항목").replace(/[<>&]/g, "")}</button>`).join("");
      candidates.querySelectorAll<HTMLButtonElement>("[data-target-ref]").forEach((button) => button.addEventListener("click", () => { targetRef = button.dataset.targetRef || ""; void switchView("path"); }));
    });
    if (status) status.textContent = "노드를 선택하면 주변 관계를 이어서 봅니다.";
    if (graph.hasNode(rootRef)) showDetails(rootRef);
  } catch (error) {
    container.dataset.ready = "false";
    container.textContent = error instanceof Error ? error.message : "그래프를 표시하지 못했습니다.";
  }
}

document.addEventListener("boi:knowledge-graph-open", (event) => {
  const panel = (event as CustomEvent).detail?.panel as HTMLElement | undefined;
  if (panel) void render(panel);
});
document.addEventListener("boi:knowledge-graph-render", (event) => {
  const detail = (event as CustomEvent).detail || {};
  if (detail.panel && detail.payload) void render(detail.panel, detail.payload);
});
document.addEventListener("DOMContentLoaded", () => document.querySelectorAll<HTMLElement>('[data-auto-open="true"]').forEach((panel) => void render(panel)));
(window as unknown as { BoiKnowledgeGraph?: { renderPayload: typeof render } }).BoiKnowledgeGraph = { renderPayload: render };
