(function () {
  const relationLabels = {
    has_task: "업무 단계로 포함",
    uses_sop: "업무 절차를 활용",
    uses_action: "실행 요청을 활용",
    uses_event: "업무 이벤트를 활용",
    uses_skill: "업무 방법을 활용",
    requires_evidence: "확인 자료가 필요",
    evidence: "근거로 연결",
    related: "서로 관련",
    links_to: "본문에서 연결",
    broader: "더 넓은 개념",
    narrower: "더 구체적인 개념",
    supersedes: "새 판단으로 대체",
  };

  function buildUrl(panel, params) {
    const url = new URL(panel.dataset.exploreUrl, window.location.origin);
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && String(value)) url.searchParams.set(key, String(value));
    });
    return url.toString();
  }

  async function request(panel, params) {
    const response = await fetch(buildUrl(panel, params), { headers: { Accept: "application/json" } });
    if (!response.ok) {
      let message = "연결 정보를 불러오지 못했습니다.";
      try {
        const payload = await response.json();
        if (typeof payload.detail === "string") message = payload.detail;
      } catch (_error) {
        // The user-facing fallback above is enough when the response is not JSON.
      }
      throw new Error(message);
    }
    return response.json();
  }

  function nodeTitle(node) {
    if (!node || typeof node !== "object") return "연결된 항목";
    const payload = node.payload && typeof node.payload === "object" ? node.payload : {};
    return String(node.title || payload.title || "연결된 항목");
  }

  function nodeUrl(node) {
    if (!node || typeof node !== "object") return "";
    const payload = node.payload && typeof node.payload === "object" ? node.payload : {};
    const value = String(node.url || payload.url || "");
    if (!value) return "";
    const url = new URL(value, window.location.origin);
    const employeeId = new URL(window.location.href).searchParams.get("employee_id");
    if (employeeId && !url.searchParams.has("employee_id")) url.searchParams.set("employee_id", employeeId);
    return url.pathname + url.search + url.hash;
  }

  function nodeRef(node) {
    return String((node && (node.node_id || node.evidence_id || node.record_id)) || "");
  }

  function nodeLink(node) {
    const url = nodeUrl(node);
    const element = document.createElement(url ? "a" : "strong");
    if (url) element.href = url;
    element.textContent = nodeTitle(node);
    return element;
  }

  function relationLabel(edge) {
    const relation = String((edge && (edge.relation || edge.relationship)) || "related");
    return relationLabels[relation] || "업무 맥락으로 연결";
  }

  function emptyMessage(text) {
    const paragraph = document.createElement("p");
    paragraph.className = "empty-state compact";
    paragraph.textContent = text;
    return paragraph;
  }

  function resultList() {
    const list = document.createElement("ol");
    list.className = "knowledge-result-list";
    return list;
  }

  function renderNeighbors(panel, payload, options) {
    const content = panel.querySelector(".knowledge-explorer-content");
    const nodes = Array.isArray(payload.nodes) ? payload.nodes : [];
    const edges = Array.isArray(payload.edges) ? payload.edges : [];
    const lookup = new Map(nodes.map((node) => [nodeRef(node), node]));
    const sourceRef = panel.dataset.sourceRef;
    content.innerHTML = "";
    if (!edges.length) {
      content.appendChild(emptyMessage("직접 연결된 지식을 아직 찾지 못했습니다."));
      content.hidden = false;
      return;
    }
    const list = resultList();
    const seen = new Set();
    edges.forEach((edge) => {
      const source = String(edge.source_id || edge.source || "");
      const target = String(edge.target_id || edge.target || "");
      const otherRef = source === sourceRef ? target : source;
      const node = lookup.get(otherRef);
      if (!node || seen.has(otherRef)) return;
      seen.add(otherRef);
      const item = document.createElement("li");
      const copy = document.createElement("div");
      copy.appendChild(nodeLink(node));
      const relation = document.createElement("span");
      relation.textContent = relationLabel(edge);
      copy.appendChild(relation);
      item.appendChild(copy);
      if (options && options.pathChoices) {
        const pathButton = document.createElement("button");
        pathButton.type = "button";
        pathButton.className = "secondary-button knowledge-path-choice";
        pathButton.dataset.targetRef = otherRef;
        pathButton.textContent = "연결 경로 보기";
        item.appendChild(pathButton);
      }
      list.appendChild(item);
    });
    content.appendChild(list.childElementCount ? list : emptyMessage("직접 연결된 지식을 아직 찾지 못했습니다."));
    content.hidden = false;
  }

  function renderImpact(panel, payload) {
    const content = panel.querySelector(".knowledge-explorer-content");
    const nodes = Array.isArray(payload.nodes) ? payload.nodes : [];
    content.innerHTML = "";
    if (!nodes.length) {
      content.appendChild(emptyMessage("이 지식의 변경으로 직접 영향을 받는 항목을 찾지 못했습니다."));
      content.hidden = false;
      return;
    }
    const list = resultList();
    nodes
      .filter((node) => nodeRef(node) !== panel.dataset.sourceRef)
      .forEach((node) => {
        const item = document.createElement("li");
        item.appendChild(nodeLink(node));
        list.appendChild(item);
      });
    content.appendChild(list.childElementCount ? list : emptyMessage("이 지식의 변경으로 직접 영향을 받는 항목을 찾지 못했습니다."));
    content.hidden = false;
  }

  function renderTour(panel, payload) {
    const content = panel.querySelector(".knowledge-explorer-content");
    const steps = Array.isArray(payload.steps) ? payload.steps : [];
    content.innerHTML = "";
    if (!steps.length) {
      content.appendChild(emptyMessage("이해 순서를 만들 만큼 연결된 지식이 아직 없습니다."));
      content.hidden = false;
      return;
    }
    const list = resultList();
    list.classList.add("knowledge-tour-list");
    steps.forEach((step) => {
      const item = document.createElement("li");
      const order = document.createElement("span");
      order.className = "knowledge-tour-order";
      order.textContent = String(step.order || list.childElementCount + 1);
      item.appendChild(order);
      if (step.node && typeof step.node === "object") item.appendChild(nodeLink(step.node));
      else {
        const title = document.createElement("strong");
        title.textContent = String(step.title || "다음 지식");
        item.appendChild(title);
      }
      list.appendChild(item);
    });
    content.appendChild(list);
    content.hidden = false;
  }

  function renderPath(panel, payload) {
    const content = panel.querySelector(".knowledge-explorer-content");
    const nodes = Array.isArray(payload.nodes) ? payload.nodes : [];
    content.innerHTML = "";
    if (payload.status === "not_connected" || !nodes.length) {
      content.appendChild(emptyMessage("두 항목을 잇는 검증된 경로를 찾지 못했습니다."));
      content.hidden = false;
      return;
    }
    const list = resultList();
    list.classList.add("knowledge-path-list");
    nodes.forEach((node, index) => {
      const item = document.createElement("li");
      item.appendChild(nodeLink(node));
      if (index < nodes.length - 1) {
        const next = document.createElement("span");
        next.className = "knowledge-path-next";
        next.setAttribute("aria-hidden", "true");
        next.textContent = "↓";
        item.appendChild(next);
      }
      list.appendChild(item);
    });
    content.appendChild(list);
    content.hidden = false;
  }

  function setBusy(panel, busy, message) {
    panel.setAttribute("aria-busy", busy ? "true" : "false");
    panel.querySelectorAll("button").forEach((button) => {
      button.disabled = busy;
    });
    const status = panel.querySelector(".knowledge-explorer-status");
    status.textContent = message || "";
  }

  async function loadView(panel, view, targetRef) {
    setBusy(panel, true, "연결된 지식을 확인하고 있습니다.");
    try {
      const payload = await request(panel, {
        view,
        source_ref: panel.dataset.sourceRef,
        target_ref: targetRef || "",
        depth: view === "path" ? 6 : view === "neighbors" ? 1 : 2,
        limit: view === "tour" ? 12 : view === "neighbors" ? 20 : 60,
      });
      if (view === "neighbors") renderNeighbors(panel, payload);
      if (view === "impact") renderImpact(panel, payload);
      if (view === "tour") renderTour(panel, payload);
      if (view === "path") renderPath(panel, payload);
      setBusy(panel, false, "");
    } catch (error) {
      const content = panel.querySelector(".knowledge-explorer-content");
      content.innerHTML = "";
      content.appendChild(emptyMessage(error.message || "연결 정보를 불러오지 못했습니다."));
      content.hidden = false;
      setBusy(panel, false, "");
    }
  }

  async function preparePath(panel) {
    setBusy(panel, true, "바로 이어진 항목을 확인하고 있습니다.");
    try {
      const payload = await request(panel, {
        view: "neighbors",
        source_ref: panel.dataset.sourceRef,
        depth: 1,
        limit: 30,
      });
      renderNeighbors(panel, payload, { pathChoices: true });
      setBusy(panel, false, "이어지는 항목을 선택하거나 이름으로 찾아보세요.");
    } catch (error) {
      setBusy(panel, false, error.message || "연결 정보를 불러오지 못했습니다.");
    }
  }

  function renderSearchCandidates(panel, items) {
    const container = panel.querySelector(".knowledge-path-candidates");
    container.innerHTML = "";
    if (!items.length) {
      container.appendChild(emptyMessage("일치하는 지식을 찾지 못했습니다."));
      return;
    }
    items.slice(0, 8).forEach((item) => {
      if (!item.evidence_id || item.evidence_id === panel.dataset.sourceRef) return;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "knowledge-candidate-button";
      button.dataset.targetRef = item.evidence_id;
      const title = document.createElement("strong");
      title.textContent = item.title || "연결된 지식";
      const summary = document.createElement("span");
      summary.textContent = item.summary || "이 항목까지 이어지는 경로를 확인합니다.";
      button.appendChild(title);
      button.appendChild(summary);
      container.appendChild(button);
    });
  }

  async function searchTargets(panel) {
    const input = panel.querySelector("#knowledge-path-query");
    const query = input.value.trim();
    if (!query) {
      input.focus();
      return;
    }
    setBusy(panel, true, "Wiki 전체에서 항목을 찾고 있습니다.");
    try {
      const payload = await request(panel, { view: "ranked", q: query, limit: 8 });
      renderSearchCandidates(panel, Array.isArray(payload.items) ? payload.items : []);
      setBusy(panel, false, "이어지는 경로를 볼 항목을 선택하세요.");
    } catch (error) {
      setBusy(panel, false, error.message || "항목을 찾지 못했습니다.");
    }
  }

  function selectView(panel, view) {
    panel.querySelectorAll("[data-knowledge-view]").forEach((button) => {
      const active = button.dataset.knowledgeView === view;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
    });
    const pathSearch = panel.querySelector(".knowledge-path-search");
    pathSearch.hidden = view !== "path";
    const graphCanvas = panel.querySelector(".knowledge-graph-shell");
    if (graphCanvas) graphCanvas.hidden = view !== "explorer";
    const content = panel.querySelector(".knowledge-explorer-content");
    if (content) content.hidden = view === "explorer";
    if (view === "explorer") document.dispatchEvent(new CustomEvent("boi:knowledge-graph-open", { detail: { panel } }));
    else if (view === "path") preparePath(panel);
    else loadView(panel, view);
  }

  document.addEventListener("click", function (event) {
    const panel = event.target.closest("#knowledge-explorer");
    if (!panel) return;
    const viewButton = event.target.closest("[data-knowledge-view]");
    if (viewButton) {
      event.preventDefault();
      selectView(panel, viewButton.dataset.knowledgeView);
      return;
    }
    if (event.target.closest("[data-knowledge-search]")) {
      event.preventDefault();
      searchTargets(panel);
      return;
    }
    const choice = event.target.closest("[data-target-ref]");
    if (choice) {
      event.preventDefault();
      loadView(panel, "path", choice.dataset.targetRef);
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Enter" || event.target.id !== "knowledge-path-query") return;
    event.preventDefault();
    const panel = event.target.closest("#knowledge-explorer");
    if (panel) searchTargets(panel);
  });
})();
