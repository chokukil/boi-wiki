import Graph from "graphology";
import forceAtlas2 from "graphology-layout-forceatlas2";
import FA2Layout from "graphology-layout-forceatlas2/worker";
import noverlap from "graphology-layout-noverlap";
import Sigma from "sigma";
import { EdgeArrowProgram } from "sigma/rendering";

type GraphNode = { node_id: string; node_type?: string; payload?: Record<string, unknown> };
type GraphEdge = {
  edge_id: string;
  source_id: string;
  target_id: string;
  relation?: string;
  relation_family?: string;
  user_label?: string;
  display_priority?: number;
  payload?: Record<string, unknown>;
};
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
  empty_reason?: string;
  primary_path?: string[];
  legend?: Array<{ relation_family?: string; labels?: string[] }>;
  layout_hint?: string;
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
const relationColors: Record<string, string> = {
  structure: "#7c3aed", sequence: "#2563eb", work: "#0369a1", event: "#be123c",
  result: "#15803d", responsibility: "#c2410c", organization: "#0f766e",
  lineage: "#4d7c0f", concept: "#64748b", reference: "#94a3b8", change: "#b45309", other: "#64748b",
};

const nodeTitle = (node: GraphNode): string => String(node.payload?.title || "연결된 항목");
const graphLabel = (value: string): string => value.length > 24 ? `${value.slice(0, 23)}…` : value;

function seededPosition(value: string, focal: boolean): { x: number; y: number } {
  if (focal) return { x: 0, y: 0 };
  let seed = 2166136261;
  for (const character of value) seed = Math.imul(seed ^ character.charCodeAt(0), 16777619);
  const angle = ((seed >>> 0) / 0xffffffff) * Math.PI * 2;
  const radius = 1.2 + (((seed >>> 8) & 255) / 255) * 2.8;
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
  const graphLayout = panel.querySelector<HTMLElement>(".knowledge-graph-hub-layout, .knowledge-graph-shell");
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
    const message = String(payload.empty_reason || "조건에 맞는 관계를 찾지 못했습니다.").replace(/[<>&]/g, "");
    content.innerHTML = `<p class="muted">${message}</p>`;
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
  let layoutSupervisor: FA2Layout | null = null;
  let layoutSettleTimer = 0;
  let visibilityRetryTimer = 0;
  let visibilityRetryCount = 0;
  let resizeObserver: ResizeObserver | null = null;
  let backgroundSuspended = false;
  let hoveredRef = "";
  let primaryPath = new Set<string>();
  let activeRelationFamilies = new Set<string>();
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
    if (layoutSettleTimer) window.clearTimeout(layoutSettleTimer);
    layoutSettleTimer = 0;
    layoutSupervisor?.kill();
    layoutSupervisor = null;
    if (visibilityRetryTimer) window.clearTimeout(visibilityRetryTimer);
    visibilityRetryTimer = 0;
    visibilityRetryCount = 0;
    container.dataset.graphPainted = "false";
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
    panel.removeEventListener("boi:knowledge-graph-restore-state", handleRestoreState as EventListener);
    lifecycleObserver.disconnect();
  });
  lifecycleObserver.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("pagehide", () => {
    destroyRenderer(false);
    document.removeEventListener("boi:background-visuals", handleBackgroundVisuals);
    document.removeEventListener("boi:agent-visuals", handleAgentVisuals);
    panel.removeEventListener("boi:knowledge-graph-restore-state", handleRestoreState as EventListener);
    lifecycleObserver.disconnect();
  }, { once: true });
  const details = panel.querySelector<HTMLElement>("[data-knowledge-node-details]");
  const status = panel.querySelector<HTMLElement>(".knowledge-explorer-status");
  const pathSearch = panel.querySelector<HTMLElement>(".knowledge-path-search");

  const showDetails = (nodeRef: string) => {
    if (!graph.hasNode(nodeRef) || !details) return;
    container.dataset.detailsOpenCount = String(Number(container.dataset.detailsOpenCount || "0") + 1);
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
    renderer?.refresh();
    emitState({ selectedNodeId: nodeRef, inspectorOpen: true });
  };

  const closeDetails = () => {
    if (!details) return;
    details.hidden = true;
    panel.classList.remove("knowledge-node-inspector-open");
    renderer?.refresh();
    emitState({ inspectorOpen: false });
    window.requestAnimationFrame(() => renderer?.resize());
  };

  function handleRestoreState(event: Event): void {
    const nextState = ((event as CustomEvent).detail || {}) as ExplorerViewState;
    if (nextState.selectedNodeId && graph.hasNode(nextState.selectedNodeId)) selectedRef = nextState.selectedNodeId;
    if (nextState.camera && renderer) renderer.getCamera().setState(nextState.camera);
    if (nextState.inspectorOpen && graph.hasNode(selectedRef)) showDetails(selectedRef);
    else if (!nextState.inspectorOpen && details && !details.hidden) closeDetails();
  }
  panel.addEventListener("boi:knowledge-graph-restore-state", handleRestoreState as EventListener);

  const renderLegend = (payload: GraphPayload) => {
    const shell = container.closest<HTMLElement>(".knowledge-graph-shell");
    if (!shell) return;
    let legend = shell.querySelector<HTMLElement>(".knowledge-graph-legend");
    if (!legend) {
      legend = document.createElement("div");
      legend.className = "knowledge-graph-legend";
      legend.setAttribute("aria-label", "관계 종류 필터");
      shell.insertBefore(legend, container);
    }
    const families = (payload.legend || []).filter((item) => item.relation_family);
    activeRelationFamilies = new Set(families.map((item) => String(item.relation_family)));
    legend.replaceChildren(...families.map((item) => {
      const family = String(item.relation_family || "other");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "knowledge-graph-legend-item active";
      button.dataset.relationFamily = family;
      button.setAttribute("aria-pressed", "true");
      const swatch = document.createElement("span");
      swatch.className = "knowledge-graph-legend-swatch";
      swatch.style.backgroundColor = relationColors[family] || relationColors.other;
      const label = document.createElement("span");
      label.textContent = (item.labels || [family]).join(" · ");
      button.append(swatch, label);
      button.addEventListener("click", () => {
        if (activeRelationFamilies.has(family)) activeRelationFamilies.delete(family);
        else activeRelationFamilies.add(family);
        const active = activeRelationFamilies.has(family);
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", String(active));
        renderer?.refresh();
      });
      return button;
    }));
    legend.hidden = families.length === 0;
  };

  const runLayout = () => {
    if (layoutSettleTimer) window.clearTimeout(layoutSettleTimer);
    layoutSupervisor?.kill();
    layoutSupervisor = null;
    if (graph.order <= 1) {
      container.dataset.layoutState = "ready";
      return;
    }
    container.dataset.layoutState = "running";
    if (graph.order <= 25) {
      const focal = graph.hasNode(rootRef) ? rootRef : graph.nodes()[0];
      const distance = new Map<string, number>([[focal, 0]]);
      const queue = [focal];
      while (queue.length) {
        const current = queue.shift()!;
        const nextDistance = (distance.get(current) || 0) + 1;
        graph.neighbors(current).forEach((neighbor) => {
          if (distance.has(neighbor)) return;
          distance.set(neighbor, nextDistance);
          queue.push(neighbor);
        });
      }
      const maxDistance = Math.max(1, ...distance.values());
      graph.nodes().forEach((node) => {
        if (!distance.has(node)) distance.set(node, maxDistance + 1);
      });
      const levels = new Map<number, string[]>();
      graph.nodes().forEach((node) => {
        const level = distance.get(node) || 0;
        levels.set(level, [...(levels.get(level) || []), node]);
      });
      const widestLevel = Math.max(...[...levels.values()].map((items) => items.length));
      const levelGap = widestLevel > 8 ? 22 : 18;
      const rowGap = widestLevel > 10 ? 8 : 11;
      levels.forEach((nodesAtLevel, level) => {
        const sorted = [...nodesAtLevel].sort((left, right) => {
          const leftLabel = String(graph.getNodeAttribute(left, "fullLabel") || left);
          const rightLabel = String(graph.getNodeAttribute(right, "fullLabel") || right);
          return leftLabel.localeCompare(rightLabel, "ko");
        });
        sorted.forEach((node, index) => {
          const y = (index - (sorted.length - 1) / 2) * rowGap;
          graph.mergeNodeAttributes(node, {
            x: (level - maxDistance / 2) * levelGap,
            y,
          });
        });
      });
      container.dataset.layoutState = "ready";
      renderer?.refresh();
      return;
    }
    layoutSupervisor = new FA2Layout(graph, {
      settings: {
        ...forceAtlas2.inferSettings(graph),
        adjustSizes: true,
        barnesHutOptimize: graph.order > 80,
        gravity: 1.2,
        scalingRatio: graph.order > 30 ? 8 : 5,
        slowDown: 3,
      },
    });
    layoutSupervisor.start();
    layoutSettleTimer = window.setTimeout(() => {
      layoutSupervisor?.stop();
      layoutSupervisor?.kill();
      layoutSupervisor = null;
      noverlap.assign(graph, {
        maxIterations: 120,
        settings: { margin: 8, ratio: 1.15, speed: 2 },
      });
      container.dataset.layoutState = "ready";
      renderer?.refresh();
    }, graph.order > 100 ? 1600 : 900);
  };

  const replaceGraph = (payload: GraphPayload) => {
    graph.clear();
    const nodes = (payload.nodes || []).slice(0, MAX_NODES);
    primaryPath = new Set(payload.primary_path || []);
    nodes.forEach((node) => {
      const point = seededPosition(node.node_id, node.node_id === rootRef);
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
      const family = String(edge.relation_family || edge.payload?.relation_family || "other");
      const priority = Number(edge.display_priority || edge.payload?.display_priority || 45);
      const sourceIndex = (payload.primary_path || []).indexOf(edge.source_id);
      const targetIndex = (payload.primary_path || []).indexOf(edge.target_id);
      const isPrimary = sourceIndex >= 0 && targetIndex === sourceIndex + 1;
      graph.addDirectedEdgeWithKey(edge.edge_id, edge.source_id, edge.target_id, {
        label: edge.user_label || String(edge.payload?.user_label || edge.relation || "관계"),
        relation: edge.relation || "related", relationFamily: family, displayPriority: priority,
        color: relationColors[family] || relationColors.other, size: isPrimary ? 3 : 1.5,
        type: "arrow", primary: isPrimary,
        reason: String(edge.payload?.reason || edge.payload?.description || edge.user_label || edge.relation || ""),
        provenance: String(edge.payload?.provenance || "근거가 확인된 관계"),
        observedAt: String(edge.payload?.observed_at || edge.payload?.valid_from || edge.payload?.recorded_at || ""),
      });
    });
    renderLegend(payload);
    runLayout();
    renderer?.refresh();
    if (selectedRef && graph.hasNode(selectedRef) && !details?.hidden) showDetails(selectedRef);
  };

  const hasRenderableSize = () => {
    const bounds = container.getBoundingClientRect();
    return container.isConnected && !container.hidden && bounds.width >= 80 && bounds.height >= 80;
  };
  const scheduleRenderer = () => {
    if (renderer || backgroundSuspended || visibilityRetryTimer) return;
    visibilityRetryTimer = window.setTimeout(() => {
      visibilityRetryTimer = 0;
      ensureRenderer();
      if (!renderer && visibilityRetryCount < 120) {
        visibilityRetryCount += 1;
        scheduleRenderer();
      }
    }, visibilityRetryCount ? 50 : 0);
  };
  const ensureRenderer = () => {
    if (!renderer && !backgroundSuspended && hasRenderableSize()) {
      visibilityRetryCount = 0;
      container.dataset.graphPainted = "false";
      renderer = new Sigma(graph, container, {
        edgeProgramClasses: { arrow: EdgeArrowProgram },
        defaultEdgeType: "arrow",
        renderEdgeLabels: true,
        labelDensity: 0.12,
        labelGridCellSize: 120,
        labelRenderedSizeThreshold: 7.5,
        stagePadding: container.clientWidth < 600 ? 36 : graph.order <= 25 ? 120 : 46,
        allowInvalidContainer: true,
        nodeReducer: (node, data) => {
          const neighbors = selectedRef && graph.hasNode(selectedRef) ? new Set(graph.neighbors(selectedRef)) : new Set<string>();
          const emphasized = !selectedRef || node === selectedRef || node === hoveredRef || neighbors.has(node) || primaryPath.has(node);
          return {
            ...data,
            color: emphasized ? data.color : "#cbd5e1",
            forceLabel: graph.order <= 25 || node === rootRef || node === selectedRef || node === hoveredRef || neighbors.has(node) || primaryPath.has(node),
            highlighted: node === selectedRef || node === hoveredRef,
            zIndex: emphasized ? 2 : 0,
          };
        },
        edgeReducer: (edge, data) => {
          const family = String(graph.getEdgeAttribute(edge, "relationFamily") || "other");
          if (activeRelationFamilies.size && !activeRelationFamilies.has(family)) return { ...data, hidden: true };
          const source = graph.source(edge);
          const target = graph.target(edge);
          const incident = !selectedRef || source === selectedRef || target === selectedRef;
          const primary = Boolean(graph.getEdgeAttribute(edge, "primary"));
          const highlighted = primary || incident || source === hoveredRef || target === hoveredRef;
          return {
            ...data,
            color: highlighted ? String(graph.getEdgeAttribute(edge, "color") || data.color) : "#d7dee8",
            size: primary ? 3.2 : highlighted ? 2 : 1,
            forceLabel: primary || (incident && graph.order <= 25),
            zIndex: highlighted ? 2 : 0,
          };
        },
      });
      const restoredCamera = restoredState.camera;
      if (restoredCamera && [restoredCamera.x, restoredCamera.y, restoredCamera.ratio].every((value) => Number.isFinite(Number(value)))) {
        renderer.getCamera().setState({
          x: Number(restoredCamera.x), y: Number(restoredCamera.y), ratio: Number(restoredCamera.ratio),
          angle: Number.isFinite(Number(restoredCamera.angle)) ? Number(restoredCamera.angle) : 0,
        });
      } else if (container.clientWidth < 600 && graph.order <= 25) {
        renderer.getCamera().setState({ ratio: 0.68 });
      }
      renderer.getCamera().on("updated", () => emitState());
      const updateLayoutMetrics = () => {
        if (!renderer) return;
        const points = graph.nodes().map((node) => renderer!.graphToViewport(graph.getNodeAttributes(node)));
        let minimum = Number.POSITIVE_INFINITY;
        points.forEach((point, index) => points.slice(index + 1).forEach((other) => {
          minimum = Math.min(minimum, Math.hypot(point.x - other.x, point.y - other.y));
        }));
        container.dataset.nodeCount = String(points.length);
        container.dataset.minimumNodeDistance = Number.isFinite(minimum) ? String(Math.round(minimum)) : "0";
        if (points.length > 0 && hasRenderableSize()) {
          const firstPaint = container.dataset.graphPainted !== "true";
          container.dataset.graphPainted = "true";
          if (firstPaint) {
            container.dispatchEvent(new CustomEvent("boi:knowledge-graph-painted", {
              bubbles: true,
              detail: { nodeCount: points.length },
            }));
          }
        }
      };
      renderer.on("afterRender", updateLayoutMetrics);
      renderer.on("enterNode", ({ node }) => { hoveredRef = node; renderer?.refresh(); });
      renderer.on("leaveNode", () => { hoveredRef = ""; renderer?.refresh(); });
      renderer.on("clickNode", async ({ node }) => {
        showDetails(node);
        if (activeView !== "explorer" || graph.order >= MAX_NODES) return;
        const payload = await load(panel, "explorer", node);
        const existing = new Set(graph.nodes());
        const combined = {
          nodes: [...graph.nodes().map((id) => ({ node_id: id, node_type: String(graph.getNodeAttribute(id, "kind") || ""), payload: { title: graph.getNodeAttribute(id, "fullLabel") || graph.getNodeAttribute(id, "label"), url: graph.getNodeAttribute(id, "url"), summary: graph.getNodeAttribute(id, "summary") } })), ...(payload.nodes || []).filter((item) => !existing.has(item.node_id))],
          edges: [...graph.edges().map((id) => ({
            edge_id: id, source_id: graph.source(id), target_id: graph.target(id),
            relation: String(graph.getEdgeAttribute(id, "relation") || "related"),
            relation_family: String(graph.getEdgeAttribute(id, "relationFamily") || "other"),
            user_label: String(graph.getEdgeAttribute(id, "label") || "관계"),
            display_priority: Number(graph.getEdgeAttribute(id, "displayPriority") || 45),
            payload: { reason: graph.getEdgeAttribute(id, "reason"), provenance: graph.getEdgeAttribute(id, "provenance"), observed_at: graph.getEdgeAttribute(id, "observedAt") },
          })), ...(payload.edges || [])],
          legend: payload.legend,
          primary_path: payload.primary_path,
        };
        replaceGraph(combined);
        showDetails(node);
      });
      resizeObserver = new ResizeObserver(() => {
        if (!hasRenderableSize()) return;
        if (!renderer) {
          scheduleRenderer();
          return;
        }
        renderer.resize();
        renderer.refresh();
      });
      resizeObserver.observe(container);
      renderer.scheduleRefresh();
      window.requestAnimationFrame(() => {
        if (!renderer || !hasRenderableSize()) return;
        renderer.resize();
        renderer.refresh();
      });
      return;
    }
    if (!renderer && !backgroundSuspended) scheduleRenderer();
  };

  const switchView = async (view: string) => {
    activeView = view;
    panel.dataset.activeView = view;
    const graphVisible = ["explorer", "path", "workflow", "impact", "lineage", "responsibility"].includes(view);
    const graphLayout = panel.querySelector<HTMLElement>(".knowledge-graph-hub-layout, .knowledge-graph-shell");
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
      container.dataset.keyEventCount = String(Number(container.dataset.keyEventCount || "0") + 1);
      container.dataset.lastKey = event.key;
      const nodes = graph.nodes();
      if (!nodes.length) return;
      if (["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(event.key)) {
        event.preventDefault();
        event.stopPropagation();
        const current = graph.hasNode(selectedRef) ? graph.getNodeAttributes(selectedRef) : graph.getNodeAttributes(nodes[0]);
        const vectors: Record<string, [number, number]> = {
          ArrowRight: [1, 0], ArrowLeft: [-1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1],
        };
        const [dx, dy] = vectors[event.key];
        const candidates = nodes
          .filter((node) => node !== selectedRef)
          .map((node) => {
            const point = graph.getNodeAttributes(node);
            const vx = Number(point.x) - Number(current.x);
            const vy = Number(point.y) - Number(current.y);
            const distance = Math.hypot(vx, vy) || 0.001;
            const alignment = (vx * dx + vy * dy) / distance;
            return { node, alignment, score: distance * (2.1 - Math.max(-1, alignment)) };
          })
          .filter((item) => item.alignment > 0.15)
          .sort((left, right) => left.score - right.score);
        const next = candidates[0]?.node || nodes.find((node) => node !== selectedRef) || nodes[0];
        showDetails(next);
      } else if (event.key === "Enter") {
        event.preventDefault();
        event.stopPropagation();
        showDetails(graph.hasNode(selectedRef) ? selectedRef : nodes[0]);
      } else if (event.key === "Escape" && details && !details.hidden) {
        event.preventDefault();
        event.stopPropagation();
        closeDetails();
      }
    });
    container.dataset.keyboardReady = "true";
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
