(function () {
  const root = document.querySelector("[data-agent-v2-workspace]");
  if (!root) return;

  const $ = (selector) => root.querySelector(selector);
  const elements = {
    launcher: $(`[data-agent-v2-open]`),
    surface: $(`[data-agent-v2-surface]`),
    title: $("[data-agent-v2-session-title]"),
    saveState: $("[data-agent-v2-save-state]"),
    recent: $("[data-agent-v2-recent-list]"),
    messages: $("[data-agent-v2-messages]"),
    starters: $("[data-agent-v2-starters]"),
    related: $("[data-agent-v2-related]"),
    nextActions: $("[data-agent-v2-next-actions]"),
    form: $("[data-agent-v2-form]"),
    context: $("[data-agent-v2-context]"),
    notice: $("[data-agent-v2-notice]"),
    progress: $("[data-agent-v2-progress]"),
    mobileTabs: $("[data-agent-v2-mobile-tabs]"),
    attachments: $("[data-agent-v2-attachments]"),
    fileInput: $("[data-agent-v2-file]"),
    uploadStatus: $("[data-agent-v2-upload-status]"),
    workbench: $("[data-agent-v2-workbench]"),
    artifacts: $("[data-agent-v2-artifact-list]"),
    artifactKind: $("[data-agent-v2-artifact-kind]"),
    artifactTitle: $("[data-agent-v2-artifact-title]"),
    artifactState: $("[data-agent-v2-artifact-state]"),
    artifactFocus: $("[data-agent-v2-artifact-focus]"),
    fullEditor: $("[data-agent-v2-full-editor]"),
    sources: $("[data-agent-v2-sources]"),
    sourceList: $("[data-agent-v2-source-list]"),
    sourceCount: $("[data-agent-v2-source-count]"),
    sourcePreview: $("[data-agent-v2-source-preview]"),
    sourcePreviewTitle: $("[data-agent-v2-source-preview-title]"),
    sourcePreviewBody: $("[data-agent-v2-source-preview-body]"),
    routinesButton: $("[data-agent-v2-routines-open]"),
    routines: $("[data-agent-v2-routines]"),
    routineList: $("[data-agent-v2-routine-list]"),
    routineCount: $("[data-agent-v2-routine-count]"),
    routineStatusCount: $("[data-agent-v2-routine-status-count]"),
    backdrop: $("[data-agent-v2-task-backdrop]"),
    taskSheet: $("[data-agent-v2-task-sheet]"),
    taskHeading: $("[data-agent-v2-task-heading]"),
    taskList: $("[data-agent-v2-task-list]"),
    taskForm: $("[data-agent-v2-task-form]"),
    completionEditor: $("[data-agent-v2-completion-editor]"),
    taskStatus: $("[data-agent-v2-task-status]"),
    proposal: $("[data-agent-v2-proposal]"),
    proposalDiff: $("[data-agent-v2-proposal-diff]"),
    conflict: $("[data-agent-v2-conflict]"),
  };
  const params = new URLSearchParams(location.search);
  const isFullpage = root.dataset.surfaceKind === "fullpage";
  const state = {
    bootstrap: null,
    mode: isFullpage ? "fullpage" : (params.get("pet") === "expanded" ? "expanded" : ((params.get("pet_session") || sessionStorage.getItem("boiAgentV2WorkSession")) ? "compact" : "closed")),
    session: null,
    sessionId: params.get("session") || params.get("pet_session") || sessionStorage.getItem("boiAgentV2WorkSession") || "",
    busy: false,
    evidence: [],
    citations: [],
    relatedQuestions: [],
    sourceSet: null,
    lastRunId: "",
    workRunId: "",
    workRunState: null,
    contextAnchor: null,
    artifact: null,
    nextActions: [],
    selectedTaskId: "",
    baseTask: null,
    taskDirty: false,
    taskHydrating: false,
    saveTimer: null,
    pendingPatch: null,
    proposal: null,
    conflict: null,
    sourcePreviewReturnToSources: false,
    focusBeforeTask: null,
    routines: [],
    routineHistory: [],
    artifactPanelOpen: false,
    artifactFocusOpen: false,
    diagramViews: {},
    suggestionsExpanded: false,
    starterSet: null,
    starterSetLoading: false,
    starterSetPolls: 0,
    mobileView: "conversation",
  };
  const pageRef = root.dataset.pageRef || `${location.pathname}${location.search}`;
  const channel = "BroadcastChannel" in window ? new BroadcastChannel("boi-agent-v2-artifacts") : null;
  let completionEditor = null;

  function surfaceStateKey() {
    return `boiAgentV2Surface:${state.sessionId || "new"}`;
  }

  function saveSurfaceState() {
    sessionStorage.setItem(surfaceStateKey(), JSON.stringify({
      suggestionsExpanded: state.suggestionsExpanded,
      conversationScroll: Math.round(elements.messages?.scrollTop || 0),
      resultScroll: Math.round(elements.artifacts?.scrollTop || 0),
      artifactFocusOpen: state.artifactFocusOpen,
      diagramViews: state.diagramViews,
    }));
  }

  function restoreSurfaceState() {
    let stored = {};
    try { stored = JSON.parse(sessionStorage.getItem(surfaceStateKey()) || "{}"); } catch (_error) { stored = {}; }
    state.suggestionsExpanded = Boolean(stored.suggestionsExpanded);
    state.artifactFocusOpen = Boolean(stored.artifactFocusOpen);
    state.diagramViews = stored.diagramViews && typeof stored.diagramViews === "object" ? stored.diagramViews : {};
    window.setTimeout(() => {
      if (Number.isFinite(Number(stored.conversationScroll))) elements.messages.scrollTop = Number(stored.conversationScroll);
      if (Number.isFinite(Number(stored.resultScroll))) elements.artifacts.scrollTop = Number(stored.resultScroll);
    }, 0);
  }

  const escapeHtml = (value) => String(value || "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const clone = (value) => JSON.parse(JSON.stringify(value || {}));
  const lines = (value) => String(value || "").split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
  const joinLines = (value) => Array.isArray(value) ? value.join("\n") : String(value || "");
  const canonicalPath = (value) => {
    try { return decodeURIComponent(new URL(String(value || "/"), location.origin).pathname).replace(/\/$/, "") || "/"; }
    catch (_error) { return String(value || "").split("?", 1)[0].replace(/\/$/, "") || "/"; }
  };

  async function api(path, options) {
    const response = await fetch(path, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      ...(options || {}),
    });
    let payload = {};
    try { payload = await response.json(); } catch (_error) { payload = {}; }
    if (!response.ok) {
      const detail = payload.detail || payload;
      const error = new Error(typeof detail === "string" ? detail : detail.message || detail.status || `HTTP ${response.status}`);
      error.status = response.status;
      error.detail = detail;
      throw error;
    }
    return payload;
  }

  async function streamAgentTurn(requestBody, onProgress) {
    const response = await fetch("/api/v2/agent/turns", {
      method: "POST",
      credentials: "same-origin",
      headers: {"Content-Type": "application/json", "Accept": "text/event-stream"},
      body: JSON.stringify(requestBody),
    });
    if (!response.ok || !response.body) {
      let payload = {};
      try { payload = await response.json(); } catch (_error) { payload = {}; }
      const detail = payload.detail || payload;
      throw new Error(typeof detail === "string" ? detail : detail.message || `HTTP ${response.status}`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalPayload = null;
    const consume = (block) => {
      let eventName = "message";
      const dataLines = [];
      block.split(/\r?\n/).forEach((line) => {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
      });
      if (!dataLines.length) return;
      let payload = {};
      try { payload = JSON.parse(dataLines.join("\n")); } catch (_error) { return; }
      if (eventName === "final") finalPayload = payload;
      else if (eventName === "error") throw new Error(payload.message || "요청을 처리하지 못했습니다.");
      else onProgress?.(payload);
    };
    while (true) {
      const {value, done} = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), {stream: !done});
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() || "";
      blocks.forEach(consume);
      if (done) break;
    }
    if (buffer.trim()) consume(buffer);
    if (!finalPayload) throw new Error("최종 답변을 받지 못했습니다.");
    return finalPayload;
  }

  async function searchCompletionSources(query, kinds) {
    const search = new URLSearchParams({q: query, limit: "8"});
    (kinds || []).forEach((kind) => search.append("kinds", kind));
    const payload = await api(`/api/v2/search?${search.toString()}`);
    return payload.items || [];
  }

  completionEditor = window.BoiTaskCompletion?.createEditor(elements.completionEditor, {
    search: searchCompletionSources,
    onChange: () => queueTaskSave(),
    onModeRequest: (mode) => {
      const input = elements.taskForm.querySelector(`[name="execution_mode"][value="${CSS.escape(mode)}"]`);
      if (!input) return;
      input.checked = true;
      completionEditor?.setMode(mode);
      queueTaskSave();
    },
  });

  function setSurfaceMode(mode, persist = true) {
    if (isFullpage) mode = "fullpage";
    state.mode = mode;
    root.dataset.surfaceMode = mode;
    const open = mode !== "closed";
    elements.surface.hidden = !open;
    elements.launcher.hidden = isFullpage || open;
    elements.launcher.setAttribute("aria-expanded", String(open));
    document.body.classList.toggle("agent-surface-overlay-open", mode === "expanded");
    if (mode === "compact" || mode === "closed") {
      state.artifactPanelOpen = false;
      elements.workbench.hidden = true;
      root.classList.remove("artifact-panel-open");
      state.mobileView = "conversation";
      updateMobileView("conversation");
    } else if (state.artifact && state.artifactPanelOpen) {
      elements.workbench.hidden = false;
      root.classList.add("artifact-panel-open");
    }
    if (!isFullpage) sessionStorage.setItem("boiAgentV2SurfaceMode", mode === "expanded" ? "expanded" : "compact");
    const expandButton = $("[data-agent-v2-expand]");
    if (expandButton) {
      expandButton.textContent = mode === "expanded" || mode === "fullpage" ? "↙" : "↗";
      expandButton.title = mode === "expanded" || mode === "fullpage" ? "작게 보기" : "넓게 보기";
      expandButton.setAttribute("aria-label", expandButton.title);
      expandButton.hidden = isFullpage;
    }
    if (open) window.setTimeout(() => elements.form.elements.question.focus(), 0);
    if (elements.starters) {
      renderStarters();
      ensureStarterSet().catch(() => {});
    }
    syncArtifactFocusUi();
    if (persist) saveSurfaceState();
  }

  function updateUrl(artifactId) {
    sessionStorage.setItem("boiAgentV2WorkSession", state.sessionId || "");
    if (!isFullpage) return;
    const url = new URL(location.href);
    if (state.sessionId) url.searchParams.set("session", state.sessionId);
    else url.searchParams.delete("session");
    if (artifactId) url.searchParams.set("artifact", artifactId);
    else url.searchParams.delete("artifact");
    history.replaceState({}, "", url);
  }

  function fullEditorUrl() {
    if (!state.sessionId || !state.artifact) return "";
    let returnUrl = `/agent?session=${encodeURIComponent(state.sessionId)}`;
    if (!isFullpage) {
      const target = new URL(location.href);
      target.searchParams.set("pet_session", state.sessionId);
      target.searchParams.set("pet", "expanded");
      returnUrl = `${target.pathname}${target.search}`;
    }
    return `/sops/new?work_session_id=${encodeURIComponent(state.sessionId)}&artifact_id=${encodeURIComponent(state.artifact.artifact_id)}&return_to=${encodeURIComponent(returnUrl)}`;
  }

  function isMobileSurface() {
    return window.matchMedia("(max-width: 760px)").matches;
  }

  function artifactHasDiagram() {
    const draft = state.artifact?.draft || {};
    return Boolean(state.artifact && (state.artifact.artifact_type === "mermaid_diagram" || draft.mermaid));
  }

  function syncArtifactFocusUi() {
    const focusAvailable = Boolean(
      artifactHasDiagram()
      && state.artifactPanelOpen
      && (state.mode === "expanded" || state.mode === "fullpage")
      && !isMobileSurface()
    );
    const focusActive = focusAvailable && state.artifactFocusOpen;
    root.classList.toggle("artifact-focus-open", focusActive);
    elements.artifactFocus.hidden = !focusAvailable;
    elements.artifactFocus.textContent = focusActive ? "↙" : "⛶";
    elements.artifactFocus.title = focusActive ? "대화와 함께 보기" : "결과 크게 보기";
    elements.artifactFocus.setAttribute("aria-label", elements.artifactFocus.title);
    elements.artifactFocus.setAttribute("aria-pressed", String(focusActive));
  }

  function setArtifactFocus(open) {
    const centers = new Map(
      [...elements.artifacts.querySelectorAll("[data-v2-mermaid]")]
        .map((diagram) => [diagram.dataset.mermaidViewKey, mermaidCanvasCenter(diagram)])
    );
    state.artifactFocusOpen = Boolean(open && !isMobileSurface());
    syncArtifactFocusUi();
    window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
      elements.artifacts.querySelectorAll("[data-v2-mermaid]").forEach((diagram) => {
        syncMermaidView(diagram, { center: centers.get(diagram.dataset.mermaidViewKey) });
      });
    }));
    saveSurfaceState();
  }

  function renderMarkdown(value, artifactId) {
    const mermaidBlocks = [];
    let source = String(value || "").replace(/```mermaid\s*([\s\S]*?)```/gi, (_all, diagram) => {
      const index = mermaidBlocks.push(diagram.trim()) - 1;
      return `@@MERMAID_${index}@@`;
    });
    source = escapeHtml(source);
    source = source.replace(/```json\s*([\s\S]*?)```/gi, "<details class=\"agent-v2-raw-draft\"><summary>초안 세부 내용</summary><pre><code>$1</code></pre></details>");
    source = source.replace(/^### (.+)$/gm, "<h4>$1</h4>").replace(/^## (.+)$/gm, "<h3>$1</h3>");
    source = source.replace(/\[([^\]]+)\]\((\/[^)]+)\)/g, '<a href="$2">$1</a>');
    source = source.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    source = source.replace(/^- (.+)$/gm, "<li>$1</li>").replace(/((?:<li>.*<\/li>\n?)+)/g, "<ul>$1</ul>");
    source = source.replace(/\n{2,}/g, "</p><p>").replace(/\n/g, "<br>");
    mermaidBlocks.forEach((diagram, index) => {
      source = source.replace(`@@MERMAID_${index}@@`, mermaidViewer(diagram, "업무 흐름", artifactId));
    });
    return `<p>${source}</p>`;
  }

  function mermaidViewer(rawSource, title, artifactId, artifactType, artifactActions) {
    const safe = escapeHtml(rawSource);
    let hash = 2166136261;
    for (const character of String(rawSource || "")) {
      hash ^= character.charCodeAt(0);
      hash = Math.imul(hash, 16777619);
    }
    const viewKey = `${artifactId || state.artifact?.artifact_id || "inline"}:${(hash >>> 0).toString(36)}`;
    let actions = "";
    if (artifactId && artifactType === "mermaid_diagram") {
      const allowed = (artifactActions || []).filter((item) => item?.state !== "unavailable" && ["split_tasks", "create_sop_draft"].includes(item?.action_id));
      if (allowed.length) {
        actions = `<div class="mermaid-v2-actions">${allowed.map((item) => `<button type="button" data-v2-mermaid-action="${escapeHtml(item.action_id)}">${escapeHtml(item.label)}</button>`).join("")}</div>`;
      }
    } else if (artifactId) {
      actions = `<div class="mermaid-v2-actions"><button type="button" data-agent-v2-result-action="tasks">Task 다듬기</button><button type="button" data-agent-v2-result-action="full">전체 SOP 편집</button></div>`;
    }
    return `<div class="mermaid-diagram" data-v2-mermaid data-mermaid-state="pending" data-mermaid-title="${escapeHtml(title)}" data-mermaid-source="${safe}" data-mermaid-view-key="${escapeHtml(viewKey)}" data-agent-artifact-id="${escapeHtml(artifactId || "")}"><div class="mermaid-v2-toolbar"><span class="mermaid-status sr-only">흐름 그림 준비 중</span><div class="mermaid-v2-view-modes" role="group" aria-label="흐름 그림 보기 방식"><button type="button" data-mermaid-view="read" aria-pressed="true">읽기 크기</button><button type="button" data-mermaid-view="fit" aria-pressed="false">전체 보기</button></div><div class="mermaid-v2-zoom-controls" role="group" aria-label="흐름 그림 확대 축소"><button type="button" data-mermaid-view="out" title="축소" aria-label="흐름 그림 축소">−</button><output data-mermaid-zoom aria-live="polite">100%</output><button type="button" data-mermaid-view="in" title="확대" aria-label="흐름 그림 확대">＋</button></div></div><div class="mermaid-v2-canvas" tabindex="0" aria-label="${escapeHtml(title)} 흐름 그림. 방향키로 이동할 수 있습니다."><div class="mermaid">${safe}</div></div>${actions}<details class="mermaid-source-fallback"><summary>원문 보기</summary><pre>${safe}</pre></details></div>`;
  }

  const MERMAID_MIN_ZOOM = .6;
  const MERMAID_MAX_ZOOM = 5;

  function clampMermaidZoom(value) {
    const clamped = Math.max(MERMAID_MIN_ZOOM, Math.min(MERMAID_MAX_ZOOM, Number(value) || 1));
    return Math.round(clamped * 100) / 100;
  }

  function mermaidCanvasCenter(diagram) {
    const canvas = diagram?.querySelector(".mermaid-v2-canvas");
    if (!canvas) return null;
    return {
      x: canvas.scrollWidth > 0 ? (canvas.scrollLeft + canvas.clientWidth / 2) / canvas.scrollWidth : .5,
      y: canvas.scrollHeight > 0 ? (canvas.scrollTop + canvas.clientHeight / 2) / canvas.scrollHeight : .5,
    };
  }

  function restoreMermaidCanvasCenter(canvas, center) {
    if (!canvas || !center) return;
    canvas.scrollLeft = Math.max(0, center.x * canvas.scrollWidth - canvas.clientWidth / 2);
    canvas.scrollTop = Math.max(0, center.y * canvas.scrollHeight - canvas.clientHeight / 2);
  }

  function renderedLabelHeights(svg, selector) {
    const heights = [];
    svg.querySelectorAll(selector).forEach((label) => {
      const lines = label.querySelectorAll("tspan");
      const targets = lines.length ? lines : [label];
      targets.forEach((target) => {
        const height = target.getBoundingClientRect().height;
        if (height > 1) heights.push(height);
      });
    });
    return heights;
  }

  function readableMermaidZoom(svg) {
    svg.style.width = "100%";
    svg.style.maxWidth = "100%";
    const nodeHeights = renderedLabelHeights(svg, "g.node text, .nodeLabel text");
    const edgeHeights = renderedLabelHeights(svg, "g.edgeLabel text, .edgeLabel text");
    const smallestNode = nodeHeights.length ? Math.min(...nodeHeights) : 0;
    const smallestEdge = edgeHeights.length ? Math.min(...edgeHeights) : 0;
    const nodeScale = smallestNode ? 14 / smallestNode : 1;
    const edgeScale = smallestEdge ? 12 / smallestEdge : 1;
    return clampMermaidZoom(Math.ceil(Math.max(1, nodeScale, edgeScale) * 10) / 10);
  }

  function mermaidLabelMinimums(svg) {
    const nodeHeights = renderedLabelHeights(svg, "g.node text, .nodeLabel text");
    const edgeHeights = renderedLabelHeights(svg, "g.edgeLabel text, .edgeLabel text");
    return {
      node: nodeHeights.length ? Math.min(...nodeHeights) : 0,
      edge: edgeHeights.length ? Math.min(...edgeHeights) : 0,
    };
  }

  function updateMermaidToolbar(diagram, mode, zoom) {
    diagram.dataset.viewMode = mode;
    diagram.dataset.zoom = String(zoom);
    diagram.querySelectorAll("[data-mermaid-view='read'], [data-mermaid-view='fit']").forEach((button) => {
      const active = button.dataset.mermaidView === mode;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    const output = diagram.querySelector("[data-mermaid-zoom]");
    if (output) output.textContent = `${Math.round(zoom * 100)}%`;
    const out = diagram.querySelector("[data-mermaid-view='out']");
    const zoomIn = diagram.querySelector("[data-mermaid-view='in']");
    if (out) out.disabled = zoom <= MERMAID_MIN_ZOOM;
    if (zoomIn) zoomIn.disabled = zoom >= MERMAID_MAX_ZOOM;
  }

  function rememberMermaidView(diagram) {
    const canvas = diagram?.querySelector(".mermaid-v2-canvas");
    const key = diagram?.dataset.mermaidViewKey;
    if (!canvas || !key) return;
    state.diagramViews[key] = {
      mode: diagram.dataset.viewMode || "read",
      zoom: Number(diagram.dataset.zoom || 1),
      scrollLeft: Math.round(canvas.scrollLeft),
      scrollTop: Math.round(canvas.scrollTop),
    };
    saveSurfaceState();
  }

  function bindMermaidCanvas(diagram) {
    const canvas = diagram.querySelector(".mermaid-v2-canvas");
    if (!canvas || canvas.dataset.viewStateBound === "true") return;
    canvas.dataset.viewStateBound = "true";
    let saveTimer = 0;
    canvas.addEventListener("scroll", () => {
      window.clearTimeout(saveTimer);
      saveTimer = window.setTimeout(() => rememberMermaidView(diagram), 120);
    }, { passive: true });
  }

  function syncMermaidView(diagram, options = {}) {
    if (!diagram || diagram.dataset.mermaidState !== "rendered") return;
    const canvas = diagram.querySelector(".mermaid-v2-canvas");
    const svg = canvas?.querySelector("svg");
    const key = diagram.dataset.mermaidViewKey;
    if (!canvas || !svg || !key || canvas.clientWidth <= 0) return;
    bindMermaidCanvas(diagram);
    const stored = state.diagramViews[key] || { mode: "read", zoom: 1, scrollLeft: 0, scrollTop: 0 };
    const mode = ["read", "fit", "custom"].includes(stored.mode) ? stored.mode : "read";
    const center = options.center || (diagram.dataset.viewApplied === "true" ? mermaidCanvasCenter(diagram) : null);
    let zoom = mode === "read" ? readableMermaidZoom(svg) : mode === "fit" ? 1 : clampMermaidZoom(stored.zoom);
    const applyZoom = () => {
      svg.style.width = `${Math.round(zoom * 100)}%`;
      svg.style.maxWidth = zoom > 1 ? "none" : "100%";
      updateMermaidToolbar(diagram, mode, zoom);
      state.diagramViews[key] = { ...stored, mode, zoom };
    };
    applyZoom();
    diagram.dataset.viewApplied = "true";
    window.requestAnimationFrame(() => {
      if (mode === "read") {
        const minimums = mermaidLabelMinimums(svg);
        const correction = Math.max(minimums.node ? 14 / minimums.node : 1, minimums.edge ? 12 / minimums.edge : 1);
        if (correction > 1.02 && zoom < MERMAID_MAX_ZOOM) {
          zoom = clampMermaidZoom(Math.ceil(zoom * correction * 10) / 10);
          applyZoom();
        }
      }
      window.requestAnimationFrame(() => {
        if (center) restoreMermaidCanvasCenter(canvas, center);
        else {
          canvas.scrollLeft = Number(stored.scrollLeft || 0);
          canvas.scrollTop = Number(stored.scrollTop || 0);
        }
        canvas.dataset.panReady = String(canvas.scrollWidth > canvas.clientWidth + 2 || canvas.scrollHeight > canvas.clientHeight + 2);
        rememberMermaidView(diagram);
      });
    });
  }

  function setMermaidView(diagram, mode, zoom) {
    const key = diagram?.dataset.mermaidViewKey;
    if (!diagram || !key) return;
    const center = mermaidCanvasCenter(diagram);
    const current = state.diagramViews[key] || { mode: "read", zoom: 1 };
    state.diagramViews[key] = { ...current, mode, zoom: clampMermaidZoom(zoom ?? current.zoom) };
    syncMermaidView(diagram, { center });
  }

  function syncResponsiveMermaidScale(diagram) {
    syncMermaidView(diagram);
  }

  function syncResponsiveMermaidScales() {
    elements.artifacts.querySelectorAll("[data-v2-mermaid]").forEach(syncResponsiveMermaidScale);
  }

  function clearEmpty() {
    elements.messages.querySelector(".agent-v2-empty")?.remove();
  }

  function scrollStorageKey() {
    return state.sessionId ? `boiAgentV2Scroll:${state.sessionId}` : "";
  }

  function restoreMessageScroll() {
    const key = scrollStorageKey();
    const stored = key ? Number(sessionStorage.getItem(key)) : Number.NaN;
    window.setTimeout(() => {
      elements.messages.scrollTop = Number.isFinite(stored) ? stored : elements.messages.scrollHeight;
    }, 0);
  }

  function addMessage(role, content, metadata) {
    clearEmpty();
    const article = document.createElement("article");
    article.className = `agent-v2-message ${role}`;
    if (role === "assistant") article.innerHTML = metadata?.displayHtml || renderMarkdown(content, metadata?.artifactId || "");
    else article.textContent = content;
    if (metadata?.label) {
      const tag = document.createElement("small");
      tag.textContent = metadata.label;
      article.prepend(tag);
    }
    if (role === "assistant" && metadata?.artifactId) {
      const artifactButton = document.createElement("button");
      artifactButton.type = "button";
      artifactButton.className = "agent-v2-message-artifact";
      artifactButton.dataset.messageArtifact = metadata.artifactId;
      artifactButton.textContent = "결과 보기";
      article.appendChild(artifactButton);
    }
    elements.messages.appendChild(article);
    elements.messages.scrollTop = elements.messages.scrollHeight;
    document.dispatchEvent(new CustomEvent("boi:markdown-rendered", { bubbles: true }));
  }

  function renderTimeline(items) {
    elements.messages.innerHTML = "";
    (items || []).forEach((item) => {
      const artifactId = item.artifact_refs?.[0]?.artifact_id || "";
      addMessage(item.role, item.display_text, { artifactId, displayHtml: item.display_html || "", label: item.role === "assistant" ? "BoI Agent" : "" });
      if (item.role === "assistant") {
        if (item.evidence_refs?.length) state.evidence = item.evidence_refs;
        if (item.next_actions?.length) state.nextActions = item.next_actions;
        if (item.citations?.length) state.citations = item.citations;
        if (item.related_questions?.length) state.relatedQuestions = item.related_questions;
        if (item.run_id) state.lastRunId = item.run_id;
        if (item.work_run_id) state.workRunId = item.work_run_id;
        if (item.loop_state) state.workRunState = item.loop_state;
        if (item.knowledge_candidates?.length) appendLearningSummary(item.knowledge_candidates);
        renderWorkState(item.loop_state, item.harness_results);
      }
    });
    if (!items?.length) renderEmpty();
    else restoreMessageScroll();
  }

  function renderEmpty() {
    elements.messages.innerHTML = '<div class="agent-v2-empty"><strong>BoI Agent와 무엇을 해볼까요?</strong><div class="agent-v2-starters" data-agent-v2-starters></div></div>';
    elements.starters = $("[data-agent-v2-starters]");
    renderStarters();
  }

  function renderStarters() {
    if (!elements.starters) return;
    elements.starters.innerHTML = "";
    const starters = state.starterSet?.items || state.bootstrap?.starters || [];
    const showAll = state.suggestionsExpanded || state.mode === "expanded" || state.mode === "fullpage";
    const areaLabels = {
      current_work: "지금 할 일",
      knowledge: "지식·연결 관계·유사 사례",
      workflow: "SOP·Workflow·Task",
      event_action: "업무 이벤트·Action",
      learning: "결과 기록·지식 자산화",
      automation: "자동 확인·업무 개선",
    };
    const makeButton = (starter) => {
      const button = document.createElement("button");
      button.type = "button";
      button.innerHTML = `<strong>${escapeHtml(starter.label || starter.prompt)}</strong>${starter.reason ? `<span>${escapeHtml(starter.reason)}</span>` : ""}`;
      button.setAttribute("aria-label", starter.label || starter.prompt);
      button.addEventListener("click", () => {
        submitQuestion(starter.prompt, { suggestionId: starter.suggestion_id, suggestionSetId: state.starterSet?.set_id || "" }).catch(showError);
      });
      return button;
    };
    if (showAll) {
      Object.entries(areaLabels).forEach(([area, label]) => {
        const areaItems = starters.filter((item) => (item.area || "knowledge") === area).slice(0, 3);
        if (!areaItems.length) return;
        const section = document.createElement("section");
        section.className = "agent-v2-starter-area";
        section.innerHTML = `<h4>${escapeHtml(label)}</h4>`;
        section.appendChild(makeButton(areaItems[0]));
        if (areaItems.length > 1) {
          const details = document.createElement("details");
          details.innerHTML = `<summary>이 영역 제안 더보기</summary><div></div>`;
          areaItems.slice(1).forEach((item) => details.querySelector("div").appendChild(makeButton(item)));
          section.appendChild(details);
        }
        elements.starters.appendChild(section);
      });
      return;
    }
    const featured = starters.filter((item) => item.featured).slice(0, 4);
    (featured.length ? featured : starters.slice(0, 4)).forEach((starter) => elements.starters.appendChild(makeButton(starter)));
    if (starters.length > 4) {
      const more = document.createElement("button");
      more.type = "button";
      more.className = "agent-v2-starters-more";
      more.innerHTML = `<strong>다른 제안 보기</strong><span>${starters.length - 4}개 더 보기</span>`;
      more.addEventListener("click", () => {
        state.suggestionsExpanded = true;
        saveSurfaceState();
        renderStarters();
      });
      elements.starters.appendChild(more);
    }
  }

  async function pollStarterSet() {
    if (!state.starterSet?.set_id || state.starterSet.state !== "updating" || state.starterSetPolls >= 2) return;
    state.starterSetPolls += 1;
    window.setTimeout(async () => {
      try {
        state.starterSet = await api(`/api/v2/starter-suggestion-sets/${encodeURIComponent(state.starterSet.set_id)}`);
        if (elements.starters && !elements.form.elements.question.value.trim()) renderStarters();
        if (state.starterSet.state === "updating") pollStarterSet();
      } catch (_error) { /* Grounded immediate suggestions remain usable. */ }
    }, state.starterSetPolls === 1 ? 1000 : 2200);
  }

  async function ensureStarterSet() {
    if (state.starterSet || state.starterSetLoading || !elements.starters || state.mode === "closed") return;
    state.starterSetLoading = true;
    try {
      state.starterSet = await api("/api/v2/starter-suggestion-sets", {
        method: "POST",
        body: JSON.stringify({page_ref: pageRef, work_session_id: state.sessionId || ""}),
      });
      renderStarters();
      pollStarterSet();
    } finally {
      state.starterSetLoading = false;
    }
  }

  function renderNotice() {
    elements.notice.hidden = true;
    elements.notice.textContent = "";
  }

  function renderContext() {
    const groups = state.sourceSet?.groups || {};
    const excluded = new Set(state.sourceSet?.excluded || []);
    const currentSource = ["pinned", "used", "related"].flatMap((name) => groups[name] || [])
      .find((item) => item.url && canonicalPath(pageRef) === canonicalPath(item.url));
    const anchor = state.contextAnchor || state.bootstrap?.page?.context || null;
    const current = currentSource || (anchor?.resolved ? {
      source_ref: anchor.ref,
      title: anchor.title,
      url: anchor.url,
    } : null);
    if (current?.source_ref && excluded.has(current.source_ref)) {
      elements.context.hidden = true;
      elements.context.innerHTML = "";
      return;
    }
    elements.context.hidden = !current;
    elements.context.innerHTML = current
      ? `<span>현재 업무 맥락</span><strong>${escapeHtml(current.title)}</strong><button type="button" data-source-exclude="${escapeHtml(current.source_ref)}" title="현재 맥락 제외" aria-label="현재 맥락 제외">×</button>`
      : "";
  }

  function renderWorkState(loopState, harnessResults) {
    const stateValue = loopState?.status || "";
    const blocker = (harnessResults || []).flatMap((item) => item.blockers || [])[0] || "";
    const labels = {
      blocked: blocker ? `보완 필요 · ${blocker}` : "보완이 필요한 항목이 있습니다.",
      waiting_human: "담당자 확인을 기다리고 있습니다.",
      waiting_review: "초안을 확인하면 다음 단계로 이어집니다.",
      waiting_signal: "연결된 시스템의 확인 결과를 기다리고 있습니다.",
      queued: "관련 근거를 확인하며 심층 작업을 진행하고 있습니다.",
      in_progress: "새 근거를 반영해 업무를 이어가고 있습니다.",
      stopped: "같은 작업이 반복되어 멈췄습니다. 다른 근거나 담당자 확인이 필요합니다.",
    };
    if (!labels[stateValue]) return;
    elements.progress.hidden = false;
    elements.progress.textContent = labels[stateValue];
  }

  function appendLearningSummary(candidates) {
    (candidates || []).slice(0, 1).forEach((item) => {
      if (elements.messages.querySelector(`[data-knowledge-candidate="${CSS.escape(item.candidate_id)}"]`)) return;
      const section = document.createElement("aside");
      section.className = "agent-v2-learning-summary";
      section.dataset.knowledgeCandidate = item.candidate_id;
      section.innerHTML = `<span>이번 업무에서 남길 내용</span><strong>${escapeHtml(item.title)}</strong><a href="${escapeHtml(item.url)}">확인하기</a>`;
      elements.messages.appendChild(section);
    });
  }

  function renderSources() {
    const groups = state.sourceSet?.groups || {};
    const seen = new Set();
    const rows = [];
    ["pinned", "used", "attached", "related"].forEach((group) => {
      (groups[group] || []).forEach((item) => {
        if (!item.source_ref || seen.has(item.source_ref)) return;
        seen.add(item.source_ref);
        rows.push({...item, group});
      });
    });
    elements.sourceCount.textContent = `${rows.length}개`;
    elements.sourceList.innerHTML = rows.length ? rows.map((item) => `
      <article data-source-ref="${escapeHtml(item.source_ref)}">
        <div><span>${escapeHtml(item.kind)}</span><strong>${escapeHtml(item.title)}</strong></div>
        <p>${escapeHtml(item.summary || "")}</p>
        <small>${item.group === "pinned" ? "이 작업에 고정" : item.group === "attached" ? "직접 연결" : item.group === "related" ? "관련 있지만 미사용" : "이번 답변에 사용"}</small>
        <div>
          ${item.url ? `<a href="${escapeHtml(item.url)}">원문</a>` : ""}
          <button type="button" ${item.group === "pinned" ? "data-source-unpin" : "data-source-pin"}="${escapeHtml(item.source_ref)}" title="${item.group === "pinned" ? "고정 해제" : "이 작업에 고정"}">${item.group === "pinned" ? "고정 해제" : "고정"}</button>
          <button type="button" data-source-exclude="${escapeHtml(item.source_ref)}" title="이 작업에서 제외">제외</button>
        </div>
      </article>`).join("") : "<p>아직 사용한 지식이 없습니다.</p>";
    renderContext();
  }

  function displayDate(value) {
    if (!value) return "";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value).slice(0, 16).replace("T", " ");
    return new Intl.DateTimeFormat("ko-KR", {month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"}).format(parsed);
  }

  function renderRoutines() {
    const items = state.routines || [];
    const history = state.routineHistory || [];
    const activeCount = items.filter((item) => item.status === "active").length;
    const failedCount = items.filter((item) => item.status === "failed").length;
    elements.routinesButton.hidden = items.length === 0;
    elements.routineStatusCount.textContent = `${items.length}건`;
    elements.routineCount.textContent = failedCount ? `확인 필요 ${failedCount}건` : `진행 중 ${activeCount}건`;
    const stopLabel = (item) => ({
      cancelled: "직접 멈출 때까지",
      max_runs: `${item.loop_policy?.max_runs || item.max_runs || 0}회 확인 후`,
      event_resolved: "연결된 상태가 해소될 때",
    }[item.loop_policy?.routine_stop || "cancelled"] || "직접 멈출 때까지");
    const cards = items.map((item) => {
      const active = item.status === "active";
      const status = active ? "진행 중" : "확인 필요";
      const next = active && item.next_run_at ? displayDate(item.next_run_at) : (item.event_ref ? "업무 이벤트 발생 시" : "조건 확인 필요");
      const last = item.last_result_summary || (item.last_status ? `최근 결과 ${item.last_status}` : "아직 실행 결과가 없습니다.");
      return `<article data-routine-id="${escapeHtml(item.routine_id)}"><header><div><strong>${escapeHtml(item.title || "자동 확인")}</strong><span>${escapeHtml(status)}</span></div>${active ? `<button type="button" class="icon-button" data-routine-cancel="${escapeHtml(item.routine_id)}" title="자동 확인 멈추기" aria-label="${escapeHtml(item.title || "자동 확인")} 멈추기">■</button>` : ""}</header><dl><div><dt>목적</dt><dd>${escapeHtml(item.goal || "")}</dd></div><div><dt>다음 확인</dt><dd>${escapeHtml(next)}</dd></div><div><dt>최근 결과</dt><dd>${escapeHtml(last)}</dd></div><div><dt>끝내는 기준</dt><dd>${escapeHtml(stopLabel(item))}</dd></div></dl></article>`;
    }).join("");
    const historyMarkup = history.length ? `<details class="agent-surface-routine-history"><summary>지난 자동 확인 ${history.length}건</summary>${history.map((item) => `<article><strong>${escapeHtml(item.title || "자동 확인")}</strong><span>${item.status === "completed" ? "완료" : "멈춤"}</span></article>`).join("")}</details>` : "";
    elements.routineList.innerHTML = cards || "<p>현재 진행 중이거나 확인이 필요한 자동 확인이 없습니다.</p>";
    elements.routineList.insertAdjacentHTML("beforeend", historyMarkup);
  }

  async function loadRoutines() {
    const [actionable, history] = await Promise.all([
      api("/api/v2/work-routines?limit=30&surface=pet&status=actionable"),
      api("/api/v2/work-routines?limit=20&surface=pet&status=completed,cancelled"),
    ]);
    state.routines = actionable.items || [];
    state.routineHistory = history.items || [];
    renderRoutines();
  }

  async function openRoutines() {
    await loadRoutines();
    elements.sources.hidden = true;
    elements.sourcePreview.hidden = true;
    elements.routines.hidden = false;
  }

  function updateMobileView(view) {
    state.mobileView = view;
    elements.mobileTabs.querySelectorAll("[data-agent-v2-mobile-view]").forEach((button) => {
      button.classList.toggle("active", button.dataset.agentV2MobileView === view);
      if (button.dataset.agentV2MobileView === "result") button.disabled = !state.artifact;
    });
  }

  function renderRelated() {
    elements.related.innerHTML = "";
    state.relatedQuestions.slice(0, 3).forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.relatedQuestion = item.question || "";
      button.innerHTML = `<span>${escapeHtml(item.kind === "understand" ? "더 이해하기" : item.kind === "connect" ? "연결 관계 확인" : "업무 적용")}</span><strong>${escapeHtml(item.label || item.question)}</strong>`;
      elements.related.appendChild(button);
    });
    elements.related.hidden = !state.relatedQuestions.length;
  }

  function renderProgress(progress) {
    const active = (progress || []).filter((item) => !["completed", "failed"].includes(item.status));
    elements.progress.hidden = !active.length;
    elements.progress.textContent = active.length
      ? active.map((item) => item.label).filter(Boolean).join(" · ")
      : "";
  }

  async function loadSources() {
    if (!state.sessionId) return;
    state.sourceSet = await api(`/api/v2/work-sessions/${encodeURIComponent(state.sessionId)}/sources`);
    renderSources();
    renderNextActions();
  }

  async function patchSources(values, retried) {
    if (!state.sessionId) return;
    if (!state.sourceSet) await loadSources();
    try {
      state.sourceSet = await api(`/api/v2/work-sessions/${encodeURIComponent(state.sessionId)}/sources`, {
        method: "PATCH",
        body: JSON.stringify({ expected_revision: state.sourceSet.revision, ...values }),
      });
      renderSources();
    } catch (error) {
      if (error.status === 409 && !retried) {
        state.sourceSet = error.detail?.source_set || null;
        return patchSources(values, true);
      }
      throw error;
    }
  }

  function openSources() {
    if (!state.sessionId) return;
    elements.sourcePreview.hidden = true;
    elements.sources.hidden = false;
    updateMobileView("sources");
    loadSources().catch(showError);
  }

  async function openCitation(citationId) {
    if (!citationId) return;
    state.sourcePreviewReturnToSources = !elements.sources.hidden;
    const citation = await api(`/api/v2/citations/${encodeURIComponent(citationId)}`);
    elements.sourcePreviewTitle.textContent = citation.title || "원문 근거";
    elements.sourcePreviewBody.innerHTML = `
      <div class="agent-surface-citation-meta">
        ${citation.heading ? `<strong>${escapeHtml(citation.heading)}</strong>` : ""}
        ${citation.start_line ? `<span>${citation.start_line}${citation.end_line && citation.end_line !== citation.start_line ? `-${citation.end_line}` : ""}행</span>` : ""}
      </div>
      <blockquote>${escapeHtml(citation.excerpt || "원문 일부를 불러오지 못했습니다.")}</blockquote>
      ${citation.target_url ? `<a class="secondary-button" href="${escapeHtml(citation.target_url)}">원문 열기</a>` : ""}`;
    elements.sources.hidden = true;
    elements.sourcePreview.hidden = false;
    updateMobileView("sources");
  }

  function closeSourcePreview() {
    elements.sourcePreview.hidden = true;
    elements.sources.hidden = !state.sourcePreviewReturnToSources;
    updateMobileView(state.sourcePreviewReturnToSources ? "sources" : "conversation");
    state.sourcePreviewReturnToSources = false;
  }

  async function saveCurrentNote() {
    if (!state.lastRunId || !state.sessionId) return;
    const payload = await api("/api/v2/notes/from-turn", {
      method: "POST",
      body: JSON.stringify({ run_id: state.lastRunId, work_session_id: state.sessionId }),
    });
    state.sourceSet = payload.source_set || state.sourceSet;
    if (payload.artifact) {
      state.artifact = payload.artifact;
      renderArtifact(true);
    }
    renderSources();
    renderNoticeMessage("이 답변을 private 지식 노트로 저장했습니다.");
  }

  async function uploadContextFiles() {
    const files = [...(elements.fileInput.files || [])];
    if (!files.length) {
      elements.uploadStatus.textContent = "연결할 파일을 선택해주세요.";
      return;
    }
    const button = $("[data-agent-v2-file-upload]");
    button.disabled = true;
    elements.uploadStatus.textContent = "자료를 안전하게 저장하고 있습니다.";
    const refs = lines(elements.form.elements.external_artifact_refs.value);
    try {
      for (const file of files) {
        const body = new FormData();
        body.append("file", file);
        body.append("visibility", "private");
        body.append("source_context", JSON.stringify({
          source: "pet_agent",
          attached_from_surface: "pet_agent",
          target_type: "agent_work_session",
          target_id: state.sessionId || "pending",
          attachment_role: "reference",
        }));
        const employeeId = root.dataset.employeeId || "";
        const response = await fetch(`/api/data-lake/artifacts/upload?employee_id=${encodeURIComponent(employeeId)}`, {
          method: "POST",
          credentials: "same-origin",
          body,
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
        if (payload.status === "disabled") throw new Error("파일 연결은 Data Lake가 준비된 환경에서 사용할 수 있습니다.");
        const artifact = payload.artifact || {};
        const ref = artifact.api_url || artifact.download_url || artifact.artifact_id;
        if (ref && !refs.includes(ref)) refs.push(ref);
      }
      elements.form.elements.external_artifact_refs.value = refs.join("\n");
      elements.fileInput.value = "";
      elements.uploadStatus.textContent = `${files.length}개 자료를 이 작업에 연결했습니다.`;
    } catch (error) {
      elements.uploadStatus.textContent = error.message || "자료를 연결하지 못했습니다.";
    } finally {
      button.disabled = false;
    }
  }

  function renderNoticeMessage(message) {
    elements.notice.hidden = !message;
    elements.notice.textContent = message || "";
    if (message) window.setTimeout(() => renderNotice(), 3200);
  }

  function renderNextActions() {
    elements.nextActions.innerHTML = "";
    state.nextActions.slice(0, 3).forEach((action) => {
      const button = document.createElement("button");
      button.type = "button";
      if (action.action_kind === "show_sources") {
        const sourceRefs = new Set(
          Object.values(state.sourceSet?.groups || {}).flatMap((items) => (items || []).map((item) => item.source_ref))
        );
        button.textContent = `사용한 지식 ${sourceRefs.size}개`;
      } else button.textContent = action.label;
      button.addEventListener("click", (event) => {
        if (action.action_kind === "open_task_editor") { event.preventDefault(); openTaskSheet(action.task_id || ""); }
        if (action.action_kind === "open_full_editor") { event.preventDefault(); location.href = action.href || fullEditorUrl(); }
        if (action.action_kind === "show_sources") { event.preventDefault(); openSources(); }
        if (action.action_kind === "save_note") { event.preventDefault(); saveCurrentNote().catch(showError); }
        if (action.action_kind === "confirm_plan") { event.preventDefault(); confirmAutomaticCheck(action).catch(showError); }
        if (action.action_kind === "open_artifact") {
          event.preventDefault();
          if (action.artifact_id && action.artifact_id !== state.artifact?.artifact_id) loadArtifact(action.artifact_id).catch(showError);
          else renderArtifact(true);
        }
      });
      elements.nextActions.appendChild(button);
    });
    elements.nextActions.hidden = !state.nextActions.length;
  }

  async function confirmAutomaticCheck(action) {
    if (!action.plan_id || !window.confirm("이 계획대로 자동 확인을 시작할까요?")) return;
    const result = await api(`/api/v2/plans/${encodeURIComponent(action.plan_id)}/confirm`, {
      method: "POST",
      body: JSON.stringify({confirmation: "confirm", reason: "표시된 자동 확인 계획을 검토하고 활성화함"}),
    });
    state.nextActions = state.nextActions.filter((item) => item.plan_id !== action.plan_id);
    renderNextActions();
    renderNoticeMessage(result.message || "자동 확인을 시작했습니다.");
    await loadRoutines();
  }

  function taskSummary(task, index) {
    const count = task.completion_design?.checks?.length ?? (task.exit_criteria || []).length;
    return `<button type="button" data-task-id="${escapeHtml(task.task_id)}"><span>${index + 1}</span><div><strong>${escapeHtml(task.name)}</strong><small>${escapeHtml(task.execution_mode || "copilot")} · 완료 항목 ${count}개</small></div></button>`;
  }

  function workflowTaskSummary(task, index) {
    const count = task.completion_design?.checks?.length ?? (task.exit_criteria || []).length;
    return `<article class="agent-v2-task-candidate"><span>${index + 1}</span><div><strong>${escapeHtml(task.name)}</strong><small>${escapeHtml(task.execution_mode || "copilot")} · 완료 항목 ${count}개</small></div></article>`;
  }

  function renderArtifact(reveal = false) {
    const artifact = state.artifact;
    if (!artifact) {
      elements.artifacts.innerHTML = "";
      elements.workbench.hidden = true;
      state.artifactPanelOpen = false;
      root.classList.remove("artifact-panel-open");
      root.classList.remove("diagram-artifact-active");
      updateMobileView("conversation");
      elements.fullEditor.hidden = true;
      elements.artifactKind.textContent = "작업 결과";
      elements.artifactTitle.textContent = "작업 결과";
      elements.artifactState.textContent = "";
      syncArtifactFocusUi();
      return;
    }
    if (reveal) {
      state.artifactPanelOpen = true;
      if (!isFullpage && state.mode !== "expanded") setSurfaceMode("expanded");
    } else if (isFullpage) {
      state.artifactPanelOpen = true;
    }
    const canShowPanel = state.artifactPanelOpen && (state.mode === "expanded" || state.mode === "fullpage");
    elements.workbench.hidden = !canShowPanel;
    root.classList.toggle("artifact-panel-open", canShowPanel);
    if (canShowPanel) updateMobileView("result");
    const draft = artifact.draft || {};
    const isSop = artifact.capability_id === "sop.plan";
    const isDiagram = artifact.artifact_type === "mermaid_diagram";
    const isWorkflowDraft = artifact.artifact_type === "workflow_draft";
    const isRoutine = artifact.artifact_type === "work_routine_draft";
    const hasDiagram = Boolean(isDiagram || draft.mermaid);
    root.classList.toggle("diagram-artifact-active", isDiagram);
    elements.artifactKind.textContent = isDiagram ? "흐름 그림" : isSop ? "SOP 초안" : isWorkflowDraft ? "Task 후보" : isRoutine ? "자동 확인 계획" : "작업 결과";
    elements.artifactTitle.textContent = artifact.title || "작업 결과";
    elements.artifactState.textContent = `자동 저장됨 · 버전 ${artifact.revision || 1}`;
    elements.fullEditor.hidden = !isSop;
    if (isSop) {
      elements.fullEditor.href = fullEditorUrl();
      const tasks = draft.tasks || [];
      elements.artifacts.innerHTML = `<article class="agent-v2-sop-result"><header><span>private SOP 초안</span><h3>${escapeHtml(artifact.title)}</h3><p>${escapeHtml(draft.goal || "")}</p></header>${draft.mermaid ? mermaidViewer(draft.mermaid, artifact.title, artifact.artifact_id, "sop_draft") : ""}<section class="agent-v2-task-map"><header><strong>Task ${tasks.length}개</strong><button type="button" class="secondary-button" data-agent-v2-open-tasks>Task 다듬기</button></header><div>${tasks.map(taskSummary).join("")}</div></section></article>`;
    } else if (isWorkflowDraft) {
      const tasks = draft.tasks || [];
      elements.artifacts.innerHTML = `<article class="agent-v2-workflow-result"><header><span>나만의 Task 후보</span><h3>${escapeHtml(artifact.title)}</h3><p>${escapeHtml(draft.goal || "")}</p></header>${draft.mermaid ? mermaidViewer(draft.mermaid, artifact.title, "", "workflow_draft") : ""}<section class="agent-v2-task-map"><header><strong>Task 후보 ${tasks.length}개</strong></header><div>${tasks.map(workflowTaskSummary).join("")}</div></section></article>`;
    } else if (isDiagram) {
      elements.artifactState.textContent = `근거 ${draft.source_refs?.length || 0}개 · 버전 ${artifact.revision || 1}`;
      elements.artifacts.innerHTML = `<article class="agent-v2-diagram-result">${mermaidViewer(draft.mermaid || "", artifact.title, artifact.artifact_id, "mermaid_diagram", artifact.actions || [])}</article>`;
    } else if (isRoutine) {
      const trigger = draft.schedule_description || (draft.trigger === "event" ? "연결된 업무 이벤트가 발생할 때" : "정해진 간격으로");
      elements.artifacts.innerHTML = `<article class="agent-v2-routine-result"><header><span>확인 전 계획</span><h3>${escapeHtml(artifact.title)}</h3></header><dl><div><dt>목적</dt><dd>${escapeHtml(draft.goal || "")}</dd></div><div><dt>다시 확인</dt><dd>${escapeHtml(trigger)}</dd></div><div><dt>끝내는 기준</dt><dd>${escapeHtml(draft.completion_condition || "직접 멈출 때까지")}</dd></div></dl><p>아직 자동 확인을 만들지 않았습니다.</p></article>`;
    } else {
      const body = draft.body || artifact.preview || JSON.stringify(draft, null, 2);
      elements.artifacts.innerHTML = `<article class="agent-v2-generic-result"><span>${escapeHtml(artifact.status || "draft")}</span><h3>${escapeHtml(artifact.title)}</h3><div>${renderMarkdown(body)}</div></article>`;
    }
    elements.artifactFocus.hidden = !hasDiagram;
    syncArtifactFocusUi();
    document.dispatchEvent(new CustomEvent("boi:markdown-rendered", { bubbles: true }));
    saveSurfaceState();
  }

  async function loadArtifact(artifactId, reveal = true) {
    if (!artifactId) return;
    state.artifact = await api(`/api/v2/artifacts/${encodeURIComponent(artifactId)}`);
    if (!state.sessionId && state.artifact.work_session_id) state.sessionId = state.artifact.work_session_id;
    updateUrl(artifactId);
    renderArtifact(reveal);
    await replayPendingPatch();
  }

  function setBusy(busy) {
    state.busy = busy;
    root.setAttribute("aria-busy", busy ? "true" : "false");
    const button = elements.form.querySelector("[data-agent-v2-submit]");
    button.disabled = busy;
    button.textContent = busy ? "…" : "↑";
    button.setAttribute("aria-label", busy ? "확인 중" : "보내기");
    elements.form.elements.question.disabled = busy;
    elements.starters?.querySelectorAll("button").forEach((starter) => { starter.disabled = busy; });
  }

  async function applyResponse(payload) {
    if (payload.a2ui_surface_ref) {
      root.dataset.a2uiSurfaceRef = payload.a2ui_surface_ref;
      root.dataset.a2uiCatalog = payload.presentation_plan?.catalog_id || "boi-a2ui/v1";
    } else {
      delete root.dataset.a2uiSurfaceRef;
      delete root.dataset.a2uiCatalog;
    }
    state.sessionId = payload.work_session_id || state.sessionId;
    state.nextActions = payload.next_actions || [];
    state.evidence = payload.evidence_refs || [];
    state.citations = payload.citations || [];
    state.relatedQuestions = payload.related_questions || [];
    state.lastRunId = payload.run_id || "";
    state.workRunId = payload.work_run_id || "";
    state.workRunState = payload.loop_state || null;
    state.contextAnchor = payload.context_usage?.page_anchor || state.contextAnchor;
    const artifactRef = payload.artifact_refs?.[0];
    addMessage("assistant", payload.answer?.markdown || payload.answer?.summary || "결과가 없습니다.", {
      artifactId: artifactRef?.artifact_id,
      displayHtml: payload.answer?.display_html || "",
      label: "BoI Agent",
    });
    appendLearningSummary(payload.knowledge_candidates || []);
    updateUrl(artifactRef?.artifact_id || state.artifact?.artifact_id || "");
    renderNextActions();
    renderRelated();
    renderProgress(payload.progress || []);
    renderWorkState(payload.loop_state, payload.harness_results);
    renderContext();
    await loadSources().catch(() => {});
    if (artifactRef) {
      const reveal = ["mermaid_diagram", "sop_draft"].includes(artifactRef.artifact_type);
      await loadArtifact(artifactRef.artifact_id, reveal);
      if (artifactRef.metadata?.proposal_id) {
        state.selectedTaskId = artifactRef.metadata.task_id || "";
        const proposal = await api(`/api/v2/task-proposals/${encodeURIComponent(artifactRef.metadata.proposal_id)}`);
        openTaskSheet(state.selectedTaskId);
        showProposal(proposal);
      }
    }
    await loadSessionHeader().catch(() => {});
    await loadRoutines().catch(() => {});
    if (payload.job_ref) watchJob(payload.job_ref);
  }

  async function submitQuestion(value, options = {}) {
    if (state.busy) return;
    const question = String(value || "").trim();
    if (!question) return;
    addMessage("user", question);
    if (elements.form.elements.question.value.trim() === question) elements.form.elements.question.value = "";
    setBusy(true);
    try {
      const payload = await streamAgentTurn({
        question,
        suggestion_id: options.suggestionId || null,
        suggestion_set_id: options.suggestionSetId || state.starterSet?.set_id || null,
        page_ref: pageRef,
        work_session_id: state.sessionId || null,
        external_ai_summary: elements.form.elements.external_ai_summary?.value.trim() || "",
        external_artifact_refs: lines(elements.form.elements.external_artifact_refs?.value),
      }, (progress) => {
        elements.progress.hidden = false;
        elements.progress.textContent = progress.message || "관련 업무 맥락을 확인하고 있습니다.";
      });
      await applyResponse(payload);
    } catch (error) { showError(error); }
    finally { setBusy(false); }
  }

  async function submit(event) {
    event.preventDefault();
    return submitQuestion(elements.form.elements.question.value);
  }

  function showError(error) {
    addMessage("assistant", `작업을 이어가지 못했습니다. ${error.message}`, { label: "확인 필요" });
  }

  async function watchJob(jobId) {
    let attempts = 0;
    const poll = async () => {
      attempts += 1;
      try {
        const job = await api(`/api/v2/deep-jobs/${encodeURIComponent(jobId)}`);
        if (job.status === "completed" && job.artifact_id) { await loadArtifact(job.artifact_id); addMessage("assistant", "심층 작업 초안이 준비되었습니다."); return; }
        if (job.status === "failed") { addMessage("assistant", `심층 작업을 완료하지 못했습니다. ${job.message || ""}`); return; }
        if (attempts < 120) window.setTimeout(poll, 1500);
      } catch (error) { showError(error); }
    };
    poll();
  }

  function renderTaskList() {
    const tasks = state.artifact?.draft?.tasks || [];
    elements.taskList.innerHTML = tasks.map((task, index) => `<button type="button" class="${task.task_id === state.selectedTaskId ? "active" : ""}" data-task-id="${escapeHtml(task.task_id)}"><span>${index + 1}</span><div><strong>${escapeHtml(task.name)}</strong><small>${escapeHtml(task.execution_mode)}</small></div></button>`).join("");
  }

  function selectedTask() {
    return state.artifact?.draft?.tasks?.find((item) => item.task_id === state.selectedTaskId) || null;
  }

  function hydrateTaskForm(task) {
    if (!task) return;
    state.taskHydrating = true;
    state.baseTask = clone(task);
    elements.taskForm.elements.task_id.value = task.task_id;
    ["name", "purpose", "tat"].forEach((field) => { elements.taskForm.elements[field].value = task[field] || ""; });
    ["outputs", "action_refs", "event_refs", "skill_refs", "verification", "fallback"].forEach((field) => { elements.taskForm.elements[field].value = joinLines(task[field]); });
    const mode = elements.taskForm.querySelector(`[name="execution_mode"][value="${CSS.escape(task.execution_mode || "copilot")}"]`);
    if (mode) mode.checked = true;
    completionEditor?.setTask(task);
    elements.taskHeading.textContent = task.name || "Task";
    state.taskDirty = false;
    elements.taskStatus.textContent = "변경하면 자동 저장됩니다.";
    elements.conflict.hidden = true;
    state.taskHydrating = false;
    renderTaskList();
  }

  function openTaskSheet(taskId) {
    if (!state.artifact || state.artifact.capability_id !== "sop.plan") return;
    if (!isFullpage && state.mode !== "expanded") setSurfaceMode("expanded");
    state.selectedTaskId = taskId || state.session?.selected_task_id || state.artifact.draft.tasks?.[0]?.task_id || "";
    renderTaskList();
    hydrateTaskForm(selectedTask());
    elements.backdrop.hidden = false;
    elements.taskSheet.hidden = false;
    state.focusBeforeTask = document.activeElement;
    document.body.classList.add("agent-v2-task-open");
    const href = fullEditorUrl();
    $("[data-agent-v2-task-full-editor]").href = href;
    patchSession({ selected_task_id: state.selectedTaskId, active_panel: "task" }).catch(() => {});
    window.setTimeout(() => $("[data-agent-v2-task-close]").focus(), 0);
  }

  function closeTaskSheet() {
    elements.backdrop.hidden = true;
    elements.taskSheet.hidden = true;
    document.body.classList.remove("agent-v2-task-open");
    patchSession({ active_panel: "result" }).catch(() => {});
    if (state.focusBeforeTask instanceof HTMLElement) state.focusBeforeTask.focus();
    state.focusBeforeTask = null;
  }

  function collectTask() {
    const form = elements.taskForm.elements;
    const completionDesign = completionEditor?.getDesign() || {version: 1, checks: [], evidence: []};
    const completionProjection = completionEditor?.getProjection() || {exit_criteria: [], required_evidence: []};
    return {
      ...clone(state.baseTask),
      task_id: form.task_id.value,
      name: form.name.value.trim(),
      purpose: form.purpose.value.trim(),
      execution_mode: form.execution_mode.value || "copilot",
      completion_design: completionDesign,
      completion_readiness: completionEditor?.getReadiness() || {},
      exit_criteria: completionProjection.exit_criteria,
      required_evidence: completionProjection.required_evidence,
      outputs: lines(form.outputs.value),
      action_refs: lines(form.action_refs.value),
      event_refs: lines(form.event_refs.value),
      skill_refs: lines(form.skill_refs.value),
      tat: form.tat.value.trim(),
      verification: lines(form.verification.value),
      fallback: lines(form.fallback.value),
    };
  }

  function queueTaskSave() {
    if (state.taskHydrating || !state.baseTask) return;
    state.taskDirty = true;
    elements.taskStatus.textContent = "저장 중...";
    clearTimeout(state.saveTimer);
    state.saveTimer = window.setTimeout(saveTask, 500);
  }

  async function saveTask(options) {
    if (!state.taskDirty || !state.artifact || !state.baseTask) return;
    const task = options?.task || collectTask();
    const body = options?.body || {
      expected_revision: state.artifact.revision || 1,
      task_updates: [{ task_id: task.task_id, base_task: state.baseTask, task }],
      selected_task_id: task.task_id,
    };
    state.pendingPatch = { artifactId: state.artifact.artifact_id, body, task };
    await pendingDbPut(state.pendingPatch).catch(() => {});
    try {
      const artifact = await api(`/api/v2/artifacts/${encodeURIComponent(state.artifact.artifact_id)}/sop`, { method: "PATCH", body: JSON.stringify(body), keepalive: Boolean(options?.keepalive) });
      state.artifact = artifact;
      state.selectedTaskId = task.task_id;
      state.baseTask = clone(selectedTask());
      state.taskDirty = false;
      state.pendingPatch = null;
      elements.taskStatus.textContent = `저장됨 · 버전 ${artifact.revision}`;
      elements.artifactState.textContent = `자동 저장됨 · 버전 ${artifact.revision}`;
      await pendingDbDelete(artifact.artifact_id).catch(() => {});
      renderArtifact();
      renderTaskList();
      channel?.postMessage({ artifactId: artifact.artifact_id, revision: artifact.revision });
    } catch (error) {
      if (error.status === 409) showConflict(error.detail, task);
      else elements.taskStatus.textContent = `저장 대기 · 연결되면 다시 시도합니다. ${error.message}`;
    }
  }

  function showConflict(detail, submittedTask) {
    const conflicts = detail?.conflicts || [];
    state.conflict = { detail, submittedTask };
    elements.conflict.hidden = false;
    elements.conflict.innerHTML = `<strong>같은 항목이 다른 화면에서도 수정되었습니다.</strong><p>어느 내용을 남길지 확인해주세요.</p>${conflicts.map((item) => `<article><b>${escapeHtml(item.task_id)}</b><span>${escapeHtml((item.fields || []).join(", "))}</span><div><pre>현재\n${escapeHtml(JSON.stringify(item.current, null, 2))}</pre><pre>내 변경\n${escapeHtml(JSON.stringify(item.submitted, null, 2))}</pre></div></article>`).join("")}<div><button type="button" data-conflict-choice="server">현재 내용 불러오기</button><button type="button" class="primary-button" data-conflict-choice="mine">내 변경 적용</button></div>`;
    elements.taskStatus.textContent = "수정 충돌을 확인해주세요.";
  }

  async function resolveConflict(choice) {
    if (!state.conflict) return;
    const latest = state.conflict.detail.artifact || await api(`/api/v2/artifacts/${encodeURIComponent(state.artifact.artifact_id)}`);
    state.artifact = latest;
    const submitted = state.conflict.submittedTask;
    elements.conflict.hidden = true;
    if (choice === "server") {
      state.selectedTaskId = submitted.task_id;
      hydrateTaskForm(selectedTask());
      renderArtifact();
      return;
    }
    const current = selectedTask();
    state.baseTask = clone(current);
    state.taskDirty = true;
    await saveTask({ task: submitted, body: { expected_revision: latest.revision, task_updates: [{ task_id: submitted.task_id, base_task: current, task: submitted }], selected_task_id: submitted.task_id } });
    hydrateTaskForm(selectedTask());
  }

  function proposalFieldLabel(field) {
    return {
      name: "Task 이름",
      purpose: "이 Task의 목적",
      execution_mode: "수행 방식",
      completion_design: "완료된 모습과 확인할 자료",
      outputs: "남길 결과물",
    }[field] || field;
  }

  function proposalValue(value, field) {
    if (field === "completion_design") {
      const checks = (value?.checks || []).map((item) => `<li>${escapeHtml(item.label || "")}</li>`).join("");
      const evidence = (value?.evidence || []).map((item) => `<li>${escapeHtml(item.label || "")}</li>`).join("");
      return `<div class="agent-v2-proposal-friendly"><b>완료된 모습</b><ul>${checks || "<li>없음</li>"}</ul><b>확인할 자료</b><ul>${evidence || "<li>없음</li>"}</ul></div>`;
    }
    if (Array.isArray(value)) return `<ul class="agent-v2-proposal-friendly">${value.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>없음</li>"}</ul>`;
    return `<p class="agent-v2-proposal-friendly">${escapeHtml(value || "없음")}</p>`;
  }

  function showProposal(proposal) {
    if (!proposal) return;
    state.proposal = proposal;
    elements.proposal.hidden = false;
    const fields = (proposal.changed_fields || []).filter((field) => !["exit_criteria", "required_evidence", "completion_readiness"].includes(field));
    elements.proposalDiff.innerHTML = fields.map((field) => `<article><strong>${escapeHtml(proposalFieldLabel(field))}</strong><div><span>현재</span>${proposalValue(proposal.before?.[field], field)}</div><div><span>제안</span>${proposalValue(proposal.after?.[field], field)}</div></article>`).join("");
    elements.taskStatus.textContent = "제안을 확인한 뒤 적용하세요.";
  }

  async function refineTask() {
    if (state.taskDirty) await saveTask();
    const task = selectedTask();
    if (!task) return;
    elements.taskStatus.textContent = "선택한 Task를 구체화하고 있습니다.";
    try {
      const proposal = await api(`/api/v2/artifacts/${encodeURIComponent(state.artifact.artifact_id)}/tasks/${encodeURIComponent(task.task_id)}/refine-preview`, { method: "POST", body: JSON.stringify({ expected_revision: state.artifact.revision, instruction: "목적을 유지하면서 일반 구성원이 이해할 완료된 모습과 확인할 자료를 쉬운 문장으로 제안해줘. 기술 연결은 별도 binding에만 넣어줘" }) });
      showProposal(proposal);
    } catch (error) { elements.taskStatus.textContent = `구체화하지 못했습니다. ${error.message}`; }
  }

  async function applyProposal() {
    if (!state.proposal) return;
    try {
      state.artifact = await api(`/api/v2/artifacts/${encodeURIComponent(state.artifact.artifact_id)}/tasks/${encodeURIComponent(state.selectedTaskId)}/proposals/${encodeURIComponent(state.proposal.proposal_id)}/apply`, { method: "POST", body: JSON.stringify({ expected_revision: state.artifact.revision }) });
      elements.proposal.hidden = true;
      state.proposal = null;
      hydrateTaskForm(selectedTask());
      renderArtifact();
      elements.taskStatus.textContent = `제안을 적용했습니다 · 버전 ${state.artifact.revision}`;
      channel?.postMessage({ artifactId: state.artifact.artifact_id, revision: state.artifact.revision });
    } catch (error) { elements.taskStatus.textContent = `제안을 적용하지 못했습니다. ${error.message}`; }
  }

  async function patchSession(values) {
    if (!state.session) return;
    try {
      state.session = await api(`/api/v2/work-sessions/${encodeURIComponent(state.sessionId)}`, { method: "PATCH", body: JSON.stringify({ expected_revision: state.session.revision, ...values }) });
    } catch (error) {
      if (error.status === 409 && error.detail?.session) state.session = error.detail.session;
    }
  }

  async function loadSessionHeader() {
    if (!state.sessionId) return;
    const bundle = await api(`/api/v2/work-sessions/${encodeURIComponent(state.sessionId)}`);
    state.session = bundle.session;
    elements.title.textContent = state.session.title || "BoI Agent";
    elements.saveState.textContent = state.session.pinned ? "고정된 작업" : "자동 저장됨";
  }

  async function loadSession() {
    if (!state.sessionId) return false;
    const bundle = await api(`/api/v2/work-sessions/${encodeURIComponent(state.sessionId)}`);
    state.session = bundle.session;
    renderTimeline(bundle.timeline || []);
    elements.title.textContent = state.session.title || "BoI Agent";
    elements.saveState.textContent = state.session.pinned ? "고정된 작업" : "자동 저장됨";
    state.sourceSet = bundle.source_set || null;
    restoreSurfaceState();
    if (bundle.active_artifact) {
      state.artifact = bundle.active_artifact;
      renderArtifact();
    } else renderArtifact();
    renderSources();
    renderRelated();
    renderNextActions();
    return true;
  }

  async function loadRecent() {
    try {
      const payload = await api("/api/v2/work-sessions?limit=8");
      elements.recent.innerHTML = payload.items?.length ? payload.items.map((item) => `<article><button type="button" class="agent-surface-recent-open" data-open-session="${escapeHtml(item.session_id)}"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.updated_at?.slice(0, 16).replace("T", " ") || "")}</span></button><button type="button" data-delete-session="${escapeHtml(item.session_id)}" title="작업 삭제" aria-label="${escapeHtml(item.title)} 삭제">×</button></article>`).join("") : "<p>아직 저장된 작업이 없습니다.</p>";
    } catch (error) { elements.recent.innerHTML = `<p>${escapeHtml(error.message)}</p>`; }
  }

  async function switchSession(sessionId) {
    state.sessionId = sessionId;
    state.session = null;
    state.artifact = null;
    state.sourceSet = null;
    state.evidence = [];
    state.citations = [];
    state.relatedQuestions = [];
    state.nextActions = [];
    state.lastRunId = "";
    state.workRunId = "";
    state.workRunState = null;
    state.artifactPanelOpen = false;
    state.artifactFocusOpen = false;
    state.diagramViews = {};
    state.suggestionsExpanded = false;
    updateUrl("");
    await loadSession();
    elements.recent.closest("details")?.removeAttribute("open");
  }

  async function newSession() {
    const session = await api("/api/v2/work-sessions", { method: "POST", body: JSON.stringify({ title: "새 업무", page_ref: pageRef }) });
    await switchSession(session.session_id);
    renderEmpty();
    elements.title.textContent = "무엇을 찾거나 진행할까요?";
    elements.saveState.textContent = "새 작업";
    elements.form.elements.question.focus();
    await loadRecent();
  }

  function pendingDb() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open("boi-agent-v2", 1);
      request.onupgradeneeded = () => request.result.createObjectStore("patches", { keyPath: "artifactId" });
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }
  async function pendingDbPut(value) { const db = await pendingDb(); db.transaction("patches", "readwrite").objectStore("patches").put(value); }
  async function pendingDbDelete(key) { const db = await pendingDb(); db.transaction("patches", "readwrite").objectStore("patches").delete(key); }
  async function pendingDbGet(key) {
    const db = await pendingDb();
    return new Promise((resolve, reject) => { const request = db.transaction("patches").objectStore("patches").get(key); request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error); });
  }
  async function replayPendingPatch() {
    if (!state.artifact) return;
    const pending = await pendingDbGet(state.artifact.artifact_id).catch(() => null);
    if (!pending) return;
    state.pendingPatch = pending;
    state.taskDirty = true;
    state.baseTask = pending.body?.task_updates?.[0]?.base_task || null;
    state.selectedTaskId = pending.task?.task_id || "";
    await saveTask({ task: pending.task, body: pending.body });
  }

  elements.form.addEventListener("submit", submit);
  elements.messages.addEventListener("scroll", () => {
    const key = scrollStorageKey();
    if (key) sessionStorage.setItem(key, String(Math.round(elements.messages.scrollTop)));
    saveSurfaceState();
  }, { passive: true });
  elements.artifacts.addEventListener("scroll", saveSurfaceState, { passive: true });
  elements.form.elements.question.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); elements.form.requestSubmit(); } });
  elements.launcher.addEventListener("click", () => setSurfaceMode("compact"));
  $("[data-agent-v2-close]").addEventListener("click", () => setSurfaceMode("closed"));
  $("[data-agent-v2-expand]").addEventListener("click", () => setSurfaceMode(state.mode === "expanded" ? "compact" : "expanded"));
  elements.artifactFocus.addEventListener("click", () => setArtifactFocus(!state.artifactFocusOpen));
  $("[data-agent-v2-attach]").addEventListener("click", () => { elements.attachments.hidden = !elements.attachments.hidden; });
  $("[data-agent-v2-file-upload]").addEventListener("click", () => uploadContextFiles());
  $("[data-agent-v2-attachments-close]").addEventListener("click", () => { elements.attachments.hidden = true; });
  $("[data-agent-v2-workbench-close]").addEventListener("click", () => { state.artifactPanelOpen = false; elements.workbench.hidden = true; root.classList.remove("artifact-panel-open"); syncArtifactFocusUi(); updateMobileView("conversation"); saveSurfaceState(); });
  $("[data-agent-v2-sources-close]").addEventListener("click", () => { elements.sources.hidden = true; updateMobileView("conversation"); });
  $("[data-agent-v2-source-preview-close]").addEventListener("click", closeSourcePreview);
  elements.routinesButton.addEventListener("click", () => openRoutines().catch(showError));
  $("[data-agent-v2-routines-close]").addEventListener("click", () => { elements.routines.hidden = true; });
  $("[data-agent-v2-new]").addEventListener("click", () => newSession().catch(showError));
  elements.recent.addEventListener("click", async (event) => {
    const openId = event.target.closest("[data-open-session]")?.dataset.openSession;
    if (openId) {
      await switchSession(openId).catch(showError);
      return;
    }
    const sessionId = event.target.closest("[data-delete-session]")?.dataset.deleteSession;
    if (!sessionId) return;
    if (!window.confirm("이 private 작업과 미게시 초안을 삭제할까요?")) return;
    try {
      await api(`/api/v2/work-sessions/${encodeURIComponent(sessionId)}`, {method: "DELETE"});
      if (sessionId === state.sessionId) { await newSession(); return; }
      await loadRecent();
    } catch (error) { showError(error); }
  });
  elements.related.addEventListener("click", (event) => {
    const question = event.target.closest("[data-related-question]")?.dataset.relatedQuestion;
    if (!question || state.busy) return;
    submitQuestion(question).catch(showError);
  });
  elements.mobileTabs.addEventListener("click", (event) => {
    const view = event.target.closest("[data-agent-v2-mobile-view]")?.dataset.agentV2MobileView;
    if (!view) return;
    elements.sourcePreview.hidden = true;
    if (view === "sources") { openSources(); return; }
    elements.sources.hidden = true;
    if (view === "result" && state.artifact) {
      state.artifactPanelOpen = true;
      elements.workbench.hidden = false;
      root.classList.add("artifact-panel-open");
    } else {
      state.artifactPanelOpen = false;
      elements.workbench.hidden = true;
      root.classList.remove("artifact-panel-open");
    }
    state.mobileView = view;
    syncArtifactFocusUi();
    updateMobileView(view);
    saveSurfaceState();
  });
  elements.messages.addEventListener("click", (event) => {
    const artifactId = event.target.closest("[data-message-artifact]")?.dataset.messageArtifact;
    if (artifactId) {
      event.preventDefault();
      if (artifactId !== state.artifact?.artifact_id) loadArtifact(artifactId, true).catch(showError);
      else renderArtifact(true);
      return;
    }
    const link = event.target.closest('a[href^="/api/v2/citations/"]');
    if (!link) return;
    event.preventDefault();
    openCitation(link.getAttribute("href").split("/").pop()).catch(showError);
  });
  elements.sourceList.addEventListener("click", (event) => {
    const pin = event.target.closest("[data-source-pin]")?.dataset.sourcePin;
    const unpin = event.target.closest("[data-source-unpin]")?.dataset.sourceUnpin;
    const exclude = event.target.closest("[data-source-exclude]")?.dataset.sourceExclude;
    if (pin) patchSources({ pin_refs: [pin] }).catch(showError);
    if (unpin) patchSources({ unpin_refs: [unpin] }).catch(showError);
    if (exclude) patchSources({ exclude_refs: [exclude] }).catch(showError);
  });
  elements.routineList.addEventListener("click", async (event) => {
    const routineId = event.target.closest("[data-routine-cancel]")?.dataset.routineCancel;
    if (!routineId || !window.confirm("이 자동 확인을 멈출까요?")) return;
    try {
      await api(`/api/v2/work-routines/${encodeURIComponent(routineId)}/cancel`, {method: "POST", body: "{}"});
      await loadRoutines();
    } catch (error) { showError(error); }
  });
  elements.context.addEventListener("click", (event) => {
    const exclude = event.target.closest("[data-source-exclude]")?.dataset.sourceExclude;
    if (exclude) patchSources({ exclude_refs: [exclude] }).catch(showError);
  });
  elements.artifacts.addEventListener("click", (event) => {
    const mermaidControl = event.target.closest("[data-mermaid-view]");
    if (mermaidControl) {
      const diagram = mermaidControl.closest("[data-v2-mermaid]");
      if (diagram) {
        const action = mermaidControl.dataset.mermaidView;
        const current = Number(diagram.dataset.zoom || 1);
        if (action === "read" || action === "fit") setMermaidView(diagram, action, action === "fit" ? 1 : current);
        else setMermaidView(diagram, "custom", current + (action === "in" ? .2 : -.2));
      }
      return;
    }
    const taskButton = event.target.closest("[data-task-id]");
    if (taskButton) openTaskSheet(taskButton.dataset.taskId);
    if (event.target.closest("[data-agent-v2-open-tasks]")) openTaskSheet("");
    const action = event.target.closest("[data-agent-v2-result-action]")?.dataset.agentV2ResultAction;
    if (action === "tasks") openTaskSheet("");
    if (action === "full") location.href = fullEditorUrl();
  });
  let mermaidPan = null;
  elements.artifacts.addEventListener("pointerdown", (event) => {
    const canvas = event.target.closest(".mermaid-v2-canvas");
    if (!canvas || event.button !== 0 || event.pointerType === "touch" || event.target.closest("button, a, summary")) return;
    if (canvas.scrollWidth <= canvas.clientWidth + 2 && canvas.scrollHeight <= canvas.clientHeight + 2) return;
    mermaidPan = { canvas, pointerId: event.pointerId, x: event.clientX, y: event.clientY, left: canvas.scrollLeft, top: canvas.scrollTop };
    canvas.classList.add("is-panning");
    canvas.setPointerCapture(event.pointerId);
    event.preventDefault();
  });
  elements.artifacts.addEventListener("pointermove", (event) => {
    if (!mermaidPan || mermaidPan.pointerId !== event.pointerId) return;
    mermaidPan.canvas.scrollLeft = mermaidPan.left - (event.clientX - mermaidPan.x);
    mermaidPan.canvas.scrollTop = mermaidPan.top - (event.clientY - mermaidPan.y);
  });
  const stopMermaidPan = (event) => {
    if (!mermaidPan || mermaidPan.pointerId !== event.pointerId) return;
    mermaidPan.canvas.classList.remove("is-panning");
    rememberMermaidView(mermaidPan.canvas.closest("[data-v2-mermaid]"));
    mermaidPan = null;
  };
  elements.artifacts.addEventListener("pointerup", stopMermaidPan);
  elements.artifacts.addEventListener("pointercancel", stopMermaidPan);
  elements.artifacts.addEventListener("keydown", (event) => {
    const canvas = event.target.closest(".mermaid-v2-canvas");
    if (!canvas || event.target !== canvas) return;
    const diagram = canvas.closest("[data-v2-mermaid]");
    const current = Number(diagram?.dataset.zoom || 1);
    if (event.key === "+" || event.key === "=") setMermaidView(diagram, "custom", current + .2);
    else if (event.key === "-") setMermaidView(diagram, "custom", current - .2);
    else if (event.key === "0") setMermaidView(diagram, "fit", 1);
    else if (event.key === "ArrowLeft") canvas.scrollBy({ left: -80 });
    else if (event.key === "ArrowRight") canvas.scrollBy({ left: 80 });
    else if (event.key === "ArrowUp") canvas.scrollBy({ top: -80 });
    else if (event.key === "ArrowDown") canvas.scrollBy({ top: 80 });
    else return;
    event.preventDefault();
  });
  elements.artifacts.addEventListener("boi:mermaid-rendered", (event) => {
    syncResponsiveMermaidScale(event.target.closest?.("[data-v2-mermaid]") || event.target);
  });
  let mermaidResizeTimer = 0;
  window.addEventListener("resize", () => {
    window.clearTimeout(mermaidResizeTimer);
    mermaidResizeTimer = window.setTimeout(() => { syncArtifactFocusUi(); syncResponsiveMermaidScales(); }, 100);
  });
  elements.taskList.addEventListener("click", (event) => { const button = event.target.closest("[data-task-id]"); if (button) { if (state.taskDirty) saveTask(); state.selectedTaskId = button.dataset.taskId; hydrateTaskForm(selectedTask()); } });
  elements.taskForm.addEventListener("input", queueTaskSave);
  elements.taskForm.addEventListener("change", (event) => {
    if (event.target.name === "execution_mode") completionEditor?.setMode(event.target.value);
    queueTaskSave();
  });
  $("[data-agent-v2-task-close]").addEventListener("click", closeTaskSheet);
  elements.backdrop.addEventListener("click", closeTaskSheet);
  $("[data-agent-v2-refine]").addEventListener("click", refineTask);
  $("[data-agent-v2-proposal-apply]").addEventListener("click", applyProposal);
  $("[data-agent-v2-proposal-dismiss]").addEventListener("click", () => { elements.proposal.hidden = true; state.proposal = null; });
  elements.conflict.addEventListener("click", (event) => { const choice = event.target.closest("[data-conflict-choice]")?.dataset.conflictChoice; if (choice) resolveConflict(choice); });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Tab" && !elements.taskSheet.hidden) {
      const focusable = [...elements.taskSheet.querySelectorAll('button:not([disabled]), a[href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), summary')]
        .filter((item) => item.offsetParent !== null);
      if (focusable.length) {
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
      return;
    }
    if (event.key !== "Escape") return;
    if (!elements.taskSheet.hidden) closeTaskSheet();
    else if (!elements.sourcePreview.hidden) closeSourcePreview();
    else if (!elements.routines.hidden) elements.routines.hidden = true;
    else if (!elements.sources.hidden) elements.sources.hidden = true;
    else if (root.classList.contains("artifact-focus-open")) setArtifactFocus(false);
    else if (!isFullpage && state.mode === "expanded") setSurfaceMode("compact");
    else if (!isFullpage && state.mode === "compact") setSurfaceMode("closed");
  });
  window.addEventListener("pagehide", () => { saveSurfaceState(); if (state.taskDirty && state.artifact && state.baseTask) { clearTimeout(state.saveTimer); saveTask({ keepalive: true }); } });
  channel?.addEventListener("message", async (event) => { if (state.artifact && event.data?.artifactId === state.artifact.artifact_id && Number(event.data.revision) > Number(state.artifact.revision)) { await loadArtifact(state.artifact.artifact_id, false); if (!state.taskDirty && state.selectedTaskId) hydrateTaskForm(selectedTask()); } });

  async function initialize() {
    try {
      state.bootstrap = await api(`/api/v2/bootstrap?page_ref=${encodeURIComponent(pageRef)}`);
      state.contextAnchor = state.bootstrap?.page?.context || null;
      setSurfaceMode(state.mode, false);
      renderNotice(); renderStarters(); renderRelated(); renderSources(); renderArtifact();
      await Promise.allSettled([loadRecent(), loadRoutines()]);
      const loaded = await loadSession().catch(() => false);
      if (!loaded) renderEmpty();
      const artifactId = params.get("artifact");
      if (artifactId && (!loaded || artifactId !== state.artifact?.artifact_id)) await loadArtifact(artifactId);
      if (isFullpage) setSurfaceMode("fullpage");
    } catch (_error) {
      elements.notice.hidden = false;
      elements.notice.textContent = "BoI Agent를 준비하지 못했습니다. 잠시 후 다시 열어주세요.";
      if (!elements.messages.children.length) renderEmpty();
    }
  }
  initialize();
})();
