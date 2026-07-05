(() => {
  const page = document.querySelector(".registration-page");
  const form = document.querySelector(".registration-form");
  if (!page || !form) return;

  const result = form.querySelector(".registration-result");
  const picker = form.querySelector(".registration-picker");
  const agentSuggestions = document.querySelector(".registration-agent-suggestions");
  const employeeId = page.dataset.employeeId || "";
  let currentDraftId = "";
  let currentPlan = null;
  const wizardSteps = ["context", "stages", "execution", "entry", "review"];
  let currentStep = "context";
  let draftSessionId = "";
  let autosaveTimer = null;
  let workflowStages = [];
  let selectedStageId = "";
  let dataLakeArtifacts = [];
  const selectedLinkState = {};
  const draftSuggestionTimers = {};
  const draftSuggestionSnapshots = {};
  const autosaveKey = `boi:sop-registration:${employeeId}:${window.location.pathname}`;
  const pickerTargets = {
    event_mode: {reuse: ["event_types", "linked_event_types"]},
    sop_mode: {reuse: ["sops", "linked_sop_ref"]},
    action_mode: {reuse: ["actions", "linked_action_keys"]},
  };

  const listFields = new Set([
    "steps",
    "evidence_requirements",
    "payload_fields",
    "input_fields",
    "output_fields",
    "linked_event_types",
    "linked_action_keys",
    "required_evidence_context",
    "payload_fields",
  ]);
  const connectorListFields = new Set([
    "connector_config.idempotency_key_fields",
  ]);
  const jsonFields = new Set([
    "schedule_config",
    "work_context_model",
    "workflow_model",
    "workflow_tasks",
    "workflow_stages",
    "okf_materialization_plan",
    "data_lake_artifacts",
    "event_producer_adapter_plan",
    "event_source_config.payload_mapping",
    "event_source_config.sample_payload",
    "event_source_config.auth_policy",
    "event_source_config.health_check",
  ]);
  const weekdayLabels = {
    MON: "월요일",
    TUE: "화요일",
    WED: "수요일",
    THU: "목요일",
    FRI: "금요일",
    SAT: "토요일",
    SUN: "일요일",
  };

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

  const splitList = (value) => String(value || "")
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);

  function humanizeTechnicalValue(value) {
    return String(value || "")
      .replace(/\.v\d+$/i, "")
      .replace(/^boi:[^:]+:/i, "")
      .split(/[._:/-]+/)
      .filter(Boolean)
      .map((part) => part && part.toUpperCase() === part ? part : part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ")
      .trim() || "선택 항목";
  }

  function valuesForField(name) {
    const field = formField(name);
    if (!field) return [];
    return listFields.has(name) ? splitList(field.value) : (field.value ? [field.value] : []);
  }

  function setNested(payload, key, value) {
    const parts = String(key || "").split(".").filter(Boolean);
    if (parts.length <= 1) {
      payload[key] = value;
      return;
    }
    let cursor = payload;
    for (const part of parts.slice(0, -1)) {
      if (!cursor[part] || typeof cursor[part] !== "object" || Array.isArray(cursor[part])) {
        cursor[part] = {};
      }
      cursor = cursor[part];
    }
    cursor[parts[parts.length - 1]] = value;
  }

  function normalizeTime(value) {
    const text = String(value || "09:00").trim();
    const match = text.match(/^(\d{1,2}):(\d{2})$/);
    if (!match) return "09:00";
    const hour = Math.min(Math.max(Number(match[1]), 0), 23);
    const minute = Math.min(Math.max(Number(match[2]), 0), 59);
    return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
  }

  function cronFromScheduleConfig(config) {
    const time = normalizeTime(config.time);
    const [hour, minute] = time.split(":");
    if (config.repeat_type === "daily") return `${Number(minute)} ${Number(hour)} * * *`;
    if (config.repeat_type === "weekly") {
      const weekdays = Array.isArray(config.weekdays) && config.weekdays.length ? config.weekdays : ["MON"];
      return `${Number(minute)} ${Number(hour)} * * ${weekdays.join(",")}`;
    }
    if (config.repeat_type === "monthly") {
      const day = Math.min(Math.max(Number(config.month_day || 1), 1), 31);
      return `${Number(minute)} ${Number(hour)} ${day} * *`;
    }
    return "";
  }

  function scheduleSummary(config) {
    const time = normalizeTime(config.time);
    if (config.repeat_type === "daily") return `매일 ${time}에 Event 초안이 만들어집니다.`;
    if (config.repeat_type === "weekly") {
      const weekdays = Array.isArray(config.weekdays) && config.weekdays.length ? config.weekdays : ["MON"];
      return `매주 ${weekdays.map((day) => weekdayLabels[day] || day).join(", ")} ${time}에 Event 초안이 만들어집니다.`;
    }
    if (config.repeat_type === "monthly") {
      const day = Math.min(Math.max(Number(config.month_day || 1), 1), 31);
      return `매월 ${day}일 ${time}에 Event 초안이 만들어집니다.`;
    }
    if (config.repeat_type === "once" && config.once_at) return `${config.once_at.replace("T", " ")}에 Event 초안이 만들어집니다.`;
    return "직접 설정한 일정으로 Event 초안이 만들어집니다.";
  }

  function currentScheduleConfig() {
    const repeatType = form.querySelector('[data-schedule-field="repeat_type"]')?.value || "weekly";
    const weekdays = Array.from(form.querySelectorAll("[data-schedule-weekday]:checked")).map((item) => item.value);
    return {
      repeat_type: repeatType,
      time: normalizeTime(form.querySelector('[data-schedule-field="time"]')?.value || "09:00"),
      weekdays: weekdays.length ? weekdays : ["MON"],
      month_day: form.querySelector('[data-schedule-field="month_day"]')?.value || "1",
      once_at: form.querySelector('[data-schedule-field="once_at"]')?.value || "",
      timezone: form.querySelector('[data-schedule-field="timezone"]')?.value || "Asia/Seoul",
    };
  }

  function updateScheduleBuilder() {
    const eventMode = formField("event_mode")?.value || "skip";
    const repeatType = form.querySelector('[data-schedule-field="repeat_type"]')?.value || "weekly";
    form.querySelectorAll("[data-schedule-control]").forEach((control) => {
      const kind = control.dataset.scheduleControl || "";
      let visible = eventMode === "schedule";
      if (kind === "weekdays") visible = visible && repeatType === "weekly";
      if (kind === "month_day") visible = visible && repeatType === "monthly";
      if (kind === "once_at") visible = visible && repeatType === "once";
      if (kind === "time") visible = visible && repeatType !== "once" && repeatType !== "custom";
      control.hidden = !visible;
    });
    const scheduleConfigField = formField("schedule_config");
    const scheduleTextField = formField("schedule_text");
    const cronField = formField("cron");
    const preview = form.querySelector("[data-schedule-preview]");
    if (eventMode !== "schedule") {
      if (scheduleConfigField) scheduleConfigField.value = "";
      if (scheduleTextField) scheduleTextField.value = "";
      if (cronField && !form.querySelector("[data-schedule-cron-direct]")?.value) cronField.value = "";
      return;
    }
    const config = currentScheduleConfig();
    const summary = scheduleSummary(config);
    if (preview) preview.textContent = summary;
    if (scheduleConfigField) scheduleConfigField.value = JSON.stringify(config);
    if (scheduleTextField) scheduleTextField.value = summary;
    if (cronField) {
      const directCron = form.querySelector("[data-schedule-cron-direct]")?.value || "";
      cronField.value = repeatType === "custom" ? directCron : cronFromScheduleConfig(config);
    }
  }

  function selectedConnectorKind() {
    return form.querySelector('input[name="connector_kind"]')?.value || "";
  }

  function setConnectorKind(connectorKind) {
    const normalized = connectorKind || "manual";
    const input = form.querySelector('input[name="connector_kind"]');
    if (input) input.value = normalized;
    form.querySelectorAll("[data-connector-kind]").forEach((button) => {
      const selected = button.dataset.connectorKind === normalized;
      button.classList.toggle("selected", selected);
      button.setAttribute("aria-pressed", selected ? "true" : "false");
    });
    form.querySelectorAll("[data-connector-panel]").forEach((panel) => {
      panel.classList.toggle("active", panel.dataset.connectorPanel === normalized);
    });
    form.querySelectorAll("[data-skill-action-picker]").forEach((panel) => {
      panel.hidden = normalized !== "skill";
    });
  }

  function selectedEventSourceKind() {
    return form.querySelector('input[name="event_source_kind"]:checked')?.value || "webhook";
  }

  function updateEventSourcePanels() {
    const selected = selectedEventSourceKind();
    form.querySelectorAll("[data-event-source-panel]").forEach((panel) => {
      const allowed = String(panel.dataset.eventSourcePanel || "").split(/\s+/).filter(Boolean);
      const active = allowed.includes(selected);
      panel.hidden = !active;
      panel.querySelectorAll("input, select, textarea, button").forEach((control) => {
        control.disabled = !active;
      });
    });
  }

  function isSopRegistration() {
    return form.dataset.apiUrl?.includes("/api/sop-registration/");
  }

  function recommendationContextText() {
    return [
      formField("raw_request")?.value || "",
      formField("title")?.value || "",
      formField("business_goal")?.value || "",
      formField("work_target")?.value || "",
      formField("work_situation")?.value || "",
      formField("decision_question")?.value || "",
      formField("required_evidence_context")?.value || "",
      formField("expected_result")?.value || "",
      formField("knowledge_update_goal")?.value || "",
    ].map((value) => String(value || "").trim()).filter(Boolean).join(" ");
  }

  function hasRecommendationInput() {
    const text = recommendationContextText();
    const compact = text.replace(/\s+/g, "");
    const tokens = text.split(/[^0-9A-Za-z가-힣_.:-]+/).filter(Boolean);
    return compact.length >= 8 || tokens.length >= 2;
  }

  function updateRecommendationControls() {
    const ready = hasRecommendationInput();
    document.querySelectorAll("[data-recommendation-gated]").forEach((button) => {
      button.toggleAttribute("disabled", !ready);
    });
    document.querySelectorAll("[data-recommendation-hint]").forEach((hint) => {
      hint.textContent = ready
        ? "입력한 설명으로 기존 Event/SOP/Action 후보와 다듬기 제안을 만듭니다. 적용은 각 섹션에서 직접 선택합니다."
        : "먼저 어떤 업무인지 적으면 기존 Event/SOP/Action 후보와 다듬기 제안을 만들 수 있습니다.";
    });
    updateSectionRefineControls();
    updateWizardNavButtons();
  }

  function sectionRefineInputs(section) {
    if (section === "event") return ["event_display_name", "payload_fields"];
    if (section === "sop") return ["steps", "evidence_requirements"];
    if (section === "action") return ["action_display_name", "input_fields", "output_fields"];
    return [];
  }

  function hasSectionRefineInput(section) {
    const directInput = sectionRefineInputs(section).some((name) => {
      const field = formField(name);
      return Boolean(String(field?.value || "").trim());
    });
    if (directInput) return true;
    if (section !== "action") return false;
    const activeConnectorKind = selectedConnectorKind();
    return Array.from(form.querySelectorAll("[data-connector-field]"))
      .filter((field) => field.dataset.connectorField === activeConnectorKind)
      .some((field) => Boolean(String(field.value || "").trim()));
  }

  function updateSectionRefineControls() {
    const hints = {
      event: "업무 시점 이름을 먼저 적어주세요.",
      sop: "주요 단계나 필요한 근거를 먼저 적어주세요.",
      action: "Action 이름이나 실행 방식을 먼저 입력해주세요.",
    };
    document.querySelectorAll("[data-section-refine]").forEach((button) => {
      const section = button.dataset.sectionRefine || "";
      const ready = hasSectionRefineInput(section);
      button.toggleAttribute("disabled", !ready);
      const hint = form.querySelector(`[data-section-refine-hint="${section}"]`);
      if (hint) {
        hint.textContent = ready
          ? "입력한 초안을 기준으로 추천 미리보기를 만들 수 있습니다."
          : hints[section] || "초안을 먼저 입력해주세요.";
      }
    });
  }

  function hideDraftSuggestion(section) {
    clearDraftSuggestionTimer(section);
    const card = form.querySelector(`[data-draft-suggestion="${section}"]`);
    if (card) {
      card.hidden = true;
      card.innerHTML = "";
    }
  }

  function setFlowStage(step) {
    currentStep = wizardSteps.includes(step) ? step : "context";
    form.querySelectorAll("[data-step-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.stepPanel !== currentStep;
    });
    document.querySelectorAll("[data-registration-step]").forEach((item) => {
      item.classList.toggle("active", item.dataset.registrationStep === currentStep);
      item.classList.toggle("complete", stepOrderIndex(item.dataset.registrationStep) < stepOrderIndex(currentStep));
    });
    updateWizardNavButtons();
  }

  function stepOrderIndex(step) {
    return wizardSteps.indexOf(step);
  }

  function moveWizard(delta) {
    const index = Math.max(0, stepOrderIndex(currentStep));
    const nextIndex = Math.min(Math.max(index + delta, 0), wizardSteps.length - 1);
    setFlowStage(wizardSteps[nextIndex]);
    scheduleAutosave();
  }

  function updateWizardNavButtons() {
    const index = Math.max(0, stepOrderIndex(currentStep));
    form.querySelectorAll("[data-wizard-nav='prev']").forEach((button) => {
      button.disabled = index <= 0;
    });
    form.querySelectorAll("[data-wizard-nav='next']").forEach((button) => {
      const blockedForContext = currentStep === "context" && !hasRecommendationInput();
      button.disabled = index >= wizardSteps.length - 1 || blockedForContext;
    });
  }

  function buildWorkContextModel() {
    return {
      work_target: String(formField("work_target")?.value || "").trim(),
      work_situation: String(formField("work_situation")?.value || "").trim(),
      decision_question: String(formField("decision_question")?.value || "").trim(),
      required_evidence: splitList(formField("required_evidence_context")?.value || ""),
      expected_result: String(formField("expected_result")?.value || "").trim(),
      knowledge_update_goal: String(formField("knowledge_update_goal")?.value || "").trim(),
    };
  }

  function buildWorkflowModel() {
    return {
      title: String(formField("title")?.value || "").trim(),
      description: String(formField("raw_request")?.value || "").trim(),
      business_goal: String(formField("business_goal")?.value || "").trim(),
      work_context: buildWorkContextModel(),
      task_count: workflowStages.length,
      measurement_policy: "runtime_trace",
      minimum_save_contract: "workflow_title_or_description_plus_one_task",
    };
  }

  const executionModeLabels = {
    manual: "Manual",
    copilot: "Copilot",
    autopilot: "Autopilot",
  };

  function normalizeExecutionMode(value) {
    const mode = String(value || "").toLowerCase();
    return ["manual", "copilot", "autopilot"].includes(mode) ? mode : "manual";
  }

  function normalizeCopilotSource(value, mode) {
    const source = String(value || "").toLowerCase();
    if (["internal", "external", "mixed", "unknown"].includes(source)) return source;
    return mode === "copilot" ? "unknown" : "";
  }

  function taskDetailStatus(stage) {
    if (!stage || !String(stage.stage_goal || "").trim()) return "상세 미정";
    if (stage.execution_mode === "autopilot" && (!stage.verification_policy || !stage.fallback_owner)) return "검증 필요";
    if (!Array.isArray(stage.required_evidence) || !stage.required_evidence.length) return "상세 미정";
    return "기본 설정";
  }

  function taskTatBadge(stage) {
    const target = String(stage?.tat_target || "").trim();
    const baseline = String(stage?.baseline_tat || "").trim();
    if (target && baseline) return `목표 ${target} · 기준 ${baseline}`;
    if (target) return `목표 ${target}`;
    if (baseline) return `기준 ${baseline}`;
    return "실측 전";
  }

  function workflowTasks() {
    return workflowStages.map((stage, index) => {
      const executionMode = normalizeExecutionMode(stage.execution_mode);
      const copilotSource = normalizeCopilotSource(stage.copilot_source, executionMode);
      return {
        ...stage,
        task_id: stage.task_id || stage.stage_id || `task-${index + 1}`,
        task_name: stage.task_name || stage.stage_name || `Task ${index + 1}`,
        execution_mode: executionMode,
        copilot_source: copilotSource,
        runner_type: stage.runner_type || (executionMode === "manual" ? "human" : executionMode === "autopilot" ? "agent" : "mixed"),
        detail_status: taskDetailStatus(stage),
        tat_badge: taskTatBadge(stage),
      };
    });
  }

  function okfMaterializationPlan() {
    const workContext = buildWorkContextModel();
    let eventProducerAdapterPlan = {};
    try {
      eventProducerAdapterPlan = JSON.parse(formField("event_producer_adapter_plan")?.value || "{}");
    } catch (_error) {
      eventProducerAdapterPlan = {};
    }
    const entryEvent = eventProducerAdapterPlan.target_event_type || splitList(formField("linked_event_types")?.value || "")[0] || formField("event_type")?.value || "";
    return {
      enabled: true,
      summary: "각 단계의 맥락, 판단, 근거, 결과를 BoI 초안과 지식 업데이트 후보로 정리합니다.",
      work_context_seed: workContext,
      workflow_model: buildWorkflowModel(),
      workflow_tasks: workflowTasks(),
      entry_event: entryEvent,
      event_producer_adapter_drafts: eventProducerAdapterPlan.source_kind && eventProducerAdapterPlan.source_kind !== "manual" ? [eventProducerAdapterPlan] : [],
      stage_transition_events: workflowStages.filter((stage) => stage.entry_event || stage.emits_event).map((stage) => ({
        stage_id: stage.stage_id,
        stage_name: stage.stage_name,
        entry_event: stage.entry_event || "",
        emits_event: stage.emits_event || "",
      })),
      event_to_stage_mapping: entryEvent && workflowStages.length ? [{
        event_type: entryEvent,
        stage_id: workflowStages[0].stage_id,
        stage_name: workflowStages[0].stage_name,
        mapping_kind: "entry_event",
      }] : [],
      stage_outputs: workflowStages.map((stage) => ({
        stage_id: stage.stage_id,
        stage_name: stage.stage_name,
        expected_outputs: stage.expected_outputs || [],
        skills: stage.skills || [],
        knowledge_update_policy: stage.knowledge_update_policy || "",
      })),
      knowledge_update_candidates: [
        {kind: "observation_boi", label: "관찰 BoI"},
        {kind: "judgment_boi", label: "판단 BoI"},
        {kind: "result_boi", label: "결과 BoI"},
        {kind: "knowledge_candidate", label: "지식 업데이트 후보"},
      ],
      validation_required: true,
      publish_blocked_until_confirmed: true,
      tat_measurement: {
        enabled: true,
        workflow_tat: "entry_event_to_workflow_complete",
        task_tat: "task_start_to_task_complete_or_next_transition",
        display_values: ["recent", "average", "median", "recent_n"],
      },
      relationships: workflowStages.flatMap((stage) => [
        ...(Array.isArray(stage.required_evidence) ? [{
          kind: "stage_has_evidence",
          stage_id: stage.stage_id,
          targets: stage.required_evidence,
        }] : []),
        ...(Array.isArray(stage.skills) ? stage.skills.map((skill) => ({
          kind: "stage_uses_skill",
          stage_id: stage.stage_id,
          targets: [skill.skill_ref],
        })) : []),
      ]),
    };
  }

  function syncHiddenModels() {
    const workContextField = formField("work_context_model");
    const workflowModelField = formField("workflow_model");
    const tasksField = formField("workflow_tasks");
    const stagesField = formField("workflow_stages");
    const okfField = formField("okf_materialization_plan");
    const sopMode = formField("sop_mode")?.value || "skip";
    const includeStages = ["draft", "lightweight"].includes(sopMode);
    if (workContextField) workContextField.value = JSON.stringify(buildWorkContextModel());
    if (workflowModelField) workflowModelField.value = JSON.stringify(buildWorkflowModel());
    if (tasksField) tasksField.value = includeStages ? JSON.stringify(workflowTasks()) : "";
    if (stagesField) stagesField.value = includeStages ? JSON.stringify(workflowStages) : "";
    if (okfField) okfField.value = includeStages ? JSON.stringify(okfMaterializationPlan()) : "";
    syncArtifactHidden();
    const stepsField = formField("steps");
    if (stepsField && workflowStages.length && includeStages) {
      stepsField.value = workflowStages.map((stage) => stage.stage_name).filter(Boolean).join(", ");
      renderDraftFieldChips("steps");
    }
  }

  function splitStageList(value) {
    return splitList(value).filter(Boolean);
  }

  function makeStage(seed = {}) {
    const index = workflowStages.length + 1;
    const workContext = buildWorkContextModel();
    const name = seed.stage_name || seed.task_name || seed.name || seed.title || `Task ${index}`;
    const executionMode = normalizeExecutionMode(seed.execution_mode || (Array.isArray(seed.skills) && seed.skills.length ? "copilot" : "manual"));
    return {
      stage_id: seed.stage_id || seed.task_id || seed.id || `task-${Date.now().toString(36)}-${index}`,
      stage_name: name,
      stage_goal: seed.stage_goal || seed.goal || `${name} 단계의 목표를 정리합니다.`,
      decision_question: seed.decision_question || workContext.decision_question || "이 단계의 판단 근거가 충분한가?",
      required_evidence: splitStageList(seed.required_evidence || seed.evidence_requirements || workContext.required_evidence || "업무 발생 근거, 판단 근거"),
      actions: Array.isArray(seed.actions) ? seed.actions : [],
      skills: Array.isArray(seed.skills) ? seed.skills : [],
      expected_outputs: splitStageList(seed.expected_outputs || seed.outputs || "단계별 판단 기록 BoI"),
      knowledge_update_policy: seed.knowledge_update_policy || workContext.knowledge_update_goal || "확인한 사실, 판단 이유, 결과를 지식 업데이트 후보로 남긴다.",
      execution_mode: executionMode,
      copilot_source: normalizeCopilotSource(seed.copilot_source, executionMode),
      runner_type: seed.runner_type || (executionMode === "manual" ? "human" : executionMode === "autopilot" ? "agent" : "mixed"),
      approval_policy: seed.approval_policy || (executionMode === "autopilot" ? "policy_required" : "stage_owner_confirmed"),
      verification_policy: seed.verification_policy || "evidence_required",
      fallback_owner: seed.fallback_owner || employeeId,
      tat_target: seed.tat_target || "",
      baseline_tat: seed.baseline_tat || "",
      measurement_policy: seed.measurement_policy || "runtime_trace",
      entry_event: seed.entry_event || "",
      emits_event: seed.emits_event || "",
      next_stage: seed.next_stage || "",
    };
  }

  function ensureWorkflowStages() {
    if (workflowStages.length) return;
    const steps = splitList(formField("steps")?.value || "");
    if (steps.length) workflowStages = steps.map((name) => makeStage({stage_name: name}));
    if (!workflowStages.length) {
      workflowStages = [
        makeStage({stage_name: "첫 Task", stage_goal: "Workflow에서 먼저 처리할 업무 단위를 적습니다.", expected_outputs: ["Task 결과 BoI"]}),
      ];
    }
    selectedStageId = workflowStages[0]?.stage_id || "";
  }

  function selectedStage() {
    return workflowStages.find((stage) => stage.stage_id === selectedStageId) || workflowStages[0] || null;
  }

  function renderStageActions(stage) {
    const target = form.querySelector("[data-stage-actions]");
    if (!target) return;
    const actions = Array.isArray(stage?.actions) ? stage.actions : [];
    const skills = Array.isArray(stage?.skills) ? stage.skills : [];
    const actionHtml = actions.length ? `
      <div class="selected-chip-list">
        ${actions.map((action, index) => `
          <span class="selected-chip">
            <span>${escapeHtml(action.label || action.action_key || "Action")}</span>
            <button type="button" aria-label="Action 연결 삭제" data-stage-action="remove-action" data-action-index="${index}">×</button>
          </span>
        `).join("")}
      </div>
    ` : `<span class="muted">아직 이 단계에 연결된 Action이 없습니다.</span>`;
    const skillHtml = skills.length ? `
      <div class="selected-chip-list">
        ${skills.map((skill, index) => `
          <span class="selected-chip">
            <span>${escapeHtml(skill.display_label || skill.skill_ref || "Skill")}</span>
            <button type="button" aria-label="Skill 연결 삭제" data-stage-action="remove-skill" data-skill-index="${index}">×</button>
          </span>
        `).join("")}
      </div>
    ` : `<span class="muted">아직 이 단계에 연결된 Skill이 없습니다.</span>`;
    target.innerHTML = `
      <strong>이 Task에 연결된 Action</strong>
      ${actionHtml}
      <strong>이 Task에 연결된 Skill</strong>
      ${skillHtml}
    `;
  }

  function renderStageDetail() {
    const detail = form.querySelector("[data-stage-detail]");
    const stage = selectedStage();
    if (!detail || !stage) return;
    detail.hidden = false;
    const title = form.querySelector("[data-stage-detail-title]");
    if (title) title.textContent = `${stage.stage_name || "Task"} 편집`;
    detail.querySelectorAll("[data-stage-field]").forEach((field) => {
      const key = field.dataset.stageField || "";
      const value = stage[key];
      field.value = Array.isArray(value) ? value.join(", ") : String(value || "");
    });
    renderStageActions(stage);
    renderArtifactResults();
  }

  function renderWorkflowStages() {
    const list = form.querySelector("[data-stage-list]");
    if (!list) return;
    ensureWorkflowStages();
    list.innerHTML = workflowStages.map((stage, index) => `
      <button type="button" class="stage-card ${stage.stage_id === selectedStageId ? "selected" : ""}" data-stage-select="${escapeHtml(stage.stage_id)}">
        <span class="stage-index">${index + 1}</span>
        <strong>${escapeHtml(stage.stage_name || `Task ${index + 1}`)}</strong>
        <span>${escapeHtml(stage.stage_goal || stage.decision_question || "Task 목적을 정리하세요.")}</span>
        <small>
          <b>${escapeHtml(executionModeLabels[normalizeExecutionMode(stage.execution_mode)] || "Manual")}</b>
          · ${escapeHtml(taskTatBadge(stage))}
          · ${escapeHtml(taskDetailStatus(stage))}
        </small>
      </button>
    `).join("");
    renderStageDetail();
    syncHiddenModels();
  }

  function updateSelectedStageField(field) {
    const stage = selectedStage();
    if (!stage || !field) return;
    const key = field.dataset.stageField || "";
    if (!key) return;
    const value = field.value || "";
    if (["required_evidence", "expected_outputs"].includes(key)) stage[key] = splitList(value);
    else if (key === "execution_mode") {
      stage[key] = normalizeExecutionMode(value);
      stage.copilot_source = normalizeCopilotSource(stage.copilot_source, stage[key]);
      if (!stage.runner_type || stage.runner_type === "human" || stage.runner_type === "agent" || stage.runner_type === "mixed") {
        stage.runner_type = stage[key] === "manual" ? "human" : stage[key] === "autopilot" ? "agent" : "mixed";
      }
    } else if (key === "copilot_source") stage[key] = normalizeCopilotSource(value, normalizeExecutionMode(stage.execution_mode));
    else stage[key] = value;
    renderWorkflowStages();
    scheduleAutosave();
  }

  function addWorkflowStage(seed = {}) {
    const stage = makeStage(seed);
    workflowStages.push(stage);
    selectedStageId = stage.stage_id;
    renderWorkflowStages();
    scheduleAutosave();
  }

  function removeSelectedWorkflowStage() {
    if (!selectedStageId || workflowStages.length <= 1) return;
    const index = workflowStages.findIndex((stage) => stage.stage_id === selectedStageId);
    workflowStages = workflowStages.filter((stage) => stage.stage_id !== selectedStageId);
    selectedStageId = workflowStages[Math.max(0, index - 1)]?.stage_id || workflowStages[0]?.stage_id || "";
    renderWorkflowStages();
    scheduleAutosave();
  }

  function attachSelectedActionToStage() {
    const stage = selectedStage();
    if (!stage) return;
    const values = valuesForField("linked_action_keys");
    const value = values[values.length - 1] || "";
    if (!value) {
      setResult("warning", "연결할 Action을 먼저 선택하세요", "기존 Action 선택에서 Action을 고른 뒤 단계에 연결할 수 있습니다.");
      return;
    }
    const state = selectedLinkState.linked_action_keys || [];
    const found = state.find((item) => item.value === value) || {};
    stage.actions = Array.isArray(stage.actions) ? stage.actions : [];
    if (!stage.actions.some((action) => action.action_key === value)) {
      stage.actions.push({label: found.label || humanizeTechnicalValue(value), action_key: value, source: "linked_action"});
    }
    renderWorkflowStages();
    scheduleAutosave();
  }

  function attachSelectedSkillToStage() {
    const stage = selectedStage();
    if (!stage) return;
    const value = formField("skill_ref")?.value || "";
    if (!value) {
      setResult("warning", "연결할 Skill을 먼저 선택하세요", "Skill 실행 유형을 고른 뒤 Skill 후보를 선택하면 단계에 연결할 수 있습니다.");
      return;
    }
    const state = selectedLinkState.skill_ref || [];
    const found = state.find((item) => item.value === value) || {};
    stage.skills = Array.isArray(stage.skills) ? stage.skills : [];
    if (!stage.skills.some((skill) => skill.skill_ref === value)) {
      stage.skills.push({
        skill_ref: value,
        display_label: found.label || humanizeTechnicalValue(value),
        invocation_mode: formField("skill_invocation_mode")?.value || "guide_only",
        input_contract: splitList(formField("input_fields")?.value || ""),
        output_artifacts: splitList(formField("output_fields")?.value || ""),
        approval_policy: "stage_owner_confirmed",
        risk_level: formField("risk_level")?.value || "low",
      });
    }
    renderWorkflowStages();
    scheduleAutosave();
  }

  function setPicker(html) {
    if (!picker) return;
    picker.hidden = false;
    picker.innerHTML = html;
    picker.scrollIntoView({block: "nearest", behavior: "smooth"});
  }

  function closePicker() {
    if (!picker) return;
    picker.hidden = true;
    picker.innerHTML = "";
  }

  function inlinePicker(targetField) {
    return targetField ? form.querySelector(`[data-inline-picker="${targetField}"]`) : null;
  }

  function setInlinePicker(targetField, html) {
    const target = inlinePicker(targetField);
    if (!target) {
      setPicker(html);
      return;
    }
    target.innerHTML = html;
  }

  function formField(name) {
    const field = form.elements[name];
    if (!field) return null;
    return field instanceof RadioNodeList ? field[0] : field;
  }

  function updateSelectedLink(name) {
    const output = form.querySelector(`[data-selected-link="${name}"]`);
    if (!output) return;
    const values = valuesForField(name);
    const state = selectedLinkState[name] || [];
    const items = values.map((value) => {
      const found = state.find((item) => item.value === value);
      return found || {value, label: humanizeTechnicalValue(value), technicalLabel: value};
    });
    selectedLinkState[name] = items;
    output.classList.toggle("selected", Boolean(items.length));
    output.innerHTML = items.length ? `
      <div class="selected-chip-list">
        ${items.map((item) => `
          <span class="selected-chip">
            <span>${escapeHtml(item.label || humanizeTechnicalValue(item.value))}</span>
            <button type="button" aria-label="${escapeHtml(item.label || item.value)} 선택 삭제" data-remove-link="${escapeHtml(name)}" data-remove-value="${escapeHtml(item.value)}">×</button>
          </span>
        `).join("")}
      </div>
    ` : "선택 안 됨";
  }

  function rememberSelectedLink(name, value, metadata = {}) {
    if (!name || !value) return;
    const incoming = Array.isArray(value) ? value : splitList(value);
    const current = selectedLinkState[name] || [];
    for (const itemValue of incoming) {
      const item = {
        value: itemValue,
        label: metadata.label || metadata.displayLabel || humanizeTechnicalValue(itemValue),
        description: metadata.description || "",
        technicalLabel: metadata.technicalLabel || itemValue,
      };
      const index = current.findIndex((existing) => existing.value === itemValue);
      if (index >= 0) current[index] = item;
      else current.push(item);
    }
    selectedLinkState[name] = current;
  }

  function removeSelectedLink(name, value) {
    const field = formField(name);
    if (!field) return;
    const values = valuesForField(name).filter((item) => item !== value);
    field.value = listFields.has(name) ? values.join(", ") : (values[0] || "");
    selectedLinkState[name] = (selectedLinkState[name] || []).filter((item) => item.value !== value);
    updateSelectedLink(name);
  }

  function setFieldValue(name, value, metadata = {}) {
    const field = formField(name);
    if (!field) return;
    if (listFields.has(name)) {
      const incoming = Array.isArray(value) ? value : splitList(value);
      const current = splitList(field.value);
      for (const item of incoming) {
        if (item && !current.includes(item)) current.push(item);
      }
      field.value = current.join(", ");
      if (metadata.label || metadata.displayLabel || metadata.technicalLabel) rememberSelectedLink(name, incoming, metadata);
    } else if (jsonFields.has(name)) {
      field.value = typeof value === "string" ? value : JSON.stringify(value || {});
    } else {
      field.value = value;
      if (metadata.label || metadata.displayLabel || metadata.technicalLabel) {
        selectedLinkState[name] = [];
        rememberSelectedLink(name, value, metadata);
      }
    }
    if (name === "schedule_config") {
      let config = {};
      try {
        config = typeof value === "string" ? JSON.parse(value) : value || {};
      } catch (_error) {
        config = {};
      }
      if (config.repeat_type) {
        const repeatField = form.querySelector('[data-schedule-field="repeat_type"]');
        if (repeatField) repeatField.value = config.repeat_type;
      }
      if (config.time) {
        const timeField = form.querySelector('[data-schedule-field="time"]');
        if (timeField) timeField.value = normalizeTime(config.time);
      }
      if (config.month_day) {
        const monthField = form.querySelector('[data-schedule-field="month_day"]');
        if (monthField) monthField.value = config.month_day;
      }
      if (config.once_at) {
        const onceField = form.querySelector('[data-schedule-field="once_at"]');
        if (onceField) onceField.value = config.once_at;
      }
      if (config.timezone) {
        const timezoneField = form.querySelector('[data-schedule-field="timezone"]');
        if (timezoneField) timezoneField.value = config.timezone;
      }
      if (Array.isArray(config.weekdays)) {
        form.querySelectorAll("[data-schedule-weekday]").forEach((box) => {
          box.checked = config.weekdays.includes(box.value);
        });
      }
      updateScheduleBuilder();
    }
    updateSelectedLink(name);
    renderDraftFieldChips(name);
  }

  function syncArtifactHidden() {
    const field = formField("data_lake_artifacts");
    if (field) field.value = JSON.stringify(dataLakeArtifacts);
  }

  function artifactLabel(artifact) {
    return artifact?.filename || artifact?.display_label || artifact?.artifact_id || "Data Lake artifact";
  }

  function currentArtifactTarget(panel) {
    const context = panel?.dataset.artifactContext || "";
    const configuredType = panel?.dataset.artifactTargetType || "";
    if (context === "review") return {target_type: "", target_id: "", context};
    if (configuredType === "workflow_stage" || context === "workflow_stage") {
      const stage = selectedStage();
      return {
        target_type: "workflow_stage",
        target_id: stage?.stage_id || "",
        context,
        stage_id: stage?.stage_id || "",
        stage_name: stage?.stage_name || "",
      };
    }
    const targetType = configuredType || context || "work_context";
    return {
      target_type: targetType,
      target_id: draftSessionId || `${window.location.pathname}${window.location.search}`,
      context,
    };
  }

  function artifactSourceContext(panel) {
    let sourceContext = {};
    const sourceContextField = panel?.querySelector("[data-artifact-source-context]");
    try {
      sourceContext = sourceContextField?.value ? JSON.parse(sourceContextField.value) : {};
    } catch (_error) {
      sourceContext = {note: sourceContextField?.value || ""};
    }
    const target = currentArtifactTarget(panel);
    const role = panel?.querySelector("[data-artifact-role-select]")?.value || panel?.dataset.artifactRole || "evidence";
    const humanNote = panel?.querySelector("[data-artifact-note]")?.value || "";
    return {
      ...sourceContext,
      ...target,
      source: sourceContext.source || "sop_builder",
      attached_from_surface: "sop_builder",
      step: sourceContext.step || target.context || currentStep,
      draft_session_id: draftSessionId || "",
      work_context: buildWorkContextModel(),
      attachment_role: role,
      validation_state: "uploaded",
      human_note: humanNote,
    };
  }

  function artifactMatchesPanel(artifact, panel) {
    const target = currentArtifactTarget(panel);
    if (target.context === "review") return true;
    const sourceContext = artifact?.source_context || {};
    if (target.target_type && sourceContext.target_type !== target.target_type) return false;
    if (target.target_id && sourceContext.target_id !== target.target_id) return false;
    if (target.stage_id && sourceContext.stage_id !== target.stage_id) return false;
    return true;
  }

  function artifactStatusLabel(artifact) {
    const state = artifact?.validation_state || artifact?.profile?.kind || "uploaded";
    const labels = {
      uploaded: "업로드됨",
      profiled: "프로필 생성",
      review_required: "검토 필요",
      verified_evidence: "검증 근거",
      table: "표 샘플",
      json: "JSON 샘플",
      image: "이미지",
      document: "문서",
      text: "텍스트",
      binary: "바이너리",
    };
    return labels[state] || state;
  }

  function renderArtifactResults(message = "") {
    syncArtifactHidden();
    form.querySelectorAll("[data-artifact-results]").forEach((target) => {
      const panel = target.closest("[data-artifact-panel]");
      const artifacts = dataLakeArtifacts.filter((artifact) => artifactMatchesPanel(artifact, panel));
      const html = artifacts.length ? `
        <div class="artifact-chip-list">
          ${artifacts.map((artifact) => `
            <article class="artifact-chip evidence-artifact-card">
              <div>
                <strong>${escapeHtml(artifactLabel(artifact))}</strong>
                <span>${escapeHtml(artifactStatusLabel(artifact))} · ${escapeHtml(artifact.attachment_role || "evidence")} · ${escapeHtml(String(artifact.size_bytes || 0))} bytes</span>
                <small>${escapeHtml(artifact.human_note || artifact.source_context?.human_note || "원본은 BoI 본문 대신 stable URL과 profile로 연결됩니다.")}</small>
                <details>
                  <summary>기술 세부정보</summary>
                  <code>${escapeHtml(artifact.artifact_id || "")}</code>
                  <span>${escapeHtml(artifact.sha256 || "")}</span>
                </details>
              </div>
              <div class="artifact-card-actions">
                <a href="${escapeHtml(artifact.download_url || "#")}" target="_blank" rel="noreferrer">원본 보기</a>
                <button type="button" data-artifact-remove="${escapeHtml(artifact.artifact_id || "")}">삭제</button>
              </div>
            </article>
          `).join("")}
        </div>
      ` : `<p class="muted">${escapeHtml(message || "아직 연결된 Data Lake artifact가 없습니다.")}</p>`;
      target.innerHTML = html;
    });
  }

  async function uploadDataLakeArtifact(button, filesOverride = null) {
    const panel = button.closest("[data-artifact-panel]") || form;
    const fileInput = panel.querySelector("[data-artifact-file]");
    const files = Array.from(filesOverride || fileInput?.files || []);
    if (!files.length) {
      renderArtifactResults("업로드할 파일을 먼저 선택하세요.");
      return;
    }
    if (!draftSessionId && form.dataset.draftSessionUrl) {
      try {
        await pushServerAutosave();
      } catch (_error) {
        // Upload can still continue; the artifact will keep local target metadata.
      }
    }
    button.disabled = true;
    const previousText = button.textContent;
    button.textContent = "업로드 중...";
    try {
      const endpoint = button.dataset.uploadUrl || "/api/data-lake/artifacts/upload";
      for (const file of files) {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("visibility", formField("scope")?.value || "private");
        formData.append("source_context", JSON.stringify(artifactSourceContext(panel)));
        const response = await fetch(`${endpoint}?employee_id=${encodeURIComponent(employeeId)}`, {
          method: "POST",
          body: formData,
        });
        const body = await response.json().catch(() => ({detail: response.statusText}));
        if (!response.ok) {
          const detail = body.detail || body;
          throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail, null, 2));
        }
        if (body.status === "disabled") {
          renderArtifactResults("Data Lake가 비활성화되어 파일을 저장하지 않았습니다. core SOP 작성은 계속할 수 있습니다.");
          return;
        }
        const artifact = {...(body.artifact || {}), attachment: body.attachment || null};
        if (artifact.artifact_id && !dataLakeArtifacts.some((item) => item.artifact_id === artifact.artifact_id)) {
          dataLakeArtifacts.push(artifact);
        }
      }
      renderArtifactResults();
      scheduleAutosave();
      setResult("ok", "근거 파일을 연결했습니다", `${files.length}개 파일 원본은 Data Lake URL과 profile 기준으로 SOP 근거에 연결됩니다.`);
    } catch (error) {
      setResult("error", "Data Lake 첨부 실패", error.message || String(error));
    } finally {
      button.disabled = false;
      button.textContent = previousText || "Data Lake로 업로드";
      if (fileInput) fileInput.value = "";
    }
  }

  async function removeDataLakeArtifact(button) {
    const artifactId = button.dataset.artifactRemove || "";
    const panel = button.closest("[data-artifact-panel]") || form;
    if (!artifactId) return;
    const target = currentArtifactTarget(panel);
    try {
      const query = new URLSearchParams({
        employee_id: employeeId,
        target_type: target.target_type || "",
        target_id: target.target_id || "",
        user_confirmed: "true",
      });
      await fetch(`/api/data-lake/artifacts/${encodeURIComponent(artifactId)}/attach?${query.toString()}`, {method: "DELETE"});
    } catch (_error) {
      // Keep local cleanup responsive even if the optional Data Lake is disabled.
    }
    dataLakeArtifacts = dataLakeArtifacts.filter((artifact) => artifact.artifact_id !== artifactId);
    renderArtifactResults();
    scheduleAutosave();
  }

  function applyPayloadToForm(payload = {}) {
    const applyOne = (key, value) => {
      const field = formField(key);
      if (field) {
        if (jsonFields.has(key)) field.value = typeof value === "string" ? value : JSON.stringify(value || {});
        else if (listFields.has(key)) field.value = Array.isArray(value) ? value.join(", ") : String(value || "");
        else field.value = Array.isArray(value) ? value.join(", ") : String(value || "");
        renderDraftFieldChips(key);
        updateSelectedLink(key);
        return;
      }
      if (value && typeof value === "object" && !Array.isArray(value)) {
        for (const [childKey, childValue] of Object.entries(value)) applyOne(`${key}.${childKey}`, childValue);
      }
    };
    for (const [key, value] of Object.entries(payload || {})) applyOne(key, value);
    if (Array.isArray(payload.data_lake_artifacts)) {
      dataLakeArtifacts = payload.data_lake_artifacts;
      renderArtifactResults();
    }
    if (Array.isArray(payload.workflow_tasks) && payload.workflow_tasks.length) {
      workflowStages = payload.workflow_tasks.map((task) => makeStage(task));
      selectedStageId = workflowStages[0]?.stage_id || selectedStageId;
    } else if (Array.isArray(payload.workflow_stages) && payload.workflow_stages.length) {
      workflowStages = payload.workflow_stages.map((stage) => makeStage(stage));
      selectedStageId = workflowStages[0]?.stage_id || selectedStageId;
    }
    ["event_mode", "sop_mode", "action_mode"].forEach((name) => {
      const field = formField(name);
      setSectionMode(name, field?.value || "skip");
    });
    setConnectorKind(selectedConnectorKind() || payload.connector_kind || "manual");
    updateEventSourcePanels();
    updateScheduleBuilder();
    updateRecommendationControls();
  }

  const modeLabels = {
    reuse: "기존 항목",
    draft: "새 초안",
    pattern: "이력 기반",
    schedule: "일정",
    lightweight: "간단 절차",
    manual: "Manual",
    skip: "선택 안 함",
  };

  function modeLabelFor(name, value) {
    if (value === "skip") {
      if (name === "event_mode") return "수동 실행";
      if (name === "sop_mode") return "나중에 정리";
      if (name === "action_mode") return "Action 없음";
    }
    return modeLabels[value || "skip"] || value || "선택 안 함";
  }

  function setSectionMode(name, value, options = {}) {
    const field = formField(name);
    if (field) field.value = value || "skip";
    form.querySelectorAll(`[data-section-mode="${name}"]`).forEach((button) => {
      const selected = button.dataset.modeValue === (value || "skip");
      button.classList.toggle("selected", selected);
      button.setAttribute("aria-pressed", selected ? "true" : "false");
    });
    const label = form.querySelector(`[data-mode-label="${name}"]`);
    if (label) label.textContent = modeLabelFor(name, value || "skip");
    if (name === "action_mode" && value === "manual") setConnectorKind("manual");
    updateModeFields(name, value || "skip");
    if (name === "event_mode") updateScheduleBuilder();
    maybePrepareDraftSuggestion(name, value || "skip", options);
    updateSectionRefineControls();
    const pickerConfig = pickerTargets[name]?.[value || "skip"];
    if (pickerConfig) {
      const [kind, targetField] = pickerConfig;
      void handleLinkPicker(kind, targetField, {inline: true}).catch((error) => {
        setInlinePicker(targetField, `<p class="muted">후보를 불러오지 못했습니다. ${escapeHtml(error.message || String(error))}</p>`);
      });
    }
  }

  function updateModeFields(name, value) {
    const prefix = name.replace("_mode", "");
    form.querySelectorAll(`[data-${prefix}-mode-field]`).forEach((item) => {
      const allowed = String(item.dataset[`${prefix}ModeField`] || "").split(/\s+/).filter(Boolean);
      const hidden = !allowed.includes(value || "skip");
      item.hidden = hidden;
      item.querySelectorAll("input, select, textarea, button").forEach((control) => {
        if (control.matches("[data-section-mode], [data-picker-close]")) return;
        control.disabled = hidden;
      });
    });
  }

  function draftSectionForModeField(name, value) {
    if (name === "event_mode" && value === "draft") return "event";
    if (name === "sop_mode" && (value === "draft" || value === "lightweight")) return "sop";
    if (name === "action_mode" && value === "draft") return "action";
    return "";
  }

  function draftSuggestionFromPlan(section) {
    if (!currentPlan) return null;
    if (section === "event") return currentPlan.event_section?.draft_suggestion || null;
    if (section === "sop") return currentPlan.sop_section?.draft_suggestion || null;
    if (section === "action") return (currentPlan.action_sections || [])[0]?.draft_suggestion || null;
    return null;
  }

  function clearDraftSuggestionTimer(section) {
    if (draftSuggestionTimers[section]) {
      clearTimeout(draftSuggestionTimers[section]);
      delete draftSuggestionTimers[section];
    }
  }

  function snapshotFields(fields) {
    const snapshot = {};
    for (const fieldName of fields || []) {
      const field = formField(fieldName);
      if (field) snapshot[fieldName] = field.value || "";
    }
    return snapshot;
  }

  function restoreSnapshot(snapshot) {
    for (const [fieldName, value] of Object.entries(snapshot || {})) {
      const field = formField(fieldName);
      if (field) field.value = value;
      updateSelectedLink(fieldName);
      renderDraftFieldChips(fieldName);
    }
  }

  function applyDraftSuggestion(section) {
    const suggestion = draftSuggestionFromPlan(section);
    if (!suggestion) return;
    clearDraftSuggestionTimer(section);
    const fields = suggestion.editable_fields || Object.keys(suggestion.recommended_payload || {});
    draftSuggestionSnapshots[section] = snapshotFields(fields);
    for (const [fieldName, value] of Object.entries(suggestion.recommended_payload || {})) {
      if (fieldName === "connector_kind") {
        setConnectorKind(String(value || "manual"));
      }
      setFieldValue(fieldName, value);
    }
    const card = form.querySelector(`[data-draft-suggestion="${section}"]`);
    if (card) {
      card.hidden = false;
      card.innerHTML = `
        <strong>${escapeHtml(suggestion.display_name || "추천값")} 적용됨</strong>
        <span>추천값을 초안에 채웠습니다. 필요하면 바로 수정할 수 있습니다.</span>
        <div class="draft-suggestion-actions">
          <button type="button" class="secondary-button" data-draft-suggestion-undo="${escapeHtml(section)}">되돌리기</button>
        </div>
      `;
    }
  }

  function renderDraftSuggestion(section, suggestion) {
    const card = form.querySelector(`[data-draft-suggestion="${section}"]`);
    if (!card || !suggestion) return;
    clearDraftSuggestionTimer(section);
    const diffPreview = Array.isArray(suggestion.diff_preview) ? suggestion.diff_preview : [];
    card.hidden = false;
    card.innerHTML = `
      <strong>${escapeHtml(suggestion.display_name || "추천값")}</strong>
      <span>${escapeHtml(suggestion.summary || "추천값을 만들었습니다. 적용을 누를 때만 초안에 반영됩니다.")}</span>
      ${diffPreview.length ? `
        <details class="draft-suggestion-preview" open>
          <summary>비교 보기</summary>
          <ul class="diff-preview-list">
            ${diffPreview.map((item) => `
              <li>
                <span>${escapeHtml(item.field || "field")}</span>
                <strong>${escapeHtml(item.recommended || "")}</strong>
              </li>
            `).join("")}
          </ul>
        </details>
      ` : ""}
      <small>${escapeHtml(suggestion.technical_name ? `내부 이름은 저장 시 자동 정리됩니다.` : "내부 식별자는 검증 단계에서 자동 정리됩니다.")}</small>
      <div class="draft-suggestion-actions">
        <button type="button" class="secondary-button" data-draft-suggestion-apply="${escapeHtml(section)}">적용</button>
        <button type="button" class="secondary-button" data-draft-suggestion-compare="${escapeHtml(section)}">비교 보기</button>
        <button type="button" class="secondary-button" data-draft-suggestion-cancel="${escapeHtml(section)}">무시</button>
      </div>
    `;
  }

  async function ensureSopPlan() {
    if (currentPlan?.plan_type === "sop_registration_plan") return currentPlan;
    const payload = collectPayload();
    currentPlan = await postJson(form.dataset.planUrl, planRequestFromPayload(payload));
    renderAgentSuggestions(currentPlan);
    return currentPlan;
  }

  function maybePrepareDraftSuggestion(name, value, options = {}) {
    const section = draftSectionForModeField(name, value);
    if (!section || !options.fromUser) return;
    hideDraftSuggestion(section);
  }

  async function prepareSectionDraftSuggestion(section) {
    if (!hasSectionRefineInput(section)) {
      const card = form.querySelector(`[data-draft-suggestion="${section}"]`);
      if (card) {
        card.hidden = false;
        card.innerHTML = `<span class="muted">초안을 먼저 입력하면 AI가 다듬기 제안을 만들 수 있습니다.</span>`;
      }
      return;
    }
    const card = form.querySelector(`[data-draft-suggestion="${section}"]`);
    if (card) {
      card.hidden = false;
      card.innerHTML = `<span class="muted">입력한 초안을 정리하고 있습니다.</span>`;
    }
    try {
      currentPlan = await postJson(form.dataset.planUrl, planRequestFromPayload(collectPayload()));
      renderAgentSuggestions(currentPlan);
      if (currentPlan?.recommendation_state && currentPlan.recommendation_state !== "ready") {
        if (card) {
          card.innerHTML = `<span class="muted">${escapeHtml((currentPlan.input_requirements || [])[0] || "추천을 만들려면 업무 설명을 조금 더 적어주세요.")}</span>`;
        }
        return;
      }
      const suggestion = draftSuggestionFromPlan(section);
      if (suggestion) renderDraftSuggestion(section, suggestion);
      else if (card) card.innerHTML = `<span class="muted">이 초안에 바로 적용할 추천값이 없습니다. 현재 입력으로 계속 진행해도 됩니다.</span>`;
    } catch (error) {
      if (card) {
        card.innerHTML = `<span class="muted">추천값을 불러오지 못했습니다. 직접 입력해도 됩니다. ${escapeHtml(error.message || String(error))}</span>`;
      }
    }
  }

  function renderDraftFieldChips(name) {
    const target = form.querySelector(`[data-draft-field-chips="${name}"]`);
    if (!target) return;
    const values = valuesForField(name);
    target.innerHTML = values.length ? values.map((value) => `
      <span class="selected-chip draft-chip">
        <span>${escapeHtml(value)}</span>
        <button type="button" aria-label="${escapeHtml(value)} 삭제" data-remove-draft-value="${escapeHtml(name)}" data-remove-value="${escapeHtml(value)}">×</button>
      </span>
    `).join("") : "";
  }

  function removeDraftFieldValue(name, value) {
    const field = formField(name);
    if (!field) return;
    field.value = valuesForField(name).filter((item) => item !== value).join(", ");
    renderDraftFieldChips(name);
  }

  function resultJsonDetails(body) {
    return `
      <details class="registration-result-details">
        <summary>세부 JSON 보기</summary>
        <pre>${escapeHtml(typeof body === "string" ? body : JSON.stringify(body, null, 2))}</pre>
      </details>
    `;
  }

  function renderCandidateList(items) {
    if (!Array.isArray(items) || !items.length) return `<p class="muted">기존 후보가 없습니다. 신규 초안이 필요할 수 있습니다.</p>`;
    return `
      <div class="registration-result-list">
        ${items.slice(0, 5).map((item) => `
          <div class="registration-result-card">
            <strong>${escapeHtml(item.title || item.workflow_definition_key || item.boi_id || item.action_key || "기존 후보")}</strong>
            <span>${escapeHtml(item.description || item.business_goal || item.match_reason || "")}</span>
          </div>
        `).join("")}
      </div>
    `;
  }

  function renderPlan(body) {
    if (body?.plan_type === "sop_registration_plan") {
      renderAgentSuggestions(body);
      if (body?.recommendation_state === "needs_input") {
        return `
          <strong>업무 설명이 먼저 필요합니다</strong>
          <p>추천을 만들기 전에 어떤 업무를 SOP 실행 흐름으로 정리할지 자연어 설명, 제목, 업무 목적 중 하나를 먼저 적어주세요.</p>
          ${(body.input_requirements || []).length ? `<ul class="warning-list">${body.input_requirements.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
        `;
      }
      const sections = [body.event_section, body.sop_section, ...(body.action_sections || [])].filter(Boolean);
      const stageSuggestions = Array.isArray(body.workflow_stage_suggestions) ? body.workflow_stage_suggestions : [];
      return `
        <strong>SOP 실행 흐름 추천</strong>
        <div class="registration-result-summary">
          <span class="badge">SOP 추가</span>
          <span>${escapeHtml(body?.recommended_next_step || "필요한 섹션만 선택하세요.")}</span>
        </div>
        ${stageSuggestions.length ? `
          <div class="registration-result-card">
            <strong>단계 추천</strong>
            <span>${escapeHtml(stageSuggestions.map((stage) => stage.stage_name).slice(0, 6).join(" → "))}</span>
            <button type="button" class="secondary-button" data-apply-stage-suggestions>단계 추천 적용</button>
          </div>
        ` : ""}
        <div class="registration-result-list">
          ${sections.map((section) => `
            <div class="registration-result-card">
              <strong>${escapeHtml(section.title || section.section_id || "섹션")}</strong>
              <span>${escapeHtml((section.suggestions || []).map((item) => item.label).slice(0, 2).join(" · ") || "선택 사항")}</span>
            </div>
          `).join("")}
        </div>
        ${(body.missing_decisions || []).length ? `<ul class="warning-list">${body.missing_decisions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
        <details>
          <summary>추천값 보기</summary>
          <pre>${escapeHtml(JSON.stringify(body?.draft_payload || {}, null, 2))}</pre>
        </details>
      `;
    }
    const refs = body?.candidate_references || {};
    const candidates = [
      ...(refs.documents || []),
      ...(refs.event_types || []),
    ];
    const missing = body?.missing_decisions || [];
    return `
      <strong>추천 결과</strong>
      <div class="registration-result-summary">
        <span class="badge">${escapeHtml(body?.target_kind || "확인 필요")}</span>
        <span>${escapeHtml(body?.business_goal || "입력한 설명을 기준으로 추천했습니다.")}</span>
      </div>
      ${renderCandidateList(candidates)}
      ${(missing || []).length ? `<ul class="warning-list">${missing.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
      <details>
        <summary>추천값 보기</summary>
        <pre>${escapeHtml(JSON.stringify(body?.draft_payload || {}, null, 2))}</pre>
      </details>
    `;
  }

  function renderAgentSuggestions(body) {
    if (!agentSuggestions) return;
    const sections = [
      ...(body?.event_section?.suggestions || []).map((item) => ({...item, section: "Event"})),
      ...(body?.sop_section?.suggestions || []).map((item) => ({...item, section: "SOP"})),
      ...((body?.action_sections || []).flatMap((section) => (section.suggestions || []).map((item) => ({...item, section: "Action"})))),
    ];
    if (!sections.length) {
      agentSuggestions.innerHTML = `<p class="muted">아직 보여줄 추천 후보가 없습니다. 설명을 조금 더 적고 추천 후보를 만들어보세요.</p>`;
      return;
    }
    agentSuggestions.innerHTML = `
      <div class="registration-agent-suggestion-list">
        ${sections.slice(0, 8).map((item, index) => {
          return `
            <article class="registration-agent-suggestion-card">
              <span class="badge">${escapeHtml(item.section || "제안")}</span>
              <strong>${escapeHtml(item.label || "추천")}</strong>
              <p>${escapeHtml(item.description || "")}</p>
              <small>필요하면 해당 섹션의 AI 다듬기 버튼에서 미리보고 적용하세요.</small>
            </article>
          `;
        }).join("")}
      </div>
    `;
  }

  function renderExplorer(body) {
    const roots = body?.root_hints || [];
    const tree = body?.folders?.folder_tree || {};
    setPicker(`
      <div class="registration-picker-heading">
        <div>
          <strong>업무 단위 폴더 선택</strong>
          <p class="muted">기본 폴더를 그대로 쓰거나, 접근 가능한 폴더를 직접 선택하세요.</p>
        </div>
        <button type="button" class="secondary-button" data-picker-close>닫기</button>
      </div>
      <div class="registration-result-list">
        ${roots.map((root) => `
          <button type="button" class="registration-result-card selectable" data-pick-folder="${escapeHtml(root)}">
            <strong>추천 시작 폴더</strong>
            <span>${escapeHtml(root)}</span>
          </button>
        `).join("")}
      </div>
      <div class="registration-folder-tree">${renderFolderNodes(tree?.children || [])}</div>
    `);
    return `
      <strong>폴더 선택기를 열었습니다</strong>
      <p>위쪽 선택 영역에서 업무 단위 폴더를 고르세요.</p>
    `;
  }

  function renderFolderNodes(nodes, depth = 0) {
    if (!Array.isArray(nodes) || !nodes.length) {
      return depth === 0 ? `<p class="muted">선택할 수 있는 하위 폴더가 없습니다.</p>` : "";
    }
    return `
      <ul>
        ${nodes.map((node) => `
          <li>
            <button type="button" data-pick-folder="${escapeHtml(node.path || "")}">
              <span>${escapeHtml(node.label || node.path || "folder")}</span>
              <small>${escapeHtml(node.count || 0)}</small>
            </button>
            ${renderFolderNodes(node.children || [], depth + 1)}
          </li>
        `).join("")}
      </ul>
    `;
  }

  function renderLinkCandidates(kind, targetField, body, options = {}) {
    const labels = {
      sops: "SOP",
      event_types: "Event",
      actions: "Action",
      skills: "Skill",
    };
    const candidates = body?.kind === kind ? (body.items || []) : (body?.groups?.[kind] || []);
    const total = Number(body?.kind === kind ? body.total : body?.pagination?.[kind]?.total || candidates.length || 0);
    const currentPage = Number(body?.kind === kind ? body.current_page : body?.pagination?.[kind]?.current_page || 1) || 1;
    const pageSize = Number(body?.kind === kind ? body.page_size : body?.pagination?.[kind]?.page_size || options.pageSize || options.limit || 8) || 8;
    const totalPages = Number(body?.kind === kind ? body.total_pages : body?.pagination?.[kind]?.total_pages || Math.max(1, Math.ceil(total / pageSize))) || 1;
    const query = body?.query || "";
    const heading = query ? "검색 결과" : "추천 후보";
    const commonReasonValues = [...new Set(candidates.map((item) => String(item.why_recommended || "").trim()).filter(Boolean))];
    const commonHintValues = [...new Set(candidates.map((item) => String(item.assetization_hint || "").trim()).filter(Boolean))];
    const commonReason = commonReasonValues.length === 1 ? commonReasonValues[0] : "";
    const commonAssetizationHint = commonHintValues.length === 1 ? commonHintValues[0] : "";
    const genericBadge = labels[kind] || "";
    const itemBadges = (item) => (item.badges || []).filter((badge) => String(badge || "").trim() && String(badge || "").trim() !== genericBadge);
    const itemReason = (item) => {
      const reason = String(item.why_recommended || "").trim();
      return reason && reason !== commonReason ? reason : "";
    };
    const itemAssetizationHint = (item) => {
      const hint = String(item.assetization_hint || "").trim();
      return hint && hint !== commonAssetizationHint ? hint : "";
    };
    const renderPageButtons = () => {
      if (totalPages <= 1) return "";
      const start = Math.max(1, currentPage - 2);
      const end = Math.min(totalPages, currentPage + 2);
      const pages = [];
      if (start > 1) pages.push(1);
      if (start > 2) pages.push("ellipsis-start");
      for (let page = start; page <= end; page += 1) pages.push(page);
      if (end < totalPages - 1) pages.push("ellipsis-end");
      if (end < totalPages) pages.push(totalPages);
      return `
        <nav class="catalog-picker-pagination" aria-label="${escapeHtml(labels[kind] || "항목")} 페이지">
          <button type="button" class="secondary-button catalog-page-button" data-catalog-page="${escapeHtml(kind)}" data-target-field="${escapeHtml(targetField || "")}" data-page="${escapeHtml(Math.max(1, currentPage - 1))}" data-page-size="${escapeHtml(pageSize)}" ${currentPage <= 1 ? "disabled" : ""}>이전</button>
          ${pages.map((page) => typeof page === "number"
            ? `<button type="button" class="secondary-button catalog-page-button ${page === currentPage ? "active" : ""}" data-catalog-page="${escapeHtml(kind)}" data-target-field="${escapeHtml(targetField || "")}" data-page="${escapeHtml(page)}" data-page-size="${escapeHtml(pageSize)}" ${page === currentPage ? "disabled aria-current=\"page\"" : ""}>${escapeHtml(page)}</button>`
            : `<span class="catalog-page-ellipsis">…</span>`
          ).join("")}
          <button type="button" class="secondary-button catalog-page-button" data-catalog-page="${escapeHtml(kind)}" data-target-field="${escapeHtml(targetField || "")}" data-page="${escapeHtml(Math.min(totalPages, currentPage + 1))}" data-page-size="${escapeHtml(pageSize)}" ${currentPage >= totalPages ? "disabled" : ""}>다음</button>
        </nav>
      `;
    };
    const html = `
      <div class="registration-picker-heading">
        <div>
          <strong>${escapeHtml(labels[kind] || "항목")} 선택</strong>
          <p class="muted">${escapeHtml(heading)} ${escapeHtml(candidates.length)}건${total ? ` / 전체 ${escapeHtml(total)}건` : ""}. 필요한 항목이 없으면 검색어를 바꿔보세요.</p>
        </div>
        ${options.inline ? "" : `<button type="button" class="secondary-button" data-picker-close>닫기</button>`}
      </div>
      <div class="catalog-picker-controls">
        <input data-catalog-query="${escapeHtml(targetField || "")}" data-catalog-kind="${escapeHtml(kind || "")}" value="${escapeHtml(query)}" placeholder="${escapeHtml(labels[kind] || "항목")} 이름, 설명, 업무 키워드" />
        <button type="button" class="secondary-button" data-catalog-search="${escapeHtml(kind)}" data-target-field="${escapeHtml(targetField || "")}">검색</button>
      </div>
      ${(commonReason || commonAssetizationHint) ? `
        <div class="catalog-picker-context">
          ${commonReason ? `<span>${escapeHtml(commonReason)}</span>` : ""}
          ${commonAssetizationHint ? `<span>${escapeHtml(commonAssetizationHint)}</span>` : ""}
        </div>
      ` : ""}
      <div class="registration-result-list">
        ${candidates.length ? candidates.map((item) => {
          const badges = itemBadges(item);
          const reason = itemReason(item);
          const assetizationHint = itemAssetizationHint(item);
          const displayLabel = item.display_label || item.label || item.value || "후보";
          const technicalValue = item.technical_value || item.value || "";
          const technicalLabel = item.technical_label || technicalValue;
          return `
          <article class="registration-result-card selectable catalog-candidate-card">
            <button
              type="button"
              class="catalog-candidate-select"
              data-pick-link="${escapeHtml(item.value || "")}"
              data-pick-label="${escapeHtml(displayLabel)}"
              data-pick-description="${escapeHtml(item.description || "")}"
              data-pick-technical-label="${escapeHtml(technicalLabel)}"
              data-target-field="${escapeHtml(targetField || "")}"
            >
              <strong>${escapeHtml(displayLabel)}</strong>
              ${badges.length ? `<span class="registration-card-badges">${badges.map((badge) => `<span class="badge">${escapeHtml(badge)}</span>`).join("")}</span>` : ""}
              <span>${escapeHtml(item.description || "")}</span>
              ${reason ? `<small>${escapeHtml(reason)}</small>` : ""}
              ${assetizationHint ? `<small class="assetization-hint">${escapeHtml(assetizationHint)}</small>` : ""}
            </button>
            ${technicalValue ? `<details class="catalog-technical-details"><summary>기술 세부정보</summary><code>${escapeHtml(technicalLabel)}</code></details>` : ""}
          </article>
        `;}).join("") : `<p class="muted">선택할 후보가 없습니다. 설명을 더 구체적으로 적거나 직접 ID를 입력하세요.</p>`}
      </div>
      ${renderPageButtons()}
    `;
    if (options.inline) setInlinePicker(targetField, html);
    else setPicker(html);
  }

  function renderPreview(body) {
    const cards = body?.cards || [];
    return `
      <strong>실행 전 확인</strong>
      <p>${escapeHtml(body?.summary || "운영 반영 전에 확인할 항목을 정리했습니다.")}</p>
      <div class="registration-result-list">
        ${cards.map((card) => `
          <div class="registration-result-card">
            <strong>${escapeHtml(card.title || "확인 항목")}</strong>
            <span><span class="badge">${escapeHtml(card.status || "확인")}</span> ${escapeHtml(card.body || "")}</span>
          </div>
        `).join("")}
      </div>
      ${resultJsonDetails(body)}
    `;
  }

  function renderResult(action, body) {
    if (!result) return;
    let kind = "ok";
    let html = "";
    if (action === "plan") {
      html = renderPlan(body);
      if (body?.recommendation_state === "needs_input") kind = "warning";
      else setFlowStage("entry");
    } else if (action === "explorer") {
      html = renderExplorer(body);
    } else if (action === "preview") {
      html = renderPreview(body);
      setFlowStage("review");
    } else if (action === "dedupe") {
      const recommendation = body?.recommendation || "new";
      const label = recommendation === "reuse" ? "재사용 권장" : recommendation === "extend" ? "확장 가능" : "신규 필요";
      const candidates = [...(body?.candidates || []), ...(body?.workflow_definitions || []), ...(body?.boi_documents || [])];
      html = `
        <strong>기존 후보 확인</strong>
        <div class="registration-result-summary"><span class="badge">${escapeHtml(label)}</span><span>기존 SOP/Event/Action/업무 흐름을 먼저 재사용할 수 있는지 확인했습니다.</span></div>
        ${renderCandidateList(candidates)}
        ${resultJsonDetails(body)}
      `;
    } else if (action === "create") {
      const draft = body?.draft || {};
      const patch = draft.catalog_patch_proposal || {};
      html = `
        <strong>초안 미리보기</strong>
        <div class="registration-result-list">
          <div class="registration-result-card"><strong>Draft</strong><span>${escapeHtml(draft.draft_id || "-")}</span></div>
          <div class="registration-result-card"><strong>Action key</strong><span>${escapeHtml(patch.action_key || patch.event_type || patch.title || "-")}</span></div>
          <div class="registration-result-card"><strong>Connector</strong><span>${escapeHtml(patch.connector_kind || patch.kind || "-")}</span></div>
          <div class="registration-result-card"><strong>연결</strong><span>${escapeHtml([patch.linked_sop_ref, patch.linked_workflow_definition_key].filter(Boolean).join(" / ") || "-")}</span></div>
        </div>
        <p class="muted">아직 catalog/runtime에는 반영되지 않았습니다. 검증 후 게시 요청으로 전환하세요.</p>
        ${resultJsonDetails(body)}
      `;
      setFlowStage("review");
    } else if (action === "validate") {
      const validation = body?.draft?.validation || {};
      kind = validation.valid ? "ok" : "warning";
      html = `
        <strong>검증 결과</strong>
        <div class="registration-result-summary"><span class="badge">${validation.valid ? "통과" : "수정 필요"}</span><span>${escapeHtml((validation.checks || []).join(", ") || "schema, dedupe, rbac, secret_scan")}</span></div>
        ${(validation.errors || []).length ? `<ul class="error-list">${validation.errors.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
        ${(validation.warnings || []).length ? `<ul class="warning-list">${validation.warnings.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
        ${resultJsonDetails(body)}
      `;
    } else if (action === "publish") {
      html = `
        <strong>게시 요청 완료</strong>
        <p>검증된 초안이 게시 요청 상태로 전환되었습니다. 운영 catalog 반영은 별도 승인 흐름에서 처리합니다.</p>
        ${resultJsonDetails(body)}
      `;
    } else {
      kind = body?.kind || "ok";
      html = `<strong>${escapeHtml(body?.title || "결과")}</strong>${resultJsonDetails(body?.body || body)}`;
    }
    result.className = `registration-result ${kind || ""}`.trim();
    result.innerHTML = html;
  }

  function setResult(kind, title, body) {
    if (!result) return;
    result.className = `registration-result ${kind || ""}`.trim();
    result.innerHTML = `
      <strong>${escapeHtml(title)}</strong>
      <p>${escapeHtml(typeof body === "string" ? body : JSON.stringify(body, null, 2))}</p>
    `;
  }

  function collectPayload() {
    syncHiddenModels();
    if ((formField("event_mode")?.value || "") === "schedule") updateScheduleBuilder();
    const payload = {};
    const connectorKind = selectedConnectorKind();
    for (const field of Array.from(form.elements)) {
      const key = field.name;
      if (!key || field.disabled) continue;
      if (field.dataset?.connectorField && field.dataset.connectorField !== connectorKind) continue;
      if ((field.type === "checkbox" || field.type === "radio") && !field.checked) continue;
      const value = field.type === "checkbox" ? field.value || "true" : field.value;
      let parsedValue;
      if (listFields.has(key) || connectorListFields.has(key)) {
        parsedValue = splitList(value);
      } else if (jsonFields.has(key)) {
        try {
          parsedValue = value ? JSON.parse(value) : {};
        } catch (_error) {
          parsedValue = {};
        }
      } else {
        parsedValue = String(value || "").trim();
      }
      setNested(payload, key, parsedValue);
    }
    payload.entry_kind = form.dataset.entryKind || payload.entry_kind;
    if (payload.entry_kind === "action") {
      payload.connector_kind = connectorKind || payload.connector_kind || payload.execution_kind;
      payload.execution_kind = payload.connector_kind;
    }
    if (payload.event_mode === "schedule") updateScheduleBuilder();
    payload.approval_required = Boolean(payload.approval_required);
    return payload;
  }

  function planRequestFromPayload(payload) {
    return {
      entry_kind: payload.entry_kind || "",
      raw_request: payload.raw_request || payload.business_goal || payload.description || payload.title || "",
      scope: payload.scope || "private",
      folder: payload.folder || "",
      focus: page.dataset.focus || "",
      payload,
      connector_kind: payload.connector_kind || payload.execution_kind || "",
      selected_refs: {
        linked_sop_ref: payload.linked_sop_ref || "",
        linked_workflow_definition_key: payload.linked_workflow_definition_key || "",
        event_type: payload.event_type || "",
      },
    };
  }

  async function postJson(url, payload, method = "POST") {
    const response = await fetch(url, {
      method,
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    const body = await response.json().catch(() => ({text: response.statusText}));
    if (!response.ok) {
      const detail = body.detail || body;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail, null, 2));
    }
    return body;
  }

  function eventAdapterPreviewTarget() {
    return form.querySelector("[data-event-adapter-preview]");
  }

  function eventAdapterRequestFromPayload(payload) {
    const config = payload.event_source_config || {};
    return {
      source_kind: payload.event_source_kind || selectedEventSourceKind(),
      source_name: config.source_name || "",
      target_event_type: config.target_event_type || payload.event_type || (payload.linked_event_types || [])[0] || "",
      payload_mapping: config.payload_mapping && typeof config.payload_mapping === "object" ? config.payload_mapping : {},
      auth_policy: config.auth_policy && typeof config.auth_policy === "object" ? config.auth_policy : {},
      sample_payload: config.sample_payload && typeof config.sample_payload === "object" ? config.sample_payload : {},
      health_check: config.health_check && typeof config.health_check === "object" ? config.health_check : {},
    };
  }

  function renderEventAdapterPreview(kind, body) {
    const target = eventAdapterPreviewTarget();
    if (!target) return;
    const plan = body?.adapter_plan || body?.draft?.adapter_plan || {};
    const test = body?.test_status ? body : body?.draft?.test_result || {};
    const draft = body?.draft || {};
    target.hidden = false;
    target.innerHTML = `
      <strong>${escapeHtml(kind === "test" ? "샘플 테스트 결과" : kind === "draft" ? "Adapter 초안" : "설정 미리보기")}</strong>
      ${plan.source_kind ? `<p>${escapeHtml(plan.source_kind)} · ${escapeHtml(plan.source_name || "")} → ${escapeHtml(plan.target_event_type || "")}</p>` : ""}
      ${plan.webhook ? `<p><code>${escapeHtml(plan.webhook.endpoint_path || "")}</code></p>` : ""}
      ${plan.kafka ? `<p>${escapeHtml(plan.kafka.integration_guide || "")}</p>` : ""}
      ${test.test_status ? `<p><span class="badge">${escapeHtml(test.test_status)}</span> 실제 Event Broker에는 발행하지 않았습니다.</p>` : ""}
      ${draft.draft_id ? `<p><span class="badge">draft</span> ${escapeHtml(draft.draft_id)}</p>` : ""}
      <details>
        <summary>세부정보</summary>
        <pre>${escapeHtml(JSON.stringify(body, null, 2))}</pre>
      </details>
    `;
  }

  async function ensureEventAdapterPlan() {
    let existing = {};
    try {
      existing = JSON.parse(formField("event_producer_adapter_plan")?.value || "{}");
    } catch (_error) {
      existing = {};
    }
    if (existing && existing.plan_type === "event_producer_adapter_plan") return existing;
    const response = await postJson(`${form.dataset.eventAdapterPlanUrl}?employee_id=${encodeURIComponent(employeeId)}`, eventAdapterRequestFromPayload(collectPayload()));
    const plan = response.adapter_plan || {};
    const field = formField("event_producer_adapter_plan");
    if (field) field.value = JSON.stringify(plan);
    syncHiddenModels();
    renderEventAdapterPreview("plan", response);
    return plan;
  }

  async function handleEventAdapterAction(action) {
    try {
      if (action === "plan") {
        await ensureEventAdapterPlan();
        scheduleAutosave();
        return;
      }
      const plan = await ensureEventAdapterPlan();
      if (action === "test") {
        const body = await postJson(`${form.dataset.eventAdapterTestUrl}?employee_id=${encodeURIComponent(employeeId)}`, {adapter_plan: plan});
        renderEventAdapterPreview("test", body);
        scheduleAutosave();
        return;
      }
      if (action === "draft") {
        const testResult = await postJson(`${form.dataset.eventAdapterTestUrl}?employee_id=${encodeURIComponent(employeeId)}`, {adapter_plan: plan});
        const body = await postJson(`${form.dataset.eventAdapterDraftUrl}?employee_id=${encodeURIComponent(employeeId)}`, {adapter_plan: plan, test_result: testResult});
        renderEventAdapterPreview("draft", body);
        scheduleAutosave();
      }
    } catch (error) {
      setResult("error", "Event 시작 방식 확인 필요", error.message || String(error));
    }
  }

  function autosaveState() {
    syncHiddenModels();
    return {
      draft_session_id: draftSessionId || "",
      current_url: `${window.location.pathname}${window.location.search}`,
      payload: collectPayload(),
      plan: currentPlan || {},
      workflow_stages: workflowStages,
      workflow_tasks: workflowTasks(),
      local_state: {
        selected_stage_id: selectedStageId,
        current_step: currentStep,
        selected_links: selectedLinkState,
      },
      status: "open",
    };
  }

  function writeLocalAutosave() {
    try {
      localStorage.setItem(autosaveKey, JSON.stringify({...autosaveState(), saved_at: new Date().toISOString()}));
    } catch (_error) {
      // localStorage may be unavailable in strict browser modes; server autosave still runs.
    }
  }

  async function pushServerAutosave() {
    if (!form.dataset.draftSessionUrl) return;
    const state = autosaveState();
    const baseUrl = `${form.dataset.draftSessionUrl}?employee_id=${encodeURIComponent(employeeId)}`;
    const body = draftSessionId
      ? await postJson(`${form.dataset.draftSessionUrl}/${encodeURIComponent(draftSessionId)}?employee_id=${encodeURIComponent(employeeId)}`, state, "PATCH")
      : await postJson(baseUrl, state);
    draftSessionId = body?.session?.draft_session_id || draftSessionId;
    if (draftSessionId) {
      try {
        localStorage.setItem(autosaveKey, JSON.stringify({...state, draft_session_id: draftSessionId, saved_at: new Date().toISOString()}));
      } catch (_error) {
        // ignore
      }
    }
  }

  function scheduleAutosave() {
    if (!isSopRegistration()) return;
    writeLocalAutosave();
    if (autosaveTimer) clearTimeout(autosaveTimer);
    autosaveTimer = setTimeout(() => {
      void pushServerAutosave().catch(() => {
        // Autosave must not block editing. Readiness/diagnostics can surface failures later.
      });
    }, 2000);
  }

  function savedAutosaveState() {
    try {
      const raw = localStorage.getItem(autosaveKey);
      return raw ? JSON.parse(raw) : null;
    } catch (_error) {
      return null;
    }
  }

  function showAutosaveBannerIfNeeded() {
    const banner = form.querySelector("[data-autosave-banner]");
    if (!banner) return;
    const saved = savedAutosaveState();
    const hasPayload = saved?.payload && Object.values(saved.payload).some((value) => {
      if (Array.isArray(value)) return value.length > 0;
      if (value && typeof value === "object") return Object.keys(value).length > 0;
      return Boolean(String(value || "").trim());
    });
    banner.hidden = !hasPayload;
    const message = banner.querySelector("[data-autosave-message]");
    if (message && saved?.saved_at) message.textContent = `${new Date(saved.saved_at).toLocaleString()} 저장 상태를 이어서 작성할 수 있습니다.`;
  }

  function restoreAutosaveState() {
    const saved = savedAutosaveState();
    if (!saved) return;
    draftSessionId = saved.draft_session_id || "";
    currentPlan = saved.plan || null;
    selectedStageId = saved.local_state?.selected_stage_id || "";
    Object.assign(selectedLinkState, saved.local_state?.selected_links || {});
    workflowStages = Array.isArray(saved.workflow_stages)
      ? saved.workflow_stages
      : (Array.isArray(saved.workflow_tasks) ? saved.workflow_tasks.map((task) => makeStage(task)) : []);
    applyPayloadToForm(saved.payload || {});
    renderWorkflowStages();
    const step = saved.local_state?.current_step || "context";
    setFlowStage(step);
    const banner = form.querySelector("[data-autosave-banner]");
    if (banner) banner.hidden = true;
    setResult("ok", "작성 중인 초안을 복원했습니다", "화면을 벗어나도 이어서 작성할 수 있도록 자동저장이 유지됩니다.");
  }

  async function discardAutosaveState() {
    const saved = savedAutosaveState();
    try {
      localStorage.removeItem(autosaveKey);
    } catch (_error) {
      // ignore
    }
    const sessionId = draftSessionId || saved?.draft_session_id || "";
    draftSessionId = "";
    const banner = form.querySelector("[data-autosave-banner]");
    if (banner) banner.hidden = true;
    if (sessionId && form.dataset.draftSessionUrl) {
      try {
        await fetch(`${form.dataset.draftSessionUrl}/${encodeURIComponent(sessionId)}?employee_id=${encodeURIComponent(employeeId)}`, {method: "DELETE"});
      } catch (_error) {
        // ignore
      }
    }
  }

  function setDraftButtons(enabled) {
    form.querySelector('[data-registration-action="validate"]')?.toggleAttribute("disabled", !enabled);
    form.querySelector('[data-registration-action="publish"]')?.toggleAttribute("disabled", !enabled);
  }

  async function handleLinkPicker(kind, targetField, options = {}) {
    const payload = collectPayload();
    const inlineQuery = form.querySelector(`[data-catalog-query="${targetField}"]`)?.value || "";
    const search = encodeURIComponent(options.q ?? inlineQuery ?? "");
    const scope = encodeURIComponent(options.scope || "all");
    const folder = encodeURIComponent(options.folder || "");
    const cursor = encodeURIComponent(options.cursor || "");
    const pageSize = encodeURIComponent(options.pageSize || options.limit || "8");
    const page = encodeURIComponent(options.page || "1");
    const connectorKind = encodeURIComponent(options.connectorKind || "");
    const cursorParam = cursor ? `&cursor=${cursor}` : "";
    const connectorParam = connectorKind ? `&connector_kind=${connectorKind}` : "";
    const response = await fetch(`${form.dataset.linkCandidatesUrl}&q=${search}&scope=${scope}&folder=${folder}&kind=${encodeURIComponent(kind || "")}&limit=${pageSize}&page_size=${pageSize}&page=${page}${cursorParam}${connectorParam}`, {
      headers: {"Accept": "application/json"},
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || response.statusText);
    renderLinkCandidates(kind, targetField, body, options);
  }

  async function handleAction(action) {
    const payload = collectPayload();
    try {
      if (action === "plan") {
        if (!hasRecommendationInput()) {
          currentPlan = null;
          renderResult("plan", {plan_type: "sop_registration_plan", recommendation_state: "needs_input", input_requirements: [
            "자연어 설명, 제목, 업무 목적 중 하나에 어떤 업무를 SOP화할지 먼저 적어주세요.",
          ]});
          return;
        }
        const body = await postJson(form.dataset.planUrl, planRequestFromPayload(payload));
        currentPlan = body;
        renderResult("plan", body);
        return;
      }
      if (action === "explorer") {
        const scope = encodeURIComponent(payload.scope || "all");
        const response = await fetch(`${form.dataset.explorerUrl}&scope=${scope}`, {headers: {"Accept": "application/json"}});
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(body.detail || response.statusText);
        renderResult("explorer", body);
        return;
      }
      if (action === "preview") {
        if (!currentPlan) {
          currentPlan = await postJson(form.dataset.planUrl, planRequestFromPayload(payload));
        }
        const body = await postJson(form.dataset.previewUrl, {
          plan: currentPlan,
          entry_kind: payload.entry_kind || "",
          payload,
        });
        renderResult("preview", body);
        return;
      }
      if (action === "dedupe") {
        const body = await postJson(form.dataset.dedupeUrl, {
          event_type: payload.event_type || (payload.linked_event_types || [])[0] || "",
          action_keys: payload.linked_action_keys || (payload.action_key ? [payload.action_key] : []),
          connector: {kind: payload.connector_kind || payload.execution_kind || "", url: payload.connector_config?.endpoint || payload.connector_config?.url || ""},
          terms: [payload.title, payload.business_goal, payload.description].filter(Boolean),
        });
        renderResult("dedupe", body);
        return;
      }
      if (action === "create") {
        const draftPayload = currentPlan?.draft_payload && typeof currentPlan.draft_payload === "object"
          ? {...currentPlan.draft_payload, ...payload}
          : payload;
        const body = isSopRegistration()
          ? await postJson(form.dataset.apiUrl, {plan: currentPlan || {}, payload: draftPayload})
          : await postJson(form.dataset.apiUrl, draftPayload);
        currentDraftId = body?.draft?.draft_id || "";
        setDraftButtons(Boolean(currentDraftId));
        renderResult("create", body);
        return;
      }
      if (!currentDraftId) {
        setResult("warning", "먼저 초안을 만들어주세요", "검증과 게시 요청은 초안 생성 후 가능합니다.");
        return;
      }
      if (action === "validate") {
        const base = form.dataset.draftBaseUrl || "/api/registration/drafts";
        const body = await postJson(`${base}/${encodeURIComponent(currentDraftId)}/validate?employee_id=${encodeURIComponent(employeeId)}`, {});
        renderResult("validate", body);
        return;
      }
      if (action === "publish") {
        const base = form.dataset.draftBaseUrl || "/api/registration/drafts";
        const body = await postJson(`${base}/${encodeURIComponent(currentDraftId)}/publish?employee_id=${encodeURIComponent(employeeId)}`, {
          operation: isSopRegistration() ? "sop_registration_publish" : "registration_draft_publish",
          user_confirmed: true,
          note: "web registration wizard publish request",
        });
        renderResult("publish", body);
      }
    } catch (error) {
      setResult("error", "수정 필요", error.message || String(error));
    }
  }

  form.addEventListener("click", (event) => {
    const wizardNav = event.target.closest("[data-wizard-nav]");
    if (wizardNav) {
      moveWizard(wizardNav.dataset.wizardNav === "prev" ? -1 : 1);
      return;
    }
    const wizardSave = event.target.closest("[data-wizard-save]");
    if (wizardSave) {
      writeLocalAutosave();
      void pushServerAutosave()
        .then(() => setResult("ok", "임시저장했습니다", "화면을 벗어나도 이어서 작성할 수 있습니다."))
        .catch((error) => setResult("warning", "로컬에 임시저장했습니다", error.message || "서버 자동저장은 나중에 다시 시도됩니다."));
      return;
    }
    const eventAdapterButton = event.target.closest("[data-event-adapter-action]");
    if (eventAdapterButton) {
      void handleEventAdapterAction(eventAdapterButton.dataset.eventAdapterAction || "plan");
      return;
    }
    const artifactUploadButton = event.target.closest("[data-artifact-upload]");
    if (artifactUploadButton) {
      void uploadDataLakeArtifact(artifactUploadButton);
      return;
    }
    const artifactRemoveButton = event.target.closest("[data-artifact-remove]");
    if (artifactRemoveButton) {
      void removeDataLakeArtifact(artifactRemoveButton);
      return;
    }
    const removeLinkButton = event.target.closest("[data-remove-link]");
    if (removeLinkButton) {
      removeSelectedLink(removeLinkButton.dataset.removeLink || "", removeLinkButton.dataset.removeValue || "");
      scheduleAutosave();
      return;
    }
    const autosaveButton = event.target.closest("[data-autosave-action]");
    if (autosaveButton) {
      const action = autosaveButton.dataset.autosaveAction || "";
      if (action === "restore") restoreAutosaveState();
      if (action === "new") {
        void discardAutosaveState().then(() => setResult("ok", "새 초안으로 시작합니다", "이전 자동저장 상태는 숨겼습니다."));
      }
      if (action === "delete") {
        void discardAutosaveState().then(() => setResult("ok", "자동저장 초안을 삭제했습니다", "현재 화면에서 새로 작성할 수 있습니다."));
      }
      return;
    }
    const stageSuggestionButton = event.target.closest("[data-apply-stage-suggestions]");
    if (stageSuggestionButton) {
      const suggestions = Array.isArray(currentPlan?.workflow_task_suggestions)
        ? currentPlan.workflow_task_suggestions
        : (Array.isArray(currentPlan?.workflow_stage_suggestions) ? currentPlan.workflow_stage_suggestions : []);
      if (suggestions.length) {
        workflowStages = suggestions.map((stage) => makeStage(stage));
        selectedStageId = workflowStages[0]?.stage_id || "";
        renderWorkflowStages();
        scheduleAutosave();
        setResult("ok", "Task 추천을 적용했습니다", "각 Task를 선택해 실행 방식, Action, 근거를 보강하세요.");
      }
      return;
    }
    const stageSelectButton = event.target.closest("[data-stage-select]");
    if (stageSelectButton) {
      selectedStageId = stageSelectButton.dataset.stageSelect || "";
      renderWorkflowStages();
      scheduleAutosave();
      return;
    }
    const stageActionButton = event.target.closest("[data-stage-action]");
    if (stageActionButton) {
      const action = stageActionButton.dataset.stageAction || "";
      if (action === "add") addWorkflowStage({stage_name: `새 Task ${workflowStages.length + 1}`});
      if (action === "remove") removeSelectedWorkflowStage();
      if (action === "attach-selected-action") {
        if (selectedConnectorKind() === "skill" || formField("skill_ref")?.value) attachSelectedSkillToStage();
        else attachSelectedActionToStage();
      }
      if (action === "remove-action") {
        const stage = selectedStage();
        const index = Number(stageActionButton.dataset.actionIndex || "-1");
        if (stage && Array.isArray(stage.actions) && index >= 0) {
          stage.actions.splice(index, 1);
          renderWorkflowStages();
          scheduleAutosave();
        }
      }
      if (action === "remove-skill") {
        const stage = selectedStage();
        const index = Number(stageActionButton.dataset.skillIndex || "-1");
        if (stage && Array.isArray(stage.skills) && index >= 0) {
          stage.skills.splice(index, 1);
          renderWorkflowStages();
          scheduleAutosave();
        }
      }
      return;
    }
    const removeDraftValueButton = event.target.closest("[data-remove-draft-value]");
    if (removeDraftValueButton) {
      removeDraftFieldValue(removeDraftValueButton.dataset.removeDraftValue || "", removeDraftValueButton.dataset.removeValue || "");
      scheduleAutosave();
      return;
    }
    const draftApplyButton = event.target.closest("[data-draft-suggestion-apply]");
    if (draftApplyButton) {
      applyDraftSuggestion(draftApplyButton.dataset.draftSuggestionApply || "");
      scheduleAutosave();
      return;
    }
    const draftCancelButton = event.target.closest("[data-draft-suggestion-cancel]");
    if (draftCancelButton) {
      const section = draftCancelButton.dataset.draftSuggestionCancel || "";
      clearDraftSuggestionTimer(section);
      const card = form.querySelector(`[data-draft-suggestion="${section}"]`);
      if (card) card.hidden = true;
      scheduleAutosave();
      return;
    }
    const draftCompareButton = event.target.closest("[data-draft-suggestion-compare]");
    if (draftCompareButton) {
      const section = draftCompareButton.dataset.draftSuggestionCompare || "";
      const details = form.querySelector(`[data-draft-suggestion="${section}"] .draft-suggestion-preview`);
      if (details) details.open = !details.open;
      return;
    }
    const draftEditButton = event.target.closest("[data-draft-suggestion-edit]");
    if (draftEditButton) {
      const section = draftEditButton.dataset.draftSuggestionEdit || "";
      clearDraftSuggestionTimer(section);
      const firstInput = form.querySelector(`[data-draft-input="${section}"]`);
      if (firstInput) firstInput.focus();
      return;
    }
    const draftUndoButton = event.target.closest("[data-draft-suggestion-undo]");
    if (draftUndoButton) {
      const section = draftUndoButton.dataset.draftSuggestionUndo || "";
      restoreSnapshot(draftSuggestionSnapshots[section] || {});
      const card = form.querySelector(`[data-draft-suggestion="${section}"]`);
      if (card) card.hidden = true;
      scheduleAutosave();
      return;
    }
    const closeButton = event.target.closest("[data-picker-close]");
    if (closeButton) {
      closePicker();
      return;
    }
    const folderButton = event.target.closest("[data-pick-folder]");
    if (folderButton) {
      const folder = folderButton.dataset.pickFolder || "";
      const folderInput = formField("folder");
      if (folderInput) folderInput.value = folder;
      setResult("ok", "폴더를 선택했습니다", folder || "All Accessible");
      closePicker();
      return;
    }
    const linkButton = event.target.closest("[data-pick-link]");
    if (linkButton) {
      const value = linkButton.dataset.pickLink || "";
      const targetField = linkButton.dataset.targetField || "";
      if (value && targetField) {
        setFieldValue(targetField, value, {
          label: linkButton.dataset.pickLabel || "",
          description: linkButton.dataset.pickDescription || "",
          technicalLabel: linkButton.dataset.pickTechnicalLabel || value,
        });
        scheduleAutosave();
      }
      setResult("ok", "연결 항목을 선택했습니다", linkButton.dataset.pickLabel || value);
      closePicker();
      return;
    }
    const linkPickerButton = event.target.closest("[data-link-picker]");
    if (linkPickerButton) {
      void handleLinkPicker(linkPickerButton.dataset.linkPicker || "", linkPickerButton.dataset.targetField || "").catch((error) => {
        setResult("error", "후보를 불러오지 못했습니다", error.message || String(error));
      });
      return;
    }
    const catalogSearchButton = event.target.closest("[data-catalog-search]");
    if (catalogSearchButton) {
      const targetField = catalogSearchButton.dataset.targetField || "";
      void handleLinkPicker(catalogSearchButton.dataset.catalogSearch || "", targetField, {inline: Boolean(inlinePicker(targetField)), page: 1}).catch((error) => {
        setResult("error", "후보를 불러오지 못했습니다", error.message || String(error));
      });
      return;
    }
    const catalogPageButton = event.target.closest("[data-catalog-page]");
    if (catalogPageButton) {
      const targetField = catalogPageButton.dataset.targetField || "";
      void handleLinkPicker(catalogPageButton.dataset.catalogPage || "", targetField, {
        inline: Boolean(inlinePicker(targetField)),
        page: catalogPageButton.dataset.page || "1",
        pageSize: catalogPageButton.dataset.pageSize || "8",
      }).catch((error) => {
        setResult("error", "후보를 불러오지 못했습니다", error.message || String(error));
      });
      return;
    }
    const connectorButton = event.target.closest("[data-connector-kind]");
    if (connectorButton) {
      const connectorKind = connectorButton.dataset.connectorKind || "";
      setConnectorKind(connectorKind);
      if (connectorKind === "skill") {
        void handleLinkPicker("skills", "skill_ref", {inline: true, page: 1, pageSize: 8}).catch((error) => {
          setResult("error", "Skill 후보를 불러오지 못했습니다", error.message || String(error));
        });
      }
      updateSectionRefineControls();
      scheduleAutosave();
      return;
    }
    const sectionModeButton = event.target.closest("[data-section-mode]");
    if (sectionModeButton) {
      setSectionMode(sectionModeButton.dataset.sectionMode || "", sectionModeButton.dataset.modeValue || "skip", {fromUser: true});
      scheduleAutosave();
      return;
    }
    const refineButton = event.target.closest("[data-section-refine]");
    if (refineButton) {
      void prepareSectionDraftSuggestion(refineButton.dataset.sectionRefine || "");
      return;
    }
    const applyButton = event.target.closest("[data-apply-suggestion]");
    if (applyButton) {
      let payload = {};
      try {
        payload = JSON.parse(decodeURIComponent(applyButton.dataset.applyJson || "%7B%7D"));
      } catch (_error) {
        payload = {};
      }
      for (const [key, value] of Object.entries(payload)) {
        if (key.endsWith("_mode")) {
          setSectionMode(key, String(value || "skip"));
        } else if (key === "connector_kind") {
          setConnectorKind(String(value || "manual"));
        } else {
          setFieldValue(key, value);
        }
      }
      setFlowStage("entry");
      setResult("ok", "추천을 반영했습니다", "선택한 추천이 해당 섹션에 들어갔습니다. 필요하면 실행 전 확인으로 이어가세요.");
      scheduleAutosave();
      return;
    }
    const assistButton = event.target.closest("[data-registration-assist]");
    if (assistButton) {
      void handleAction("plan");
      return;
    }
    const button = event.target.closest("[data-registration-action]");
    if (!button || button.disabled) return;
    void handleAction(button.dataset.registrationAction);
  });

  page.addEventListener("click", (event) => {
    const stepButton = event.target.closest("[data-registration-step]");
    if (!stepButton || !page.contains(stepButton)) return;
    event.preventDefault();
    const step = stepButton.dataset.registrationStep || "";
    if (stepOrderIndex(step) < 0) return;
    if (currentStep === "context" && stepOrderIndex(step) > 0 && !hasRecommendationInput()) {
      setResult("warning", "업무 맥락을 먼저 적어주세요", "내 업무를 어떤 맥락에서 판단하고 기록할지 한 줄이라도 적으면 다음 단계로 이동할 수 있습니다.");
      return;
    }
    setFlowStage(step);
    scheduleAutosave();
  });

  form.addEventListener("input", (event) => {
    if (event.target.closest("[data-schedule-field]") || event.target.closest("[data-schedule-weekday]")) {
      updateScheduleBuilder();
      scheduleAutosave();
      return;
    }
    const stageField = event.target.closest("[data-stage-field]");
    if (stageField) {
      updateSelectedStageField(stageField);
      return;
    }
    const draftInput = event.target.closest("[data-draft-input]");
    if (draftInput) {
      const section = draftInput.dataset.draftInput || "";
      clearDraftSuggestionTimer(section);
      currentPlan = null;
      renderDraftFieldChips(draftInput.name || "");
      updateSectionRefineControls();
      if (section === "sop") {
        workflowStages = splitList(formField("steps")?.value || "").map((name, index) => workflowStages[index] ? {...workflowStages[index], stage_name: name} : makeStage({stage_name: name}));
        selectedStageId = workflowStages[0]?.stage_id || selectedStageId;
        renderWorkflowStages();
      }
      scheduleAutosave();
      return;
    }
    if (["raw_request", "title", "business_goal"].includes(event.target.name || "")) {
      currentPlan = null;
      updateRecommendationControls();
      scheduleAutosave();
      return;
    }
    if (["work_target", "work_situation", "decision_question", "required_evidence_context", "expected_result", "knowledge_update_goal", "event_source_kind"].includes(event.target.name || "") || event.target.name?.startsWith("event_source_config.")) {
      currentPlan = null;
      syncHiddenModels();
      renderWorkflowStages();
      updateRecommendationControls();
      scheduleAutosave();
      return;
    }
    if (event.target.closest("[data-connector-field]")) {
      currentPlan = null;
      updateSectionRefineControls();
      scheduleAutosave();
      return;
    }
    const directCron = event.target.closest("[data-schedule-cron-direct]");
    if (directCron) {
      const cronField = formField("cron");
      if (cronField) cronField.value = directCron.value || "";
      scheduleAutosave();
    }
  });

  form.addEventListener("keydown", (event) => {
    const queryInput = event.target.closest("[data-catalog-query]");
    if (!queryInput || event.key !== "Enter") return;
    event.preventDefault();
    const targetField = queryInput.dataset.catalogQuery || "";
    void handleLinkPicker(queryInput.dataset.catalogKind || "", targetField, {
      inline: Boolean(inlinePicker(targetField)),
      page: 1,
    }).catch((error) => {
      setResult("error", "후보를 불러오지 못했습니다", error.message || String(error));
    });
  });

  form.addEventListener("change", (event) => {
    const stageField = event.target.closest("[data-stage-field]");
    if (stageField) {
      updateSelectedStageField(stageField);
      return;
    }
    if (event.target.closest("[data-schedule-field]") || event.target.closest("[data-schedule-weekday]")) {
      updateScheduleBuilder();
      scheduleAutosave();
      return;
    }
    if ((event.target.name || "") === "event_source_kind") {
      const adapterField = formField("event_producer_adapter_plan");
      if (adapterField) adapterField.value = "";
      updateEventSourcePanels();
      syncHiddenModels();
      scheduleAutosave();
      return;
    }
    if (event.target.name) scheduleAutosave();
  });

  form.querySelectorAll("[data-artifact-panel]").forEach((panel) => {
    panel.addEventListener("dragover", (event) => {
      event.preventDefault();
      panel.classList.add("drag-over");
    });
    panel.addEventListener("dragleave", () => {
      panel.classList.remove("drag-over");
    });
    panel.addEventListener("drop", (event) => {
      event.preventDefault();
      panel.classList.remove("drag-over");
      const uploadButton = panel.querySelector("[data-artifact-upload]");
      const files = Array.from(event.dataTransfer?.files || []);
      if (uploadButton && files.length) void uploadDataLakeArtifact(uploadButton, files);
    });
  });

  setFlowStage(currentStep);
  ["event_mode", "sop_mode", "action_mode"].forEach((name) => {
    const field = formField(name);
    setSectionMode(name, field?.value || "skip");
  });
  setConnectorKind(selectedConnectorKind() || "manual");
  updateEventSourcePanels();
  renderWorkflowStages();
  updateScheduleBuilder();
  updateRecommendationControls();
  updateSectionRefineControls();
  renderArtifactResults();
  ["linked_sop_ref", "linked_workflow_definition_key", "linked_event_types", "linked_action_keys", "skill_ref"].forEach(updateSelectedLink);
  showAutosaveBannerIfNeeded();
})();
