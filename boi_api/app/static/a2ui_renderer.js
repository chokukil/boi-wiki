(function () {
  const protocolVersion = "0.9.1";
  const catalogId = "boi-a2ui/v1";
  const components = new Set([
    "Answer", "CitationList", "EvidencePicker", "WorkRecordForm", "DecisionSummary",
    "TaskStatus", "Timeline", "DataTable", "MermaidArtifact", "OntologyExplorer",
    "ActionPreview", "Confirmation", "RelatedQuestions",
  ]);
  const unsafeHtml = /<(?:script|iframe|object|embed)\b|\son[a-z]+\s*=/i;

  function safeValue(value, key = "") {
    if (Array.isArray(value)) return value.every((item) => safeValue(item, key));
    if (value && typeof value === "object") return Object.entries(value).every(([childKey, child]) => safeValue(child, childKey));
    if (typeof value !== "string") return true;
    if (["displayHtml", "html"].includes(key) && unsafeHtml.test(value)) return false;
    if (["url", "href", "downloadUrl"].includes(key) && value && !value.startsWith("/") && !value.startsWith("#")) return false;
    return true;
  }

  function validate(surface) {
    if (!surface || surface.protocol_version !== protocolVersion || surface.catalog_id !== catalogId) return null;
    if (!Array.isArray(surface.components) || (surface.events || []).length) return null;
    const ids = new Set();
    for (const item of surface.components) {
      if (!item?.id || ids.has(item.id) || !components.has(item.component) || !safeValue(item.props || {})) return null;
      ids.add(item.id);
    }
    return surface;
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  }

  function renderWorkRecordForm(mount, props) {
    const fieldsTarget = mount.querySelector(".task-console-dynamic-fields");
    if (!fieldsTarget) return false;
    fieldsTarget.innerHTML = "";
    (props.fields || []).forEach((field) => {
      const label = element("label", "", field.label || field.name);
      let control;
      if (field.control === "textarea") {
        control = element("textarea");
        control.rows = Number(field.rows || 3);
      } else if (field.control === "select") {
        control = element("select");
        (field.options || []).forEach((option) => {
          const item = element("option", "", option.label || option.value);
          item.value = option.value || "";
          control.appendChild(item);
        });
      } else control = element("input");
      control.name = field.name || "";
      control.required = Boolean(field.required);
      if (field.placeholder) control.placeholder = field.placeholder;
      label.appendChild(control);
      fieldsTarget.appendChild(label);
    });
    mount.dataset.a2uiHydrated = "true";
    return true;
  }

  function renderEvidencePicker(mount, props) {
    const sourceLabels = { boi: "BoI 문서", event: "업무 이벤트", action_result: "Action 결과", data_artifact: "데이터", file: "파일", human_note: "담당자 메모", external_ai: "외부 AI 요약" };
    mount.innerHTML = "";
    (props.items || []).forEach((item) => {
      const card = element("section", item.available ? "available" : "");
      card.appendChild(element("span", "", item.status_label || (item.available ? "확보됨" : "확인 필요")));
      card.appendChild(element("h3", "", item.label || "확인 자료"));
      card.appendChild(element("p", "", sourceLabels[item.source_kind] || "업무 근거"));
      mount.appendChild(card);
    });
    if (!mount.childElementCount) mount.appendChild(element("p", "muted", "아직 확인할 자료가 정해지지 않았습니다."));
    mount.dataset.a2uiHydrated = "true";
    return true;
  }

  function renderTaskStatus(mount) {
    mount.dataset.a2uiHydrated = "true";
    return true;
  }

  function renderAnswer(mount, props) {
    mount.innerHTML = "";
    const article = element("article", "a2ui-answer");
    if (props.summary) article.appendChild(element("h3", "", props.summary));
    const body = element("div", "a2ui-answer-body");
    if (props.displayHtml) body.innerHTML = props.displayHtml;
    else body.textContent = props.markdown || "";
    article.appendChild(body);
    mount.appendChild(article);
    return true;
  }

  function renderCitationList(mount, props) {
    mount.innerHTML = "";
    const list = element("ol", "a2ui-citations");
    (props.items || []).forEach((item, index) => {
      const row = element("li");
      const link = element("a", "", item.title || `근거 ${index + 1}`);
      const target = item.target_url || item.resolved_source?.canonical_url || "";
      if (target && target.startsWith("/")) link.href = target;
      else link.setAttribute("aria-disabled", "true");
      row.appendChild(link);
      if (item.heading) row.appendChild(element("span", "", item.heading));
      list.appendChild(row);
    });
    mount.appendChild(list);
    return true;
  }

  function renderRelatedQuestions(mount, props) {
    mount.innerHTML = "";
    const list = element("div", "a2ui-related-questions");
    (props.items || []).slice(0, 3).forEach((item) => {
      const button = element("button", "button secondary", item.label || item.question);
      button.type = "button";
      button.addEventListener("click", () => mount.dispatchEvent(new CustomEvent("boi:a2ui-question", { bubbles: true, detail: item })));
      list.appendChild(button);
    });
    mount.appendChild(list);
    return true;
  }

  function renderDataTable(mount, draft) {
    const nodes = Array.isArray(draft.nodes) ? draft.nodes : [];
    const edges = Array.isArray(draft.edges) ? draft.edges : [];
    const lookup = new Map(nodes.map((item) => [String(item.node_id || ""), item]));
    const nodeTitle = (ref) => lookup.get(String(ref || ""))?.payload?.title || "연결된 항목";
    mount.innerHTML = "";
    const table = element("table", "a2ui-data-table");
    table.innerHTML = "<thead><tr><th>항목</th><th>관계</th><th>연결 항목</th><th>확인 상태</th></tr></thead>";
    const body = element("tbody");
    edges.forEach((edge) => {
      const row = element("tr");
      [nodeTitle(edge.source_id), edge.relation || "연결", nodeTitle(edge.target_id), edge.payload?.provenance || "확인됨"].forEach((value) => row.appendChild(element("td", "", value)));
      body.appendChild(row);
    });
    table.appendChild(body);
    mount.appendChild(table);
    return true;
  }

  function renderTimeline(mount, draft) {
    mount.innerHTML = "";
    const list = element("ol", "a2ui-timeline");
    const nodes = new Map((draft.nodes || []).map((item) => [String(item.node_id || ""), item]));
    (draft.edges || []).forEach((edge) => {
      const row = element("li");
      const at = edge.payload?.observed_at || edge.payload?.valid_from || edge.payload?.recorded_at || "시점 정보 없음";
      row.appendChild(element("time", "", at));
      row.appendChild(element("p", "", `${nodes.get(edge.source_id)?.payload?.title || "업무 항목"} · ${edge.relation || "연결"} · ${nodes.get(edge.target_id)?.payload?.title || "업무 항목"}`));
      list.appendChild(row);
    });
    mount.appendChild(list);
    return true;
  }

  function ontologyPanel(mount, draft) {
    mount.innerHTML = `<article class="knowledge-explorer knowledge-graph-hub" data-source-ref=""><p class="knowledge-explorer-status muted" aria-live="polite">관계 그림을 준비하고 있습니다.</p><div class="knowledge-graph-hub-layout"><div class="knowledge-graph-shell"><div class="knowledge-graph-canvas" role="img" aria-label="업무 맥락 관계 그래프"></div></div><aside class="knowledge-node-details" data-knowledge-node-details><span class="eyebrow">선택한 항목</span><h3 data-knowledge-node-title>업무 관계</h3><p data-knowledge-node-summary>항목을 선택하면 관계 이유와 원문을 확인할 수 있습니다.</p><dl><div><dt>종류</dt><dd data-knowledge-node-kind>업무 지식</dd></div><div><dt>연결</dt><dd data-knowledge-node-degree>확인 중</dd></div><div><dt>검증 상태</dt><dd data-knowledge-node-provenance>근거가 확인된 관계</dd></div></dl><a class="button secondary" data-knowledge-open-node hidden>원문 열기</a></aside></div></article>`;
    const panel = mount.firstElementChild;
    const nodes = Array.isArray(draft.nodes) ? draft.nodes : [];
    panel.dataset.sourceRef = nodes[0]?.node_id || "";
    const payload = { nodes, edges: Array.isArray(draft.edges) ? draft.edges : [] };
    if (window.BoiKnowledgeGraph?.renderPayload) window.BoiKnowledgeGraph.renderPayload(panel, payload);
    else import("/static/dist/knowledge-graph.js")
      .then(() => window.BoiKnowledgeGraph?.renderPayload?.(panel, payload))
      .catch(() => { panel.querySelector(".knowledge-explorer-status").textContent = "관계 그림을 표시하지 못했습니다."; });
    return true;
  }

  function renderMermaid(mount, draft) {
    const source = draft.mermaid || draft.source || "";
    if (!source) return false;
    mount.innerHTML = "";
    const wrapper = element("div", "mermaid-diagram");
    wrapper.dataset.mermaidState = "pending";
    wrapper.appendChild(element("p", "mermaid-status", "흐름 그림을 준비하고 있습니다."));
    const diagram = element("div", "mermaid");
    diagram.textContent = source;
    wrapper.appendChild(diagram);
    mount.appendChild(wrapper);
    mount.dispatchEvent(new CustomEvent("boi:markdown-rendered", { bubbles: true }));
    return true;
  }

  function renderActionPreview(mount, draft) {
    mount.innerHTML = "";
    const article = element("article", "a2ui-action-preview");
    article.appendChild(element("h3", "", draft.title || "Action 실행 전 확인"));
    article.appendChild(element("p", "", draft.preview || draft.draft?.summary || "실행 대상과 결과를 확인해주세요."));
    article.appendChild(element("strong", "", "확인 전에는 실행되지 않습니다."));
    mount.appendChild(article);
    return true;
  }

  function renderDecisionSummary(mount, props) {
    mount.innerHTML = "";
    const article = element("article", "a2ui-decision-summary");
    article.appendChild(element("h3", "", props.summary || "판단 결과"));
    const list = element("ul");
    (props.items || []).forEach((item) => {
      if (!item || typeof item !== "object") {
        list.appendChild(element("li", "", item));
        return;
      }
      const row = element("li", "a2ui-decision-row");
      row.appendChild(element("strong", "", item.label || item.summary || "확인 항목"));
      if (item.value !== undefined && item.value !== null && item.value !== "") {
        const renderedValue = typeof item.value === "string" ? item.value : JSON.stringify(item.value);
        row.appendChild(element("span", "", renderedValue));
      }
      if (item.status) row.appendChild(element("small", "", item.status));
      list.appendChild(row);
    });
    article.appendChild(list);
    mount.appendChild(article);
    return true;
  }

  function renderConfirmation(mount, props) {
    mount.innerHTML = "";
    const article = element("article", "a2ui-confirmation");
    article.appendChild(element("h3", "", props.title || "실행 전 확인"));
    article.appendChild(element("p", "", props.message || "내용을 확인한 뒤 진행해주세요."));
    const button = element("button", "button primary", "확인하고 계속");
    button.type = "button";
    button.addEventListener("click", () => mount.dispatchEvent(new CustomEvent("boi:a2ui-confirm-request", { bubbles: true, detail: { plan_ref: props.plan_ref } })));
    article.appendChild(button);
    mount.appendChild(article);
    return true;
  }

  async function renderArtifactComponent(mount, component, props) {
    const artifactId = props.artifact_id || "";
    if (!artifactId) return false;
    try {
      const response = await fetch(`/api/v2/artifacts/${encodeURIComponent(artifactId)}`, { headers: { Accept: "application/json" } });
      if (!response.ok) return false;
      const artifact = await response.json();
      const draft = artifact.draft || artifact;
      if (component === "DataTable") return renderDataTable(mount, draft);
      if (component === "Timeline") return renderTimeline(mount, draft);
      if (component === "MermaidArtifact") return renderMermaid(mount, draft);
      if (component === "OntologyExplorer") return ontologyPanel(mount, draft);
      if (component === "ActionPreview") return renderActionPreview(mount, artifact);
    } catch (_error) {
      return false;
    }
    return false;
  }

  function hydrate(surface, root = document) {
    const trusted = validate(surface);
    if (!trusted) return false;
    let rendered = 0;
    trusted.components.forEach((item) => {
      const exactMounts = root.querySelectorAll?.(`[data-a2ui-component-id="${item.id}"]`) || [];
      const mounts = exactMounts.length ? exactMounts : (root.querySelectorAll?.(`[data-a2ui-mount="${item.component}"]`) || []);
      mounts.forEach((mount) => {
        const ok = item.component === "WorkRecordForm"
          ? renderWorkRecordForm(mount, item.props || {})
          : item.component === "EvidencePicker"
            ? renderEvidencePicker(mount, item.props || {})
            : item.component === "TaskStatus"
              ? renderTaskStatus(mount, item.props || {})
              : item.component === "Answer"
                ? renderAnswer(mount, item.props || {})
                : item.component === "CitationList"
                  ? renderCitationList(mount, item.props || {})
                  : item.component === "RelatedQuestions"
                    ? renderRelatedQuestions(mount, item.props || {})
                    : item.component === "DecisionSummary"
                      ? renderDecisionSummary(mount, item.props || {})
                      : item.component === "Confirmation"
                        ? renderConfirmation(mount, item.props || {})
                    : ["DataTable", "Timeline", "MermaidArtifact", "OntologyExplorer", "ActionPreview"].includes(item.component)
                      ? (renderArtifactComponent(mount, item.component, item.props || {}), true)
                      : false;
        if (ok) rendered += 1;
      });
    });
    return rendered > 0;
  }

  async function hydrateStored(root) {
    const surfaceRef = root.dataset.a2uiSurfaceRef;
    if (!surfaceRef) return false;
    try {
      const employeeId = new URL(window.location.href).searchParams.get("employee_id") || "100001";
      const response = await fetch(`/api/v2/a2ui-surfaces/${encodeURIComponent(surfaceRef)}?employee_id=${encodeURIComponent(employeeId)}`, { headers: { Accept: "application/json" } });
      if (!response.ok) return false;
      return hydrate(await response.json(), root);
    } catch (_error) {
      return false;
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-a2ui-surface-ref]").forEach((root) => hydrateStored(root));
  });
  window.BoiA2UI = { validate, hydrate, hydrateStored, catalogId, protocolVersion };
})();
