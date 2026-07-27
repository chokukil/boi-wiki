(() => {
  const root = document.querySelector("[data-agent-playground]");
  if (!root) return;

  const employeeId = root.dataset.employeeId || "";
  const endpointSelect = root.querySelector("[data-endpoint-select]");
  const projectSelect = root.querySelector("[data-project-select]");
  const endpointList = root.querySelector("[data-endpoint-list]");
  const endpointForm = root.querySelector("[data-endpoint-form]");
  const endpointSummary = root.querySelector("[data-endpoint-summary]");
  const flowList = root.querySelector("[data-flow-list]");
  const toast = root.querySelector("[data-playground-toast]");
  const onboardingRoot = root.querySelector("[data-onboarding]");
  const workbenchOnly = [...root.querySelectorAll("[data-workbench-only]")];
  const hubSearchForm = root.querySelector("[data-hub-search-form]");
  const hubAssetsRoot = root.querySelector("[data-hub-assets]");
  const hubSelectedRoot = root.querySelector("[data-hub-selected]");
  const hubCandidatesRoot = root.querySelector("[data-hub-candidates]");
  const hubAdoptionOutput = root.querySelector("[data-hub-adoption-output]");
  const hubProfileSelect = root.querySelector("[data-hub-validation-profile]");
  const hubBeginButton = root.querySelector("[data-hub-adoption-begin]");
  const hubDiscoverButton = root.querySelector("[data-hub-adoption-discover]");
  const hubDeployLink = root.querySelector("[data-hub-deploy-link]");
  const componentStatusRoot = root.querySelector("[data-component-status]");
  const taskSelect = root.querySelector("[data-task-select]");
  const nextActionRoot = root.querySelector("[data-next-action]");
  const nextActionButton = root.querySelector("[data-next-action-button]");
  const hubOnboardingRoot = root.querySelector("[data-hub-onboarding]");
  const hubOwnOpen = root.querySelector("[data-hub-own-open]");
  const hubOwnDownload = root.querySelector("[data-hub-own-download]");
  const hubOwnRefresh = root.querySelector("[data-hub-own-refresh]");
  const initialParams = new URLSearchParams(window.location.search);
  const deepLink = {
    stage: initialParams.get("stage") || "",
    endpointId: initialParams.get("endpoint_id") || "",
    projectId: initialParams.get("project_id") || "",
    flowId: initialParams.get("flow_id") || "",
  };
  const app = {
    state: null,
    endpointId: "",
    projectId: "",
    flow: null,
    projects: [],
    flows: [],
    guideForced: false,
    flowFilter: "",
    hubAssets: [],
    hubSelected: new Map(),
    hubAdoption: null,
    hubCandidates: [],
    tasks: [],
    tasksLoaded: false,
    activeStep: "create",
    journeyInitialized: false,
    hubMode: "own",
    ownFlowSnapshot: new Set(),
    deepLink,
    deepLinkApplied: false,
  };

  const withIdentity = (path) => {
    const url = new URL(path, window.location.origin);
    if (employeeId && (!app.state || app.state.identity.auth_source === "dev")) {
      url.searchParams.set("employee_id", employeeId);
    }
    return `${url.pathname}${url.search}`;
  };

  const request = async (path, options = {}) => {
    const response = await fetch(withIdentity(path), {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    let payload = {};
    try { payload = await response.json(); } catch (_) { payload = {}; }
    if (!response.ok) {
      const detail = payload.detail || payload.message || `HTTP ${response.status}`;
      throw new Error(typeof detail === "string" ? detail : (detail.message || JSON.stringify(detail)));
    }
    return payload;
  };

  const showToast = (message, state = "info") => {
    toast.textContent = message;
    toast.dataset.state = state;
    toast.hidden = false;
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => { toast.hidden = true; }, 5000);
  };

  const statusLabel = {
    connected: "연결됨",
    inactive: "비활성",
    error: "확인 실패",
    discovered: "발견됨",
    structural_validated: "구조 확인",
    build_validated: "Build 확인",
    runtime_validated: "Runtime 확인",
    task_validated: "Task 확인",
    action_ready: "Action 준비",
    action_linked: "Action 연결",
    blocked: "차단됨",
    drifted: "변경되어 재검증 필요",
  };

  const stageLabel = {
    create: "1 · 만들기",
    test: "2 · 테스트",
    hub: "3 · Agent Hub",
    action: "4 · Action 연결",
  };

  const setStatus = (name, status, detail) => {
    const card = root.querySelector(`[data-status-card="${name}"]`);
    if (!card) return;
    card.dataset.state = status || "discovered";
    card.querySelector("[data-status-value]").textContent = statusLabel[status] || "준비 전";
    card.querySelector("[data-status-detail]").textContent = detail || "";
  };

  const selectedEndpoint = () => (
    (app.state && app.state.endpoints || []).find((item) => item.endpoint_id === app.endpointId) || null
  );

  const escapeText = (value) => String(value == null ? "" : value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const setWorkbenchStep = (step, { scroll = false } = {}) => {
    const allowed = new Set(["create", "test", "hub", "action"]);
    app.activeStep = allowed.has(step) ? step : "create";
    root.querySelectorAll("[data-workbench-step]").forEach((button) => {
      const active = button.dataset.workbenchStep === app.activeStep;
      button.classList.toggle("active", active);
      if (active) button.setAttribute("aria-current", "step");
      else button.removeAttribute("aria-current");
    });
    root.querySelectorAll("[data-workbench-panel]").forEach((panel) => {
      const steps = String(panel.dataset.workbenchPanel || "").split(/\s+/).filter(Boolean);
      panel.hidden = !steps.includes(app.activeStep);
    });
    root.querySelectorAll("[data-step-action]").forEach((action) => {
      action.hidden = action.dataset.stepAction !== app.activeStep;
    });
    if (app.activeStep === "test") loadTasks();
    if (app.state) renderJourney();
    if (scroll) {
      const first = root.querySelector(`[data-workbench-panel~="${app.activeStep}"]:not([hidden])`);
      if (first) first.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const selectedSetup = () => (
    (app.state && app.state.endpoint_setups && app.state.endpoint_setups[app.endpointId]) || null
  );

  const selectedOnboarding = () => {
    const setup = selectedSetup();
    return (setup && setup.onboarding) || (app.state && app.state.onboarding) || {
      required: true,
      status: "not_started",
      current_step: "connection",
      steps: [],
      next_action: "open_langflow_settings",
    };
  };

  const selectedHubOnboarding = () => {
    const deployments = (app.state && app.state.deployments) || [];
    const selectedDeployments = deployments.filter((item) => (
      item.endpoint_id === app.endpointId
      && (!app.projectId || item.project_id === app.projectId)
    ));
    if (selectedDeployments.length) {
      return {
        required: false,
        status: "complete",
        next_action: "review_deployment",
        message: "Agent Hub 배포 Flow를 이 프로젝트에서 확인했습니다.",
      };
    }
    const pending = matchingHubAdoption();
    if (pending) {
      return {
        required: true,
        status: "in_progress",
        next_action: "discover_deployment",
        message: "Agent Hub 배포를 마친 뒤 배포 결과를 확인하세요.",
      };
    }
    return (app.state && app.state.hub_onboarding) || {
      required: true,
      status: "not_started",
      next_action: "open_agent_hub",
      message: "첫 배포 전에 endpoint와 개인 프로젝트 연결을 안내합니다.",
    };
  };

  const renderJourney = () => {
    if (!app.state) return;
    const endpoint = selectedEndpoint();
    const project = app.projects.find((item) => item.id === app.projectId)
      || ((selectedSetup() || {}).project || {});
    root.querySelector("[data-context-endpoint]").textContent = endpoint
      ? `${endpoint.name || "내 Langflow"} · ${endpoint.version || "확인 중"}`
      : "연결 필요";
    root.querySelector("[data-context-project]").textContent = project.name || `boi-${employeeId}`;
    root.querySelector("[data-context-stage]").textContent = stageLabel[app.activeStep] || "온보딩";

    const journey = app.state.journey || {};
    const suggested = journey.next_action || {};
    const stageActions = {
      create: {
        id: "open_langflow",
        stage: "create",
        label: "Langflow에서 만들기",
        description: "개인 프로젝트에서 Flow와 Agent를 편집하세요.",
      },
      test: {
        id: "validate_flow",
        stage: "test",
        label: "Flow 검증하기",
        description: "업무 맥락·Ontology·Wiki 근거와 저장 결과를 확인하세요.",
      },
      hub: {
        id: "open_agent_hub",
        stage: "hub",
        label: app.hubMode === "shared" ? "공유 자산 가져오기" : "Agent Hub에 배포",
        description: app.hubMode === "shared"
          ? "승인된 Flow·Component를 내 프로젝트에서 검증하세요."
          : "테스트를 마친 내 Flow를 Agent Hub 기존 UI에서 배포하세요.",
      },
      action: {
        id: "create_action",
        stage: "action",
        label: "Action으로 연결",
        description: "검증된 Flow를 connector-neutral Action 실행 연결로 등록하세요.",
      },
    };
    const next = stageActions[app.activeStep] || suggested;
    const guideByStage = {
      create: "/docs/boi:public:boi-wiki-manual:langflow:agent-playground-langflow-setup",
      test: "/docs/boi:public:boi-wiki-manual:langflow:agent-playground-action-wiki",
      hub: app.hubMode === "shared"
        ? "/docs/boi:public:boi-wiki-manual:langflow:agent-playground-shared-assets"
        : "/docs/boi:public:boi-wiki-manual:langflow:agent-playground-my-flow-deploy",
      action: "/docs/boi:public:boi-wiki-manual:langflow:agent-playground-action-wiki",
    };
    root.querySelector("[data-journey-summary]").textContent = next.description
      || "개인 Langflow에서 만들고, 검증한 뒤, Agent Hub와 BoI Action으로 연결합니다.";
    root.querySelector("[data-next-action-step]").textContent = stageLabel[next.stage] || "다음 할 일";
    root.querySelector("[data-next-action-label]").textContent = next.label || "내 Flow 만들기";
    root.querySelector("[data-next-action-description]").textContent = next.description
      || "개인 Langflow 프로젝트에서 Flow를 편집하세요.";
    nextActionButton.dataset.actionId = next.id || "open_langflow";
    nextActionButton.dataset.targetStep = next.stage || app.activeStep;
    nextActionButton.textContent = next.label || "계속";
    root.querySelector("[data-next-action-guide]").href = guideByStage[app.activeStep]
      || "/docs/boi:public:boi-wiki-manual:langflow:agent-playground-onboarding";

    const hub = selectedHubOnboarding();
    hubOnboardingRoot.dataset.state = hub.status || "not_started";
    hubOnboardingRoot.querySelector("[data-hub-onboarding-title]").textContent = hub.required
      ? "Agent Hub에 내 Langflow를 한 번 연결하세요"
      : "Agent Hub 배포 연결이 확인됐습니다";
    hubOnboardingRoot.querySelector("[data-hub-onboarding-message]").textContent = hub.message || "";
    const registration = (app.state.agent_hub || {}).manual_registration || {};
    hubOnboardingRoot.querySelector("[data-hub-endpoint-guide]").textContent = registration.endpoint
      ? `${endpoint.name || "내 Langflow"}의 배포용 URL 사용`
      : "Playground endpoint를 먼저 선택하세요";
    hubOnboardingRoot.querySelector("[data-hub-project-guide]").textContent = registration.project
      ? `${registration.project} 프로젝트 선택`
      : `boi-${employeeId} 프로젝트 선택`;
  };

  const assetKindLabel = (asset) => asset.type === "json" ? "Flow" : "Component";

  const renderHubSelected = () => {
    hubSelectedRoot.replaceChildren();
    const label = document.createElement("span");
    label.textContent = `선택한 자산 · ${app.hubSelected.size}개`;
    hubSelectedRoot.append(label);
    if (!app.hubSelected.size) {
      const empty = document.createElement("p");
      empty.textContent = "아직 선택한 자산이 없습니다.";
      hubSelectedRoot.append(empty);
      return;
    }
    const list = document.createElement("div");
    list.className = "agent-playground-hub-selected-list";
    app.hubSelected.forEach((asset) => {
      const item = document.createElement("span");
      item.className = "agent-playground-hub-selected-item";
      const text = document.createElement("span");
      text.textContent = `${assetKindLabel(asset)} · ${asset.title} · v${asset.version || "미표기"}`;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.setAttribute("aria-label", `${asset.title} 선택 해제`);
      remove.textContent = "×";
      remove.addEventListener("click", () => {
        app.hubSelected.delete(asset.asset_id);
        renderHubAssets();
        renderHubImport();
      });
      item.append(text, remove);
      list.append(item);
    });
    hubSelectedRoot.append(list);
  };

  const renderHubAssets = () => {
    hubAssetsRoot.replaceChildren();
    if (!app.hubAssets.length) {
      const empty = document.createElement("p");
      empty.className = "agent-playground-empty";
      empty.textContent = "조건에 맞는 승인 자산이 없습니다.";
      hubAssetsRoot.append(empty);
      renderHubSelected();
      return;
    }
    app.hubAssets.forEach((asset) => {
      const card = document.createElement("article");
      card.className = "agent-playground-hub-asset";
      card.dataset.selected = app.hubSelected.has(asset.asset_id) ? "true" : "false";
      const head = document.createElement("div");
      const kind = document.createElement("span");
      kind.className = "agent-playground-chip";
      kind.textContent = assetKindLabel(asset);
      const title = document.createElement("strong");
      title.textContent = asset.title || asset.asset_id;
      head.append(kind, title);
      const description = document.createElement("p");
      description.textContent = asset.description || "설명이 등록되지 않았습니다.";
      const meta = document.createElement("small");
      const author = asset.author || {};
      meta.textContent = [
        `v${asset.version || "미표기"}`,
        author.name || author.employee_id || "작성자 미표기",
        asset.min_langflow_version ? `Langflow ${asset.min_langflow_version}+` : "",
      ].filter(Boolean).join(" · ");
      const actions = document.createElement("div");
      const detail = document.createElement("a");
      detail.textContent = "Agent Hub 상세";
      detail.target = "_blank";
      detail.rel = "noopener";
      if (asset.asset_url) detail.href = asset.asset_url;
      else detail.setAttribute("aria-disabled", "true");
      const choose = document.createElement("button");
      choose.type = "button";
      choose.textContent = app.hubSelected.has(asset.asset_id) ? "선택 해제" : "이 자산 사용";
      choose.addEventListener("click", () => {
        if (app.hubSelected.has(asset.asset_id)) app.hubSelected.delete(asset.asset_id);
        else app.hubSelected.set(asset.asset_id, asset);
        app.hubAdoption = null;
        app.hubCandidates = [];
        renderHubAssets();
        renderHubImport();
      });
      actions.append(detail, choose);
      card.append(head, description, meta, actions);
      hubAssetsRoot.append(card);
    });
    renderHubSelected();
  };

  const matchingHubAdoption = () => {
    const adoptions = (app.state && app.state.hub_adoptions) || [];
    return [...adoptions].reverse().find((item) => (
      item.endpoint_id === app.endpointId
      && item.project_id === app.projectId
      && item.status !== "confirmed"
    )) || null;
  };

  const renderHubCandidates = () => {
    hubCandidatesRoot.replaceChildren();
    if (!app.hubCandidates.length) return;
    const heading = document.createElement("strong");
    heading.textContent = "배포 후 새로 생기거나 변경된 Flow";
    hubCandidatesRoot.append(heading);
    app.hubCandidates.forEach((candidate) => {
      const card = document.createElement("article");
      const detail = document.createElement("div");
      const name = document.createElement("strong");
      name.textContent = candidate.name || candidate.flow_id;
      const meta = document.createElement("small");
      meta.textContent = `${candidate.change_kind === "updated" ? "기존 Flow에 Component 반영" : "새 Flow"} · ${candidate.flow_id}`;
      detail.append(name, meta);
      const confirm = document.createElement("button");
      confirm.type = "button";
      confirm.textContent = "이 exact Flow 가져오기";
      confirm.addEventListener("click", async () => {
        if (!app.hubAdoption) return;
        confirm.disabled = true;
        try {
          const payload = await request(
            `/api/agent-playground/agent-hub/adoptions/${encodeURIComponent(app.hubAdoption.adoption_id)}/confirm`,
            {
              method: "POST",
              body: JSON.stringify({ flow_id: candidate.flow_id }),
            },
          );
          hubAdoptionOutput.textContent = `가져오기 완료 · exact Flow ${payload.deployment.flow_id} · 이제 Flow별 검증을 진행하세요.`;
          showToast("Agent Hub 자산의 출처와 exact Flow를 함께 고정했습니다.", "success");
          app.hubAdoption = null;
          app.hubCandidates = [];
          await loadState();
          await loadFlows();
          app.flow = app.flows.find((flow) => flow.flow_id === candidate.flow_id) || null;
          renderFlows();
          renderSelectedFlow();
          renderHubImport();
        } catch (error) {
          hubAdoptionOutput.textContent = error.message;
          showToast(`Flow 가져오기 실패: ${error.message}`, "error");
        } finally {
          confirm.disabled = false;
        }
      });
      card.append(detail, confirm);
      hubCandidatesRoot.append(card);
    });
  };

  const componentStatus = (asset, flow) => {
    const componentId = String(asset.asset_id || "");
    if ((flow.executed_component_ids || []).includes(componentId)) return "실행 검증됨";
    if ((flow.connected_component_ids || []).includes(componentId)) return "연결됨";
    const graphItem = ((flow.component_graph || {}).items || [])
      .find((item) => String(item.asset_id || "") === componentId);
    if (graphItem && graphItem.deployed) return "연결 필요";
    return "배포됨";
  };

  const renderComponentStatus = () => {
    componentStatusRoot.replaceChildren();
    const flow = app.flow || {};
    const components = (flow.source_assets || []).filter((asset) => asset && asset.type === "py");
    if (!components.length) return;
    const heading = document.createElement("strong");
    heading.textContent = "Component 실행 상태";
    componentStatusRoot.append(heading);
    components.forEach((asset) => {
      const row = document.createElement("article");
      const copy = document.createElement("div");
      const name = document.createElement("strong");
      name.textContent = asset.title || asset.asset_id;
      const state = document.createElement("span");
      const status = componentStatus(asset, flow);
      state.textContent = status;
      state.dataset.state = status === "실행 검증됨"
        ? "executed"
        : status === "연결됨"
          ? "connected"
          : status === "연결 필요"
            ? "required"
            : "deployed";
      copy.append(name, state);
      const action = document.createElement("button");
      action.type = "button";
      action.textContent = "Agent 자리에 연결";
      action.disabled = !["배포됨", "연결 필요"].includes(status) || !flow.adoption_id;
      action.addEventListener("click", async () => {
        action.disabled = true;
        try {
          const result = await request(
            `/api/agent-playground/agent-hub/adoptions/${encodeURIComponent(flow.adoption_id)}/compose`,
            {
              method: "POST",
              body: JSON.stringify({
                flow_id: flow.flow_id,
                component_asset_id: asset.asset_id,
                replace_agent_slot: true,
              }),
            },
          );
          if (result.status === "manual_required") {
            hubAdoptionOutput.textContent = `자동 연결 불가 · ${result.reason} · Langflow Canvas에서 포트를 확인하세요.`;
            if (result.langflow_canvas_url) window.open(result.langflow_canvas_url, "_blank", "noopener");
            showToast("Component 포트가 명확하지 않아 자동 연결하지 않았습니다.", "error");
          } else {
            hubAdoptionOutput.textContent = `연결 완료 · checksum ${result.live_checksum}`;
            showToast("Component를 agent_slot 실행 경로에 연결했습니다. 이제 runtime 검증이 필요합니다.", "success");
          }
          await loadState();
          await loadFlows();
        } catch (error) {
          showToast(`Component 연결 실패: ${error.message}`, "error");
        } finally {
          renderComponentStatus();
        }
      });
      row.append(copy, action);
      componentStatusRoot.append(row);
    });
  };

  const renderHubMode = () => {
    root.querySelectorAll("[data-hub-mode]").forEach((button) => {
      const active = button.dataset.hubMode === app.hubMode;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
    });
    root.querySelectorAll("[data-hub-mode-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.hubModePanel !== app.hubMode;
    });
  };

  const renderHubImport = () => {
    const editable = Boolean((app.state && app.state.capabilities || {}).can_edit);
    const canBegin = editable && app.endpointId && app.projectId && app.hubSelected.size > 0;
    hubBeginButton.disabled = !canBegin || Boolean(app.hubAdoption);
    hubDiscoverButton.disabled = !app.hubAdoption;
    const primary = [...app.hubSelected.values()].find((asset) => asset.type === "json")
      || [...app.hubSelected.values()][0];
    const deployUrl = primary && primary.asset_url
      ? primary.asset_url
      : (app.state && app.state.onboarding || {}).agent_hub_url || root.dataset.agentHubUrl || "";
    if (app.hubAdoption && deployUrl) {
      hubDeployLink.href = deployUrl;
      hubDeployLink.removeAttribute("aria-disabled");
    } else {
      hubDeployLink.removeAttribute("href");
      hubDeployLink.setAttribute("aria-disabled", "true");
    }
    if (!app.endpointId || !app.projectId) {
      hubAdoptionOutput.textContent = "Endpoint와 Project를 고른 뒤 승인 자산을 선택하세요.";
    } else if (app.hubAdoption) {
      const count = (app.hubAdoption.source_assets || []).length;
      hubAdoptionOutput.textContent = `배포 준비 완료 · 자산 ${count}개 · Agent Hub 배포 후 결과를 확인하세요.`;
    } else if (app.hubSelected.size) {
      hubAdoptionOutput.textContent = "선택한 자산의 작성자·버전과 현재 Flow 상태를 배포 준비에서 고정합니다.";
    } else {
      hubAdoptionOutput.textContent = "Agent Hub에서 승인된 Flow 또는 Component를 검색해 선택하세요.";
    }
    root.querySelector("[data-hub-own-flow]").textContent = app.flow
      ? app.flow.name || "선택한 Flow"
      : "먼저 Flow를 선택하세요";
    const ownReady = Boolean(app.flow && app.endpointId && app.projectId);
    hubOwnDownload.disabled = !ownReady;
    hubOwnRefresh.disabled = !app.endpointId || !app.projectId;
    if (ownReady) {
      hubOwnOpen.href = (app.state.onboarding || {}).agent_hub_url || root.dataset.agentHubUrl || "";
      hubOwnOpen.removeAttribute("aria-disabled");
    } else {
      hubOwnOpen.removeAttribute("href");
      hubOwnOpen.setAttribute("aria-disabled", "true");
    }
    renderHubMode();
    renderJourney();
    renderHubSelected();
    renderHubCandidates();
    renderComponentStatus();
  };

  const loadTasks = async () => {
    if (app.tasksLoaded || !taskSelect) return;
    app.tasksLoaded = true;
    const current = taskSelect.value;
    taskSelect.innerHTML = '<option value="">내 Task를 불러오는 중…</option>';
    try {
      const payload = await request("/api/agents/boi-wiki/inbox?status=open&limit=50");
      const rows = [...(payload.items || [])];
      (payload.groups || []).forEach((group) => {
        (group.items || []).forEach((item) => rows.push(item));
      });
      const seen = new Set();
      app.tasks = rows.filter((item) => {
        const taskRef = String(item.task_ref || item.task_id || "");
        if (!taskRef || seen.has(taskRef)) return false;
        seen.add(taskRef);
        return true;
      });
      taskSelect.innerHTML = '<option value="">일반 Wiki 질문 · Task 없음</option>';
      app.tasks.forEach((item) => {
        const option = document.createElement("option");
        option.value = item.task_ref || item.task_id;
        const display = item.display || {};
        const brief = item.brief || item.item_brief || {};
        option.textContent = (
          brief.event_or_stage
          || display.title
          || item.summary
          || option.value
        );
        taskSelect.append(option);
      });
      taskSelect.value = current;
    } catch (error) {
      taskSelect.innerHTML = '<option value="">Task 조회 실패 · 일반 질문으로 실행</option>';
      showToast(`내 Task 조회 실패: ${error.message}`, "error");
    }
  };

  const selectedTaskRef = (data = null) => {
    const selected = String((data ? data.get("task_ref") : taskSelect && taskSelect.value) || "").trim();
    const manual = String((data ? data.get("manual_task_ref") : root.querySelector("[name='manual_task_ref']")?.value) || "").trim();
    return selected || manual;
  };

  const searchHubAssets = async () => {
    const data = new FormData(hubSearchForm);
    hubAssetsRoot.innerHTML = '<p class="agent-playground-empty">Agent Hub 승인 카탈로그를 조회하는 중입니다.</p>';
    try {
      const query = new URLSearchParams({
        search: String(data.get("search") || ""),
        asset_type: String(data.get("asset_type") || ""),
        limit: "50",
      });
      const payload = await request(`/api/agent-playground/agent-hub/assets?${query.toString()}`);
      app.hubAssets = payload.items || [];
      renderHubAssets();
    } catch (error) {
      hubAssetsRoot.innerHTML = `<p class="agent-playground-empty">${escapeText(error.message)}</p>`;
      showToast(`Agent Hub 자산 조회 실패: ${error.message}`, "error");
    }
  };

  const renderOnboarding = () => {
    if (!app.state) return;
    const onboarding = selectedOnboarding();
    const showGuide = app.guideForced || onboarding.required;
    onboardingRoot.hidden = !showGuide;
    workbenchOnly.forEach((element) => { element.hidden = showGuide; });
    root.querySelector("[data-reopen-onboarding]").hidden = showGuide || onboarding.required;
    const stepLabels = {
      complete: "완료",
      current: "진행",
      pending: "대기",
      error: "확인 필요",
    };
    (onboarding.steps || []).forEach((step) => {
      const item = root.querySelector(`[data-onboarding-step="${step.id}"]`);
      if (!item) return;
      item.dataset.state = step.state;
      item.querySelector("[data-onboarding-step-message]").textContent = step.message || "";
      item.querySelector("[data-onboarding-step-state]").textContent = stepLabels[step.state] || step.state;
    });
    const activeStep = onboarding.current_step === "complete" ? "flow" : onboarding.current_step || "connection";
    root.querySelectorAll("[data-onboarding-stage]").forEach((stage) => {
      stage.hidden = stage.dataset.onboardingStage !== activeStep;
    });
    root.querySelector("[data-onboarding-auth]").textContent = `${app.state.identity.auth_source} · ${app.state.identity.display_name}`;
    root.querySelector("[data-onboarding-roles]").textContent = (app.state.identity.roles || []).join(", ") || "조회";

    const guide = root.querySelector("[data-onboarding-user-guide]");
    guide.href = (app.state.onboarding || {}).user_guide_url || guide.href;
    const settings = root.querySelector("[data-open-langflow-settings]");
    const settingsUrl = (app.state.onboarding || {}).langflow_settings_url || "";
    if (settingsUrl) {
      settings.href = settingsUrl;
      settings.removeAttribute("aria-disabled");
    } else {
      settings.removeAttribute("href");
      settings.setAttribute("aria-disabled", "true");
    }
    const connectionForm = root.querySelector("[data-onboarding-connection-form]");
    const endpoint = selectedEndpoint();
    if (!connectionForm.elements.base_url.value) {
      connectionForm.elements.base_url.value = (
        (endpoint && (endpoint.base_url || endpoint.endpoint))
        || (app.state.onboarding || {}).langflow_deploy_url
        || ""
      );
    }
    if (endpoint && !connectionForm.elements.name.value) {
      connectionForm.elements.name.value = endpoint.name || "내 Langflow";
    }
    connectionForm.elements.api_key.required = !endpoint || !endpoint.has_api_key;
    connectionForm.elements.api_key.placeholder = endpoint && endpoint.has_api_key
      ? "비워두면 저장된 Key를 유지합니다"
      : "저장 후에는 다시 표시하지 않습니다";

    const setup = selectedSetup() || {};
    const canonical = setup.canonical_flow || {};
    root.querySelector("[data-onboarding-flow-name]").textContent = canonical.name || "BoI Wiki Agent Loop";
    root.querySelector("[data-onboarding-flow-detail]").textContent = canonical.id
      ? `preview 통과 · ${canonical.version || "1.1.0"}`
      : "기준 Flow 확인 중";
    const openLangflow = root.querySelector("[data-onboarding-open-langflow]");
    if (canonical.flow_url) {
      openLangflow.href = canonical.flow_url;
      openLangflow.removeAttribute("aria-disabled");
    } else {
      openLangflow.removeAttribute("href");
      openLangflow.setAttribute("aria-disabled", "true");
    }
    const error = root.querySelector("[data-onboarding-error]");
    error.hidden = onboarding.status !== "error";
    error.textContent = onboarding.last_error ? `준비를 이어가지 못했습니다: ${onboarding.last_error}` : "";
  };

  const renderEndpointList = () => {
    const endpoints = (app.state && app.state.endpoints) || [];
    endpointList.replaceChildren();
    if (!endpoints.length) {
      const empty = document.createElement("p");
      empty.className = "agent-playground-empty";
      empty.textContent = "아직 등록한 Langflow endpoint가 없습니다.";
      endpointList.append(empty);
    }
    endpoints.forEach((endpoint) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "agent-playground-endpoint-item";
      button.dataset.endpointId = endpoint.endpoint_id;
      button.dataset.active = endpoint.endpoint_id === app.endpointId ? "true" : "false";
      const title = document.createElement("strong");
      title.textContent = endpoint.name || "Langflow";
      const meta = document.createElement("span");
      meta.textContent = endpoint.base_url || endpoint.endpoint || "";
      const state = document.createElement("small");
      state.textContent = `${statusLabel[endpoint.status] || endpoint.status || "저장됨"} · Langflow ${endpoint.version || "미확인"}`;
      button.append(title, meta, state);
      button.addEventListener("click", () => selectEndpoint(endpoint.endpoint_id));
      endpointList.append(button);
    });
    const limit = document.createElement("small");
    limit.className = "agent-playground-limit";
    limit.textContent = `${endpoints.length} / ${(app.state && app.state.endpoint_limit) || 5}`;
    endpointList.append(limit);

    endpointSelect.innerHTML = '<option value="">선택하세요</option>';
    endpoints.forEach((endpoint) => {
      const option = document.createElement("option");
      option.value = endpoint.endpoint_id;
      option.textContent = `${endpoint.name || "Langflow"} · ${endpoint.version || "미확인"}`;
      endpointSelect.append(option);
    });
    endpointSelect.value = app.endpointId;
  };

  const renderEndpointSummary = () => {
    const endpoint = selectedEndpoint();
    endpointSummary.replaceChildren();
    if (!endpoint) {
      endpointSummary.innerHTML = '<p class="agent-playground-empty">왼쪽에서 endpoint를 선택하거나 새로 추가하세요.</p>';
      setStatus("connection", "", "endpoint를 선택하세요.");
      return;
    }
    const card = document.createElement("article");
    card.className = "agent-playground-connection-summary";
    const heading = document.createElement("div");
    heading.innerHTML = `<p class="eyebrow">${escapeText(endpoint.status || "saved")}</p><h4>${escapeText(endpoint.name || "Langflow")}</h4>`;
    const url = document.createElement("p");
    url.textContent = endpoint.base_url || endpoint.endpoint || "";
    const facts = document.createElement("dl");
    facts.innerHTML = `
      <div><dt>Langflow</dt><dd>${escapeText(endpoint.version || "미확인")}</dd></div>
      <div><dt>사용자</dt><dd>${escapeText(endpoint.langflow_username || "미확인")}</dd></div>
      <div><dt>API Key</dt><dd>${endpoint.has_api_key ? `저장됨 · ${escapeText(endpoint.api_key_fingerprint || "")}` : "없음"}</dd></div>
      <div><dt>최근 확인</dt><dd>${endpoint.last_checked_at ? new Date(endpoint.last_checked_at).toLocaleString("ko-KR") : "아직 없음"}</dd></div>
    `;
    const actions = document.createElement("div");
    actions.className = "agent-playground-form-actions";
    const edit = document.createElement("button");
    edit.type = "button";
    edit.textContent = "수정";
    edit.addEventListener("click", () => openEndpointForm(endpoint));
    actions.append(edit);
    card.append(heading, url, facts, actions);
    endpointSummary.append(card);
    setStatus(
      "connection",
      endpoint.status || "connected",
      endpoint.status === "connected" ? `${endpoint.name} · ${endpoint.langflow_username}` : (endpoint.last_error || "연결을 다시 시험하세요."),
    );
    root.querySelector("[data-advanced-endpoint]").textContent = endpoint.base_url || endpoint.endpoint || "연결 전";
    root.querySelector("[data-advanced-user]").textContent = endpoint.langflow_username || "연결 전";
    root.querySelector("[data-test-saved]").disabled = false;
    root.querySelector("[data-deactivate-endpoint]").disabled = false;
    root.querySelector("[data-rotate-credential]").disabled = false;
    root.querySelector("[data-bootstrap]").disabled = endpoint.status !== "connected";
  };

  const openEndpointForm = (endpoint = null) => {
    endpointSummary.hidden = true;
    endpointForm.hidden = false;
    endpointForm.reset();
    endpointForm.elements.endpoint_id.value = endpoint ? endpoint.endpoint_id : "";
    endpointForm.elements.name.value = endpoint ? endpoint.name || "" : "";
    endpointForm.elements.base_url.value = endpoint ? endpoint.base_url || endpoint.endpoint || "" : "";
    endpointForm.elements.api_key.required = !endpoint;
    endpointForm.querySelector("[data-endpoint-test-output]").textContent = "";
  };

  const closeEndpointForm = () => {
    endpointForm.hidden = true;
    endpointSummary.hidden = false;
  };

  const loadState = async () => {
    app.state = await request("/api/agent-playground");
    root.querySelector("[data-auth-source]").textContent = `${app.state.identity.auth_source} · ${app.state.identity.display_name}`;
    if (!app.endpointId) {
      const deepLinkedEndpoint = !app.deepLinkApplied && (app.state.endpoints || [])
        .find((endpoint) => endpoint.endpoint_id === app.deepLink.endpointId);
      app.endpointId = (deepLinkedEndpoint && deepLinkedEndpoint.endpoint_id)
        || app.state.default_endpoint_id
        || (app.state.endpoints[0] || {}).endpoint_id
        || "";
    }
    if (!selectedEndpoint()) app.endpointId = "";
    if (!app.journeyInitialized) {
      const suggested = ((app.state.journey || {}).next_action || {}).stage
        || (app.state.journey || {}).current_stage;
      if (["create", "test", "hub", "action"].includes(app.deepLink.stage)) {
        app.activeStep = app.deepLink.stage;
      } else if (["create", "test", "hub", "action"].includes(suggested)) {
        app.activeStep = suggested;
      }
      app.journeyInitialized = true;
    }
    renderEndpointList();
    renderEndpointSummary();
    renderOnboarding();
    if (!app.hubAdoption) app.hubAdoption = matchingHubAdoption();
    if (app.hubAdoption) app.hubCandidates = app.hubAdoption.candidates || [];
    renderHubImport();
    const teamSelect = root.querySelector("[data-action-team]");
    teamSelect.innerHTML = '<option value="">팀을 선택하세요</option>';
    (app.state.identity.teams || []).forEach((team) => {
      const option = document.createElement("option");
      option.value = team;
      option.textContent = team;
      teamSelect.append(option);
    });
    if (app.endpointId && !selectedOnboarding().required) await loadProjects(false);
    setWorkbenchStep(app.activeStep);
    renderJourney();
  };

  const selectEndpoint = async (endpointId) => {
    app.endpointId = endpointId;
    app.projectId = "";
    app.flow = null;
    app.hubAdoption = null;
    app.hubCandidates = [];
    renderEndpointList();
    renderEndpointSummary();
    renderOnboarding();
    renderHubImport();
    if (!selectedOnboarding().required) await loadProjects(true);
    renderJourney();
  };

  const loadProjects = async (selectPersonal = false) => {
    if (!app.endpointId) return;
    projectSelect.disabled = true;
    projectSelect.innerHTML = '<option value="">불러오는 중…</option>';
    try {
      const payload = await request(`/api/agent-playground/endpoints/${encodeURIComponent(app.endpointId)}/projects`);
      app.projects = payload.projects || [];
      projectSelect.innerHTML = '<option value="">프로젝트 선택</option>';
      app.projects.forEach((project) => {
        const option = document.createElement("option");
        option.value = project.id;
        option.textContent = project.name;
        projectSelect.append(option);
      });
      projectSelect.disabled = false;
      const personal = app.projects.find((project) => project.name === `boi-${employeeId}`);
      const setup = selectedSetup();
      const known = setup && setup.project ? setup.project.id : "";
      const selectedProjectStillExists = app.projects.some((project) => project.id === app.projectId);
      const deepLinkedProject = !app.deepLinkApplied && (
        app.deepLink.endpointId === app.endpointId
        && app.projects.find((project) => project.id === app.deepLink.projectId)
      );
      if (deepLinkedProject) {
        app.projectId = deepLinkedProject.id;
        app.flow = null;
      } else if (selectPersonal || !selectedProjectStillExists) {
        app.projectId = (personal && personal.id) || known || "";
        app.flow = null;
      }
      projectSelect.value = app.projectId;
      setStatus("project", app.projectId ? "connected" : "", app.projectId ? (personal && personal.name) || "선택한 프로젝트" : "프로젝트를 선택하세요.");
      if (!app.hubAdoption) app.hubAdoption = matchingHubAdoption();
      if (app.hubAdoption) app.hubCandidates = app.hubAdoption.candidates || [];
      renderHubImport();
      if (app.projectId) await loadFlows();
      renderJourney();
    } catch (error) {
      projectSelect.innerHTML = '<option value="">조회 실패</option>';
      setStatus("project", "error", error.message);
      showToast(`프로젝트 조회 실패: ${error.message}`, "error");
    }
  };

  const renderFlows = () => {
    flowList.replaceChildren();
    const query = app.flowFilter.trim().toLowerCase();
    const filtered = app.flows.filter((flow) => (
      !query
      || `${flow.name || ""} ${flow.flow_id || ""} ${flow.validation_status || ""}`.toLowerCase().includes(query)
    ));
    if (!filtered.length) {
      flowList.innerHTML = '<p class="agent-playground-empty">이 프로젝트에 Flow가 없습니다. Agent Hub 배포 후 새 Flow 찾기를 누르세요.</p>';
      return;
    }
    const canonicalName = (app.state.canonical_asset || {}).name || "BoI Wiki Agent Loop";
    const isHistory = (flow) => (
      flow.validation_status === "blocked"
      || flow.checksum_state === "drifted"
      || flow.validation_status === "drifted"
    );
    const current = filtered.filter((flow) => !isHistory(flow));
    const history = filtered.filter(isHistory);
    const groups = [
      ["내 기준 Flow", current.filter((flow) => flow.name === canonicalName)],
      ["Agent Hub에서 가져온 Flow", current.filter((flow) => flow.name !== canonicalName && flow.deployment_id)],
      ["최근 작업", current.filter((flow) => flow.name !== canonicalName && !flow.deployment_id)],
    ];
    const appendFlowGroup = (parent, title, flows) => {
      if (!flows.length) return;
      const section = document.createElement("section");
      section.className = "agent-playground-flow-group";
      const heading = document.createElement("h4");
      heading.textContent = title;
      section.append(heading);
      flows.forEach((flow) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "agent-playground-flow-item";
        button.dataset.flowId = flow.flow_id;
        button.dataset.active = app.flow && app.flow.flow_id === flow.flow_id ? "true" : "false";
        const label = document.createElement("span");
        const linkedAction = (flow.linked_actions || [])[0];
        const flowKind = flow.deployment_id ? "Agent Hub 배포 Flow" : "내 프로젝트 Flow";
        const actionLabel = linkedAction ? ` · Action 연결됨: ${linkedAction.title}` : "";
        label.innerHTML = `<strong>${escapeText(flow.name || "이름 없는 Flow")}</strong><small>${escapeText(flowKind + actionLabel)}</small>`;
        const status = document.createElement("em");
        const displayStatus = flow.checksum_state === "drifted"
          ? "drifted"
          : flow.validation_status || "discovered";
        status.textContent = statusLabel[displayStatus] || displayStatus;
        status.dataset.state = displayStatus;
        button.append(label, status);
        button.addEventListener("click", () => {
          app.flow = flow;
          renderFlows();
          renderSelectedFlow();
        });
        section.append(button);
      });
      parent.append(section);
    };
    groups.forEach(([title, flows]) => appendFlowGroup(flowList, title, flows));
    if (history.length) {
      const historyDetails = document.createElement("details");
      historyDetails.className = "agent-playground-flow-history";
      historyDetails.open = Boolean(query);
      const summary = document.createElement("summary");
      summary.textContent = `문제 있는 Flow와 기록 · ${history.length}개`;
      historyDetails.append(summary);
      appendFlowGroup(historyDetails, "재검증 또는 정리가 필요한 Flow", history);
      flowList.append(historyDetails);
    }
  };

  const loadFlows = async () => {
    if (!app.endpointId || !app.projectId) return;
    root.querySelector("[data-refresh-flows]").disabled = true;
    try {
      const payload = await request(
        `/api/agent-playground/endpoints/${encodeURIComponent(app.endpointId)}/projects/${encodeURIComponent(app.projectId)}/flows`,
      );
      app.flows = payload.flows || [];
      if (app.flow) app.flow = app.flows.find((flow) => flow.flow_id === app.flow.flow_id) || null;
      if (
        !app.deepLinkApplied
        &&
        app.deepLink.flowId
        && app.deepLink.endpointId === app.endpointId
        && app.deepLink.projectId === app.projectId
      ) {
        app.flow = app.flows.find((flow) => flow.flow_id === app.deepLink.flowId) || app.flow;
        app.deepLinkApplied = Boolean(
          app.flow && app.flow.flow_id === app.deepLink.flowId,
        );
      }
      renderFlows();
      renderSelectedFlow();
    } catch (error) {
      flowList.innerHTML = `<p class="agent-playground-empty">${escapeText(error.message)}</p>`;
      showToast(`Flow 조회 실패: ${error.message}`, "error");
    } finally {
      root.querySelector("[data-refresh-flows]").disabled = false;
    }
  };

  const renderSelectedFlow = () => {
    const flow = app.flow;
    const flowSummary = flow && flow.flow_summary ? flow.flow_summary : {};
    root.querySelector("[data-selected-flow-name]").textContent = flow ? flow.name || flow.flow_id : "Flow를 선택하세요";
    root.querySelector("[data-selected-flow-description]").textContent = flow
      ? flowSummary.description || "실제 Langflow graph에서 확인한 Component 실행 경로입니다."
      : "Flow를 선택하면 실제 Component 실행 경로와 연결된 Action을 보여줍니다.";
    const pipeline = root.querySelector("[data-selected-flow-pipeline]");
    pipeline.replaceChildren();
    const nodes = (flowSummary.nodes || []).filter((node) => node.on_execution_path);
    if (nodes.length) {
      const list = document.createElement("ol");
      nodes.forEach((node) => {
        const item = document.createElement("li");
        item.dataset.role = node.role || "component";
        const title = document.createElement("strong");
        title.textContent = node.label || node.component_kind || "Component";
        const kind = document.createElement("small");
        kind.textContent = node.component_kind || "";
        item.append(title, kind);
        list.append(item);
      });
      pipeline.append(list);
    } else {
      pipeline.innerHTML = '<p class="agent-playground-empty">표시할 Flow 실행 경로가 없습니다.</p>';
    }
    const actionSection = root.querySelector("[data-selected-flow-actions]");
    const actionList = root.querySelector("[data-selected-flow-action-list]");
    const linkedActions = flow ? flow.linked_actions || [] : [];
    actionSection.hidden = !linkedActions.length;
    actionList.replaceChildren();
    linkedActions.forEach((action) => {
      const link = document.createElement("a");
      link.href = action.url;
      link.textContent = `${action.title} · ${action.status === "published" ? "카탈로그 등록됨" : action.status}`;
      actionList.append(link);
    });
    root.querySelector("[data-selected-flow-id]").textContent = flow ? flow.flow_id : "—";
    root.querySelector("[data-selected-flow-checksum]").textContent = flow && flow.artifact_checksum ? flow.artifact_checksum : "검증 전";
    const selectedStatus = flow
      ? (flow.checksum_state === "drifted" ? "drifted" : flow.validation_status || "discovered")
      : "discovered";
    const selectedStatusChip = root.querySelector("[data-selected-flow-status]");
    selectedStatusChip.dataset.state = selectedStatus;
    selectedStatusChip.textContent = statusLabel[selectedStatus] || selectedStatus;
    const ready = Boolean(flow);
    root.querySelector("[data-download-artifact]").disabled = !ready;
    root.querySelector("[data-record-deployment]").disabled = !ready || !(app.state.capabilities || {}).can_edit;
    root.querySelector("[data-validate-flow]").disabled = !ready || !(app.state.capabilities || {}).can_edit || !flow.deployment_id;
    const createActionButton = root.querySelector("[data-create-action]");
    createActionButton.disabled = !ready || flow.validation_status !== "action_ready" || !flow.deployment_id;
    createActionButton.dataset.deploymentId = flow && flow.deployment_id ? flow.deployment_id : "";
    createActionButton.dataset.flowId = flow && flow.flow_id ? flow.flow_id : "";
    const actionDraftLink = root.querySelector("[data-open-action-draft]");
    const actionDraftId = flow && flow.action_draft_id ? flow.action_draft_id : "";
    if (actionDraftId) {
      actionDraftLink.href = `/actions/drafts/${encodeURIComponent(actionDraftId)}`;
      actionDraftLink.hidden = false;
    } else {
      actionDraftLink.removeAttribute("href");
      actionDraftLink.hidden = true;
    }
    root.querySelector("[data-test-form] button[type='submit']").disabled = !ready;
    setStatus("flow", flow ? flow.validation_status || "discovered" : "", flow ? flow.flow_id : "Flow를 선택하세요.");
    setStatus(
      "action",
      flow && flow.validation_status === "action_linked" ? "action_linked" : "",
      flow && flow.validation_status === "action_ready" ? "Action 연결 가능" : "전체 검증 통과 후 활성화됩니다.",
    );
    const endpoint = selectedEndpoint();
    const open = root.querySelector("[data-open-langflow]");
    if (endpoint && app.projectId) {
      const browserBase = (
        (app.state.onboarding || {}).langflow_external_url
        || endpoint.base_url
        || endpoint.endpoint
        || ""
      ).replace(/\/$/, "");
      open.href = flow
        ? `${browserBase}/flow/${encodeURIComponent(flow.flow_id)}/folder/${encodeURIComponent(app.projectId)}`
        : `${browserBase}/all/folder/${encodeURIComponent(app.projectId)}`;
      open.target = "_blank";
      open.rel = "noopener";
      open.removeAttribute("aria-disabled");
    } else {
      open.removeAttribute("href");
      open.setAttribute("aria-disabled", "true");
    }
    renderComponentStatus();
    renderHubImport();
    setWorkbenchStep(app.activeStep);
  };

  const deepField = (value, name) => {
    if (!value || typeof value !== "object") return undefined;
    if (Object.prototype.hasOwnProperty.call(value, name)) return value[name];
    for (const child of Object.values(value)) {
      const found = deepField(child, name);
      if (found !== undefined) return found;
    }
    return undefined;
  };

  const splitList = (value) => String(value || "")
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);

  const renderResult = (result) => {
    const summary = root.querySelector("[data-result-summary]");
    const taskContext = deepField(result, "task_context") || {};
    const ontology = deepField(result, "ontology_relationships") || [];
    const sources = deepField(result, "source_references") || [];
    const grounding = deepField(result, "grounding_status") || "응답 계약에서 확인되지 않음";
    const draft = deepField(result, "draft_reference") || "";
    const missing = taskContext.missing_evidence || [];
    const ontologyRows = Array.isArray(ontology) ? ontology : [];
    const ontologyTypes = [...new Set(ontologyRows.map((item) => item && (item.type || item.relation_type)).filter(Boolean))];
    const provenanced = ontologyRows.filter((item) => item && item.provenance).length;
    summary.innerHTML = `
      <article><span>업무 맥락</span><strong>${escapeText(taskContext.profile || deepField(result, "context_profile") || "일반 지식 조회")}</strong><p>${escapeText(taskContext.task_ref || "일반 Wiki 질문")}</p></article>
      <article><span>Ontology 관계</span><strong>${ontologyRows.length}개 관계</strong><p>${ontologyRows.length ? `${escapeText(ontologyTypes.join(", ") || "typed relation")} · provenance ${provenanced}개` : "관계 없음 · 문서 근거로 보완"}</p></article>
      <article><span>문서 근거</span><strong>${Array.isArray(sources) ? sources.length : 0}개</strong><p>${escapeText(grounding)}</p></article>
      <article><span>부족 근거와 저장</span><strong>${Array.isArray(missing) ? missing.length : 0}개 부족</strong><p>${draft ? `내 초안 ${escapeText(draft)}` : "미리보기 · Wiki 변경 없음"}</p></article>
    `;
  };

  root.querySelector("[data-reopen-onboarding]").addEventListener("click", () => {
    app.guideForced = true;
    renderOnboarding();
    onboardingRoot.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  root.querySelector("[data-onboarding-finish]").addEventListener("click", async () => {
    app.guideForced = false;
    renderOnboarding();
    if (app.endpointId) await loadProjects(true);
    root.querySelector(".agent-playground-actions").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  const onboardingConnectionForm = root.querySelector("[data-onboarding-connection-form]");
  const onboardingConnectionOutput = root.querySelector("[data-onboarding-connection-output]");

  root.querySelector("[data-onboarding-test-connection]").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    const data = new FormData(onboardingConnectionForm);
    const apiKey = String(data.get("api_key") || "");
    button.disabled = true;
    onboardingConnectionOutput.textContent = "Langflow 1.11과 현재 사용자 소유권을 확인하는 중입니다.";
    try {
      let payload;
      if (apiKey) {
        payload = await request("/api/agent-playground/endpoints/test", {
          method: "POST",
          body: JSON.stringify({ base_url: data.get("base_url"), api_key: apiKey }),
        });
      } else if (app.endpointId) {
        payload = await request(
          `/api/agent-playground/endpoints/${encodeURIComponent(app.endpointId)}/test`,
          { method: "POST", body: "{}" },
        );
      } else {
        throw new Error("Langflow에서 발급한 API Key를 입력해주세요.");
      }
      const connection = payload.connection || payload.endpoint || {};
      onboardingConnectionOutput.textContent = `연결 성공 · Langflow ${connection.version || "1.11"} · ${connection.langflow_username || employeeId}`;
      showToast("Langflow 연결과 현재 사용자 소유권을 확인했습니다.", "success");
    } catch (error) {
      onboardingConnectionOutput.textContent = error.message;
      showToast(`연결 시험 실패: ${error.message}`, "error");
    } finally {
      button.disabled = false;
    }
  });

  onboardingConnectionForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(onboardingConnectionForm);
    const endpoint = selectedEndpoint();
    const apiKey = String(data.get("api_key") || "");
    const body = {
      name: data.get("name"),
      base_url: data.get("base_url"),
      make_default: true,
    };
    if (apiKey) body.api_key = apiKey;
    if (!endpoint && !apiKey) {
      onboardingConnectionOutput.textContent = "Langflow에서 발급한 API Key를 입력해주세요.";
      return;
    }
    const submit = onboardingConnectionForm.querySelector("button[type='submit']");
    submit.disabled = true;
    onboardingConnectionOutput.textContent = "키 원문을 노출하지 않고 안전하게 연결하는 중입니다.";
    try {
      const payload = await request(
        endpoint
          ? `/api/agent-playground/endpoints/${encodeURIComponent(endpoint.endpoint_id)}`
          : "/api/agent-playground/endpoints",
        {
          method: endpoint ? "PATCH" : "POST",
          body: JSON.stringify(body),
        },
      );
      const nextEndpointId = payload.endpoint.endpoint_id;
      if (app.endpointId !== nextEndpointId) {
        app.projectId = "";
        app.flow = null;
      }
      app.endpointId = nextEndpointId;
      onboardingConnectionForm.elements.api_key.value = "";
      onboardingConnectionOutput.textContent = `저장 완료 · fingerprint ${payload.endpoint.api_key_fingerprint || ""}`;
      showToast("Langflow 연결 키를 저장했습니다. 이제 BoI 지식 연결을 자동 준비합니다.", "success");
      await loadState();
    } catch (error) {
      onboardingConnectionOutput.textContent = error.message;
      showToast(`endpoint 저장 실패: ${error.message}`, "error");
    } finally {
      submit.disabled = false;
    }
  });

  root.querySelector("[data-onboarding-bootstrap]").addEventListener("click", async (event) => {
    if (!app.endpointId) return;
    const button = event.currentTarget;
    const output = root.querySelector("[data-onboarding-bootstrap-output]");
    button.disabled = true;
    output.textContent = "개인 프로젝트 → BoI 지식 연결 → 기준 Flow → preview 순서로 준비합니다.";
    try {
      await request("/api/agent-playground/bootstrap", {
        method: "POST",
        body: JSON.stringify({ endpoint_id: app.endpointId }),
      });
      app.guideForced = true;
      output.textContent = "준비 완료. API Key나 PAT 원문은 화면과 Flow에 남지 않았습니다.";
      showToast(`boi-${employeeId} 프로젝트와 기준 Flow preview를 준비했습니다.`, "success");
      await loadState();
    } catch (error) {
      output.textContent = error.message;
      showToast(`개인 공간 준비 실패: ${error.message}`, "error");
      await loadState();
    } finally {
      button.disabled = false;
    }
  });

  endpointSelect.addEventListener("change", () => selectEndpoint(endpointSelect.value));
  projectSelect.addEventListener("change", async () => {
    app.projectId = projectSelect.value;
    app.flow = null;
    app.hubAdoption = matchingHubAdoption();
    app.hubCandidates = app.hubAdoption ? app.hubAdoption.candidates || [] : [];
    renderHubImport();
    if (app.projectId) await loadFlows();
  });
  hubSearchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await searchHubAssets();
  });
  hubBeginButton.addEventListener("click", async () => {
    if (!app.endpointId || !app.projectId || !app.hubSelected.size) return;
    hubBeginButton.disabled = true;
    try {
      const payload = await request("/api/agent-playground/agent-hub/adoptions", {
        method: "POST",
        body: JSON.stringify({
          endpoint_id: app.endpointId,
          project_id: app.projectId,
          asset_ids: [...app.hubSelected.keys()],
          validation_profile: hubProfileSelect.value,
        }),
      });
      app.hubAdoption = payload.adoption;
      app.hubCandidates = [];
      renderHubImport();
      showToast("원작자·버전과 배포 전 Flow 목록을 고정했습니다.", "success");
    } catch (error) {
      hubAdoptionOutput.textContent = error.message;
      showToast(`Agent Hub 자산 준비 실패: ${error.message}`, "error");
    } finally {
      renderHubImport();
    }
  });
  hubDiscoverButton.addEventListener("click", async () => {
    if (!app.hubAdoption) return;
    hubDiscoverButton.disabled = true;
    hubAdoptionOutput.textContent = "현재 프로젝트에서 새로 생기거나 변경된 exact Flow를 찾는 중입니다.";
    try {
      const payload = await request(
        `/api/agent-playground/agent-hub/adoptions/${encodeURIComponent(app.hubAdoption.adoption_id)}/discover`,
        { method: "POST", body: "{}" },
      );
      app.hubCandidates = payload.candidates || [];
      hubAdoptionOutput.textContent = app.hubCandidates.length
        ? `${app.hubCandidates.length}개 Flow 후보를 찾았습니다. 배포한 exact Flow를 선택하세요.`
        : "아직 변경된 Flow가 없습니다. Agent Hub 배포를 마친 뒤 다시 확인하세요.";
      renderHubCandidates();
    } catch (error) {
      hubAdoptionOutput.textContent = error.message;
      showToast(`배포 결과 조회 실패: ${error.message}`, "error");
    } finally {
      hubDiscoverButton.disabled = false;
    }
  });
  root.querySelector("[data-new-endpoint]").addEventListener("click", () => openEndpointForm());
  root.querySelector("[data-cancel-endpoint]").addEventListener("click", closeEndpointForm);
  root.querySelector("[data-flow-filter]").addEventListener("input", (event) => {
    app.flowFilter = event.currentTarget.value || "";
    renderFlows();
  });
  root.querySelectorAll("[data-workbench-step]").forEach((button) => {
    button.addEventListener("click", () => {
      setWorkbenchStep(button.dataset.workbenchStep, { scroll: true });
    });
  });
  root.querySelectorAll("[data-hub-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      app.hubMode = button.dataset.hubMode || "own";
      renderHubMode();
      if (app.hubMode === "shared" && !app.hubAssets.length) searchHubAssets();
    });
  });
  nextActionButton.addEventListener("click", () => {
    const actionId = nextActionButton.dataset.actionId || "";
    const targetStep = nextActionButton.dataset.targetStep || app.activeStep;
    if (actionId === "open_langflow") {
      const open = root.querySelector("[data-open-langflow]");
      if (open.href) {
        window.open(open.href, "_blank", "noopener");
        return;
      }
    }
    if (actionId === "open_action_draft") {
      const draft = root.querySelector("[data-open-action-draft]");
      if (!draft.hidden && draft.href) {
        window.location.href = draft.href;
        return;
      }
    }
    if (actionId === "open_agent_hub" && app.activeStep === "hub" && hubOwnOpen.href) {
      hubOwnOpen.click();
      return;
    }
    if (["create", "test", "hub", "action"].includes(targetStep)) {
      setWorkbenchStep(targetStep, { scroll: true });
    }
  });
  hubOwnDownload.addEventListener("click", () => {
    root.querySelector("[data-download-artifact]").click();
  });
  hubOwnOpen.addEventListener("click", () => {
    app.ownFlowSnapshot = new Set(app.flows.map((flow) => flow.flow_id));
    showToast("현재 Flow 목록을 기준으로 기록했습니다. Agent Hub 배포 후 결과를 확인하세요.", "success");
  });
  hubOwnRefresh.addEventListener("click", async () => {
    const before = new Set(app.ownFlowSnapshot);
    await loadFlows();
    const candidates = app.flows.filter((flow) => !before.has(flow.flow_id));
    if (candidates.length === 1) {
      app.flow = candidates[0];
      renderFlows();
      renderSelectedFlow();
      showToast("Agent Hub에서 배포된 새 Flow를 찾았습니다. 배포 결과로 연결하세요.", "success");
    } else if (candidates.length > 1) {
      showToast(`${candidates.length}개 새 Flow를 찾았습니다. 배포한 Flow를 선택하세요.`, "success");
    } else {
      showToast("새 Flow를 아직 찾지 못했습니다. Agent Hub 배포를 마친 뒤 다시 확인하세요.", "error");
    }
  });
  root.querySelectorAll("[name='action_scope']").forEach((radio) => {
    radio.addEventListener("change", () => {
      root.querySelector("[data-action-team-wrap]").hidden = (
        root.querySelector("[name='action_scope']:checked").value !== "team"
      );
    });
  });

  root.querySelector("[data-test-unsaved]").addEventListener("click", async () => {
    const data = new FormData(endpointForm);
    const output = endpointForm.querySelector("[data-endpoint-test-output]");
    if (!data.get("api_key")) {
      output.textContent = "저장 전 연결 시험에는 API Key를 입력해야 합니다.";
      return;
    }
    try {
      const payload = await request("/api/agent-playground/endpoints/test", {
        method: "POST",
        body: JSON.stringify({ base_url: data.get("base_url"), api_key: data.get("api_key") }),
      });
      output.textContent = `연결 성공 · Langflow ${payload.connection.version} · ${payload.connection.langflow_username}`;
      showToast("Langflow 1.11과 API Key 소유자를 확인했습니다.", "success");
    } catch (error) {
      output.textContent = error.message;
      showToast(`연결 시험 실패: ${error.message}`, "error");
    }
  });

  endpointForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(endpointForm);
    const endpointId = String(data.get("endpoint_id") || "");
    const body = {
      name: data.get("name"),
      base_url: data.get("base_url"),
      make_default: !app.endpointId,
    };
    if (data.get("api_key")) body.api_key = data.get("api_key");
    try {
      const payload = await request(
        endpointId ? `/api/agent-playground/endpoints/${encodeURIComponent(endpointId)}` : "/api/agent-playground/endpoints",
        { method: endpointId ? "PATCH" : "POST", body: JSON.stringify(body) },
      );
      const nextEndpointId = payload.endpoint.endpoint_id;
      if (app.endpointId !== nextEndpointId) {
        app.projectId = "";
        app.flow = null;
      }
      app.endpointId = nextEndpointId;
      closeEndpointForm();
      showToast(endpointId ? "endpoint 연결을 갱신했습니다." : "endpoint를 등록했습니다.", "success");
      await loadState();
    } catch (error) {
      showToast(`endpoint 저장 실패: ${error.message}`, "error");
    }
  });

  root.querySelector("[data-test-saved]").addEventListener("click", async () => {
    if (!app.endpointId) return;
    try {
      await request(`/api/agent-playground/endpoints/${encodeURIComponent(app.endpointId)}/test`, { method: "POST", body: "{}" });
      showToast("endpoint 연결 시험을 통과했습니다.", "success");
      await loadState();
    } catch (error) {
      showToast(`연결 시험 실패: ${error.message}`, "error");
      await loadState();
    }
  });

  root.querySelector("[data-deactivate-endpoint]").addEventListener("click", async () => {
    if (!app.endpointId) return;
    try {
      const payload = await request(`/api/agent-playground/endpoints/${encodeURIComponent(app.endpointId)}`, { method: "DELETE" });
      showToast(payload.deactivated ? "배포 참조가 있어 endpoint를 비활성화했습니다." : "endpoint를 삭제했습니다.", "success");
      app.endpointId = "";
      await loadState();
    } catch (error) {
      showToast(`연결 해제 실패: ${error.message}`, "error");
    }
  });

  root.querySelector("[data-bootstrap]").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      await request("/api/agent-playground/bootstrap", {
        method: "POST",
        body: JSON.stringify({ endpoint_id: app.endpointId }),
      });
      showToast(`boi-${employeeId} 프로젝트와 기준 Flow를 준비했습니다.`, "success");
      await loadState();
    } catch (error) {
      showToast(`개인 공간 준비 실패: ${error.message}`, "error");
    } finally {
      button.disabled = false;
    }
  });

  root.querySelector("[data-refresh-flows]").addEventListener("click", loadFlows);

  root.querySelector("[data-download-artifact]").addEventListener("click", () => {
    if (!app.flow) return;
    window.location.href = withIdentity(
      `/api/agent-playground/flows/${encodeURIComponent(app.flow.flow_id)}/artifact?endpoint_id=${encodeURIComponent(app.endpointId)}&project_id=${encodeURIComponent(app.projectId)}`,
    );
  });

  root.querySelector("[data-record-deployment]").addEventListener("click", async () => {
    if (!app.flow) return;
    try {
      const payload = await request("/api/agent-playground/deployments", {
        method: "POST",
        body: JSON.stringify({
          endpoint_id: app.endpointId,
          project_id: app.projectId,
          flow_id: app.flow.flow_id,
          endpoint_name: app.flow.endpoint_name || "",
          asset_version: (app.state.canonical_asset || {}).version || "1.1.0",
          artifact_checksum: app.flow.artifact_checksum || "",
        }),
      });
      showToast(`배포 Flow ${payload.deployment.flow_id}를 exact ID로 연결했습니다.`, "success");
      await loadState();
      await loadFlows();
    } catch (error) {
      showToast(`배포 결과 연결 실패: ${error.message}`, "error");
    }
  });

  root.querySelector("[data-validate-flow]").addEventListener("click", async (event) => {
    if (!app.flow) return;
    const taskRef = selectedTaskRef();
    if (!taskRef) {
      showToast("Flow 전체 검증에는 ACL로 확인된 실제 내 Task를 선택해야 합니다.", "error");
      return;
    }
    const button = event.currentTarget;
    button.disabled = true;
    try {
      const payload = await request(`/api/agent-playground/flows/${encodeURIComponent(app.flow.flow_id)}/validate`, {
        method: "POST",
        body: JSON.stringify({
          endpoint_id: app.endpointId,
          project_id: app.projectId,
          artifact_version: (app.state.canonical_asset || {}).version || "1.1.0",
          artifact_checksum: app.flow.artifact_checksum || "",
          task_ref: taskRef,
        }),
      });
      showToast(payload.ok ? "Flow 검증을 통과해 Action 연결 준비가 됐습니다." : `Flow가 차단되었습니다: ${payload.failure_reason}`, payload.ok ? "success" : "error");
      renderResult(payload.task || payload.runtime || {});
      root.querySelector("[data-test-output]").textContent = JSON.stringify(payload, null, 2);
      await loadState();
      await loadFlows();
    } catch (error) {
      showToast(`Flow 검증 실패: ${error.message}`, "error");
    } finally {
      button.disabled = false;
    }
  });

  root.querySelector("[data-test-form]").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!app.flow) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const button = form.querySelector("button[type='submit']");
    button.disabled = true;
    try {
      const payload = await request(`/api/agent-playground/flows/${encodeURIComponent(app.flow.flow_id)}/test`, {
        method: "POST",
        body: JSON.stringify({
          endpoint_id: app.endpointId,
          project_id: app.projectId,
          question: data.get("question"),
          business_context: data.get("business_context"),
          task_ref: selectedTaskRef(data),
          page_ref: data.get("page_ref"),
          sop_ref: data.get("sop_ref"),
          sop_stage: data.get("sop_stage"),
          event_ref: data.get("event_ref"),
          action_ref: data.get("action_ref"),
          prior_results: splitList(data.get("prior_results")).map((summary) => ({ summary })),
          required_evidence: splitList(data.get("required_evidence")),
          missing_evidence: splitList(data.get("missing_evidence")),
          save_mode: data.get("save_mode"),
          title: data.get("title"),
        }),
      });
      renderResult(payload.result);
      root.querySelector("[data-test-output]").textContent = JSON.stringify(payload.result, null, 2);
      showToast("선택한 Flow의 runtime 테스트를 마쳤습니다.", "success");
      await loadState();
    } catch (error) {
      root.querySelector("[data-test-output]").textContent = error.message;
      showToast(`Flow 테스트 실패: ${error.message}`, "error");
    } finally {
      button.disabled = false;
    }
  });

  root.querySelector("[data-create-action]").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    const deploymentId = String(button.dataset.deploymentId || "");
    if (!deploymentId) {
      showToast("선택한 exact Flow의 배포 참조를 다시 확인하세요.", "error");
      return;
    }
    const scope = root.querySelector("[name='action_scope']:checked").value;
    const teamId = scope === "team" ? root.querySelector("[data-action-team]").value : "";
    if (scope === "team" && !teamId) {
      showToast("팀에서 사용할 Action은 HCP 팀을 선택해야 합니다.", "error");
      return;
    }
    try {
      const payload = await request(
        `/api/agent-playground/deployments/${encodeURIComponent(deploymentId)}/action-draft`,
        {
          method: "POST",
          body: JSON.stringify({ scope, team_id: teamId }),
        },
      );
      showToast(`Action 등록 초안 ${payload.draft.draft_id}을 만들었습니다.`, "success");
      const actionDraftLink = root.querySelector("[data-open-action-draft]");
      actionDraftLink.href = payload.draft_url;
      actionDraftLink.hidden = false;
      await loadState();
      await loadFlows();
    } catch (error) {
      showToast(`Action 연결 실패: ${error.message}`, "error");
    }
  });

  root.querySelector("[data-rotate-credential]").addEventListener("click", async () => {
    if (!app.endpointId) return;
    const confirmed = window.confirm(
      "BoI 지식 연결 키를 새로 발급할까요?\n\n기존 키는 즉시 폐기되며 Langflow의 BOI_WIKI_PAT가 새 키로 교체됩니다.",
    );
    if (!confirmed) return;
    try {
      await request("/api/agent-playground/rotate-credential", {
        method: "POST",
        body: JSON.stringify({ endpoint_id: app.endpointId, reason: "Agent Playground UI credential reissue" }),
      });
      showToast("BoI 지식 연결 키를 새로 발급하고 Langflow 연결을 갱신했습니다.", "success");
      await loadState();
    } catch (error) {
      showToast(`BoI 지식 연결 키 재발급 실패: ${error.message}`, "error");
    }
  });

  loadState().catch((error) => showToast(`Playground 상태 확인 실패: ${error.message}`, "error"));
})();
