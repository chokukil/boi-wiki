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
  comparison?: Record<string, unknown>;
  status?: string;
};

type ExplorerViewState = {
  selectedNodeId?: string;
  inspectorOpen?: boolean;
  camera?: { x?: number; y?: number; ratio?: number; angle?: number };
};

const MAX_NODES = 500;
const colors: Record<string, string> = {
  person: "#2563eb", team: "#0f766e", role: "#475569", task: "#7c3aed",
  workflow: "#b45309", sop: "#b45309", event: "#be123c", action: "#0369a1",
  evidence: "#15803d", data_artifact: "#047857", completion_record: "#166534",
};

const nodeTitle = (node: GraphNode): string => String(node.payload?.title || "연결된 항목");
const graphLabel = (value: string): string => value.length > 34 ? `${value.slice(0, 33)}…` : value;

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
  const graphVisible = ["explorer", "path", "workflow", "impact", "lineage", "responsibility"].includes(view);
  content.hidden = graphVisible;
  if (graphVisible) return;
  const resultRows = [payload.tour_steps, payload.steps, payload.timeline].find(
    (items) => Array.isArray(items) && items.length > 0,
  );
  let rows: Array<{ occurred_at?: string; title?: string; reason?: string }> = resultRows || [];
  if (!rows.length && ["neighbors", "compare"].includes(view)) {
    rows = (payload.nodes || [])
      .filter((node) => node.node_id !== panel.dataset.sourceRef)
      .map((node) => ({ title: nodeTitle(node), reason: view === "compare" ? "두 항목의 공통점과 차이를 비교한 관계" : "직접 연결된 업무 맥락" }));
  }
  if (!rows.length) {
    content.innerHTML = '<p class="muted">조건에 맞는 관계를 찾지 못했습니다.</p>';
    return;
  }
  const heading = view === "tour" ? "이 순서로 살펴보기" : view === "timeline" ? "시간에 따른 변화" : view === "compare" ? "두 항목 비교" : "직접 연결된 항목";
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
  let resizeObserver: ResizeObserver | null = null;
  let backgroundSuspended = false;
  let restoredState: ExplorerViewState = {};
  try { restoredState = JSON.parse(panel.dataset.graphState || "{}"); } catch (_error) { restoredState = {}; }
  if (restoredState.selectedNodeId) selectedRef = restoredState.selectedNodeId;
  const stateKey = panel.dataset.graphViewKey || rootRef;

  const emitState = (patch: ExplorerViewState = {}) => {
    const camera = renderer?.getCamera().getState();
    panel.dispatchEvent(new CustomEvent("boi:knowledge-graph-state", {
      bubbles: true,
      detail: {
        key: stateKey,
        selectedNodeId: selectedRef,
        inspectorOpen: Boolean(details && !details.hidden),
        camera: camera ? { x: camera.x, y: camera.y, ratio: camera.ratio, angle: camera.angle } : restoredState.camera,
        ...patch,
      },
    }));
  };
  const destroyRenderer = (preserveCamera = true) => {
    if (!renderer) return;
    if (preserveCamera) {
      const camera = renderer.getCamera().getState();
      restoredState.camera = { x: camera.x, y: camera.y, ratio: camera.ratio, angle: camera.angle };
    }
    resizeObserver?.disconnect();
    resizeObserver = null;
    renderer.kill();
    renderer = null;
  };
  const handleBackgroundVisuals = (event: Event) => {
    if (panel.closest(".agent-surface")) return;
    const paused = Boolean((event as CustomEvent).detail?.paused);
    if (paused === backgroundSuspended) {
      if (!paused) window.requestAnimationFrame(() => ensureRenderer());
      return;
    }
    backgroundSuspended = paused;
    if (paused) {
      destroyRenderer(true);
      panel.dataset.graphSuspended = "true";
      return;
    }
    panel.dataset.graphSuspended = "false";
    window.requestAnimationFrame(() => ensureRenderer());
  };
  const handleAgentVisuals = (event: Event) => {
    if (!panel.closest(".agent-surface")) return;
    const paused = Boolean((event as CustomEvent).detail?.paused);
    if (paused === backgroundSuspended) {
      if (!paused) window.requestAnimationFrame(() => ensureRenderer());
      return;
    }
    backgroundSuspended = paused;
    if (paused) {
      destroyRenderer(true);
      panel.dataset.graphSuspended = "true";
      return;
    }
    panel.dataset.graphSuspended = "false";
    window.requestAnimationFrame(() => ensureRenderer());
  };
  document.addEventListener("boi:background-visuals", handleBackgroundVisuals);
  document.addEventListener("boi:agent-visuals", handleAgentVisuals);
  const lifecycleObserver = new MutationObserver(() => {
    if (panel.isConnected) return;
    destroyRenderer(false);
    document.removeEventListener("boi:background-visuals", handleBackgroundVisuals);
    document.removeEventListener("boi:agent-visuals", handleAgentVisuals);
    lifecycleObserver.disconnect();
  });
  lifecycleObserver.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("pagehide", () => {
    destroyRenderer(false);
    document.removeEventListener("boi:background-visuals", handleBackgroundVisuals);
    document.removeEventListener("boi:agent-visuals", handleAgentVisuals);
    lifecycleObserver.disconnect();
  }, { once: true });
  const details = panel.querySelector<HTMLElement>("[data-knowledge-node-details]");
  const status = panel.querySelector<HTMLElement>(".knowledge-explorer-status");
  const pathSearch = panel.querySelector<HTMLElement>(".knowledge-path-search");

  const showDetails = (nodeRef: string) => {
    if (!graph.hasNode(nodeRef) || !details) return;
    selectedRef = nodeRef;
    const attributes = graph.getNodeAttributes(nodeRef);
    const incidentEdges = graph.edges(nodeRef).map((edgeId) => graph.getEdgeAttributes(edgeId));
    const relation = incidentEdges.find((item) => item.reason || item.label) || {};
    details.hidden = false;
    panel.classList.add("knowledge-node-inspector-open");
    details.querySelector<HTMLElement>("[data-knowledge-node-title]")!.textContent = String(attributes.fullLabel || attributes.label || "연결된 항목");
    details.querySelector<HTMLElement>("[data-knowledge-node-summary]")!.textContent = String(attributes.summary || "이 항목과 직접 연결된 업무 맥락입니다.");
    details.querySelector<HTMLElement>("[data-knowledge-node-kind]")!.textContent = String(attributes.kind || "업무 지식");
    details.querySelector<HTMLElement>("[data-knowledge-node-degree]")!.textContent = `${graph.degree(nodeRef)}개 관계`;
    details.querySelector<HTMLElement>("[data-knowledge-node-reason]")!.textContent = String(relation.reason || relation.label || "직접 연결된 업무 맥락");
    details.querySelector<HTMLElement>("[data-knowledge-node-provenance]")!.textContent = String(relation.provenance || attributes.provenance || "근거가 확인된 관계");
    details.querySelector<HTMLElement>("[data-knowledge-node-observed]")!.textContent = String(relation.observedAt || attributes.observedAt || "기록된 시점 없음");
    const openElement = details.querySelector<HTMLAnchorElement>("[data-knowledge-open-node]");
    if (openElement) {
      const url = String(attributes.url || "");
      openElement.hidden = !url;
      if (url) openElement.href = url;
    }
    container.setAttribute("aria-label", `${String(attributes.fullLabel || attributes.label || "연결된 항목")} 선택됨. 방향키로 다른 항목을 이동하고 Enter로 상세를 확인합니다.`);
    emitState({ selectedNodeId: nodeRef, inspectorOpen: true });
  };

  const closeDetails = () => {
    if (!details) return;
    details.hidden = true;
    panel.classList.remove("knowledge-node-inspector-open");
    emitState({ inspectorOpen: false });
    window.requestAnimationFrame(() => renderer?.resize());
  };

  const replaceGraph = (payload: GraphPayload) => {
    graph.clear();
    const nodes = (payload.nodes || []).slice(0, MAX_NODES);
    nodes.forEach((node, index) => {
      const point = position(index, nodes.length);
      const fullLabel = nodeTitle(node);
      graph.addNode(node.node_id, {
        label: graphLabel(fullLabel), fullLabel, size: node.node_id === rootRef ? 12 : 8,
        color: colors[node.node_type || ""] || "#64748b", x: point.x, y: point.y,
        url: String(node.payload?.url || ""), summary: String(node.payload?.summary || node.payload?.description || ""),
        kind: String(node.node_type || "업무 지식"), provenance: String(node.payload?.provenance || "근거가 확인된 관계"),
        observedAt: String(node.payload?.observed_at || node.payload?.valid_from || node.payload?.recorded_at || ""),
      });
    });
    (payload.edges || []).forEach((edge) => {
      if (!graph.hasNode(edge.source_id) || !graph.hasNode(edge.target_id) || graph.hasEdge(edge.edge_id)) return;
      graph.addDirectedEdgeWithKey(edge.edge_id, edge.source_id, edge.target_id, {
        label: edge.relation || "related", color: "#94a3b8", size: 1.5,
        reason: String(edge.payload?.reason || edge.payload?.description || edge.relation || ""),
        provenance: String(edge.payload?.provenance || "근거가 확인된 관계"),
        observedAt: String(edge.payload?.observed_at || edge.payload?.valid_from || edge.payload?.recorded_at || ""),
      });
    });
    renderer?.refresh();
    if (selectedRef && graph.hasNode(selectedRef) && !details?.hidden) showDetails(selectedRef);
  };

  const ensureRenderer = () => {
    if (!renderer && !backgroundSuspended && !container.hidden && container.clientWidth > 0) {
      renderer = new Sigma(graph, container, {
        renderEdgeLabels: false,
        labelDensity: 0.06,
        labelGridCellSize: 150,
        labelRenderedSizeThreshold: 8.5,
        stagePadding: 46,
        allowInvalidContainer: true,
      });
      const restoredCamera = restoredState.camera;
      if (restoredCamera && [restoredCamera.x, restoredCamera.y, restoredCamera.ratio].every((value) => Number.isFinite(Number(value)))) {
        renderer.getCamera().setState({
          x: Number(restoredCamera.x), y: Number(restoredCamera.y), ratio: Number(restoredCamera.ratio),
          angle: Number.isFinite(Number(restoredCamera.angle)) ? Number(restoredCamera.angle) : 0,
        });
      }
      renderer.getCamera().on("updated", () => emitState());
      renderer.on("clickNode", async ({ node }) => {
        showDetails(node);
        if (activeView !== "explorer" || graph.order >= MAX_NODES) return;
        const payload = await load(panel, "explorer", node);
        const existing = new Set(graph.nodes());
        const combined = { nodes: [...graph.nodes().map((id) => ({ node_id: id, node_type: String(graph.getNodeAttribute(id, "kind") || ""), payload: { title: graph.getNodeAttribute(id, "fullLabel") || graph.getNodeAttribute(id, "label"), url: graph.getNodeAttribute(id, "url"), summary: graph.getNodeAttribute(id, "summary") } })), ...(payload.nodes || []).filter((item) => !existing.has(item.node_id))], edges: [...graph.edges().map((id) => ({ edge_id: id, source_id: graph.source(id), target_id: graph.target(id), relation: String(graph.getEdgeAttribute(id, "label") || "related"), payload: { reason: graph.getEdgeAttribute(id, "reason"), provenance: graph.getEdgeAttribute(id, "provenance"), observed_at: graph.getEdgeAttribute(id, "observedAt") } })), ...(payload.edges || [])] };
        replaceGraph(combined);
        showDetails(node);
      });
      resizeObserver = new ResizeObserver(() => renderer?.resize());
      resizeObserver.observe(container);
    }
  };

  const switchView = async (view: string) => {
    activeView = view;
    panel.dataset.activeView = view;
    const graphVisible = ["explorer", "path", "workflow", "impact", "lineage", "responsibility"].includes(view);
    const graphLayout = panel.querySelector<HTMLElement>(".knowledge-graph-hub-layout");
    if (!graphVisible && renderer) {
      destroyRenderer(true);
    }
    if (graphLayout) graphLayout.hidden = !graphVisible;
    panel.querySelectorAll<HTMLButtonElement>("[data-knowledge-view]").forEach((button) => {
      const active = button.dataset.knowledgeView === view;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
    const needsTarget = view === "path" || view === "compare";
    if (pathSearch) pathSearch.hidden = !needsTarget;
    if (needsTarget && !targetRef) {
      renderTextResult(panel, {}, view);
      if (status) status.textContent = view === "compare" ? "비교할 항목을 검색해 선택해주세요." : "도착 항목을 검색해 선택하면 실제 연결 경로를 계산합니다.";
      return;
    }
    if (status) status.textContent = "관계 근거를 확인하고 있습니다.";
    const payload = await load(panel, view, rootRef, targetRef);
    renderTextResult(panel, payload, view);
    if (graphVisible) {
      replaceGraph(payload);
      ensureRenderer();
    }
    if (status) status.textContent = payload.status === "not_connected" ? "두 항목 사이에서 확인된 경로가 없습니다." : "근거가 확인된 관계만 표시합니다.";
  };

  try {
    replaceGraph(initialPayload || await load(panel, "explorer", rootRef));
    ensureRenderer();
    details?.querySelectorAll<HTMLElement>("[data-knowledge-node-close]").forEach((button) => button.addEventListener("click", closeDetails));
    container.addEventListener("keydown", (event) => {
      const nodes = graph.nodes();
      if (!nodes.length) return;
      const currentIndex = Math.max(0, nodes.indexOf(selectedRef));
      if (["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(event.key)) {
        event.preventDefault();
        const direction = ["ArrowRight", "ArrowDown"].includes(event.key) ? 1 : -1;
        const next = nodes[(currentIndex + direction + nodes.length) % nodes.length];
        showDetails(next);
      } else if (event.key === "Enter") {
        event.preventDefault();
        showDetails(nodes[currentIndex] || nodes[0]);
      } else if (event.key === "Escape" && details && !details.hidden) {
        event.preventDefault();
        event.stopPropagation();
        closeDetails();
      }
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
      candidates.querySelectorAll<HTMLButtonElement>("[data-target-ref]").forEach((button) => button.addEventListener("click", () => { targetRef = button.dataset.targetRef || ""; void switchView(activeView === "compare" ? "compare" : "path"); }));
    });
    if (status) status.textContent = "노드를 선택하면 주변 관계를 이어서 봅니다.";
    if (restoredState.inspectorOpen && restoredState.selectedNodeId && graph.hasNode(restoredState.selectedNodeId)) showDetails(restoredState.selectedNodeId);
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
