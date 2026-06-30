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
  let currentStep = "plan";

  const listFields = new Set([
    "steps",
    "evidence_requirements",
    "payload_fields",
    "input_fields",
    "output_fields",
    "linked_event_types",
    "linked_action_keys",
    "payload_fields",
  ]);
  const connectorListFields = new Set([
    "connector_config.idempotency_key_fields",
  ]);
  const jsonFields = new Set(["schedule_config"]);
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
  }

  function isSopRegistration() {
    return form.dataset.apiUrl?.includes("/api/sop-registration/");
  }

  function setFlowStage(step) {
    currentStep = step || "plan";
    form.querySelectorAll("[data-step-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.stepPanel !== currentStep;
    });
    document.querySelectorAll("[data-registration-step]").forEach((item) => {
      item.classList.toggle("active", item.dataset.registrationStep === currentStep);
      item.classList.toggle("complete", stepOrderIndex(item.dataset.registrationStep) < stepOrderIndex(currentStep));
    });
  }

  function stepOrderIndex(step) {
    return ["plan", "preview", "create", "validate"].indexOf(step);
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

  function formField(name) {
    const field = form.elements[name];
    if (!field) return null;
    return field instanceof RadioNodeList ? field[0] : field;
  }

  function updateSelectedLink(name) {
    const output = form.querySelector(`[data-selected-link="${name}"]`);
    if (!output) return;
    const field = formField(name);
    const value = field?.value || "";
    output.textContent = value || "선택 안 됨";
    output.classList.toggle("selected", Boolean(value));
  }

  function setFieldValue(name, value) {
    const field = formField(name);
    if (!field) return;
    if (listFields.has(name)) {
      const incoming = Array.isArray(value) ? value : splitList(value);
      const current = splitList(field.value);
      for (const item of incoming) {
        if (item && !current.includes(item)) current.push(item);
      }
      field.value = current.join(", ");
    } else if (jsonFields.has(name)) {
      field.value = typeof value === "string" ? value : JSON.stringify(value || {});
    } else {
      field.value = value;
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
  }

  const modeLabels = {
    reuse: "기존 항목",
    draft: "새 초안",
    pattern: "이력 패턴",
    schedule: "Schedule",
    lightweight: "간단 절차",
    manual: "Manual",
    skip: "건너뛰기",
  };

  function setSectionMode(name, value) {
    const field = formField(name);
    if (field) field.value = value || "skip";
    form.querySelectorAll(`[data-section-mode="${name}"]`).forEach((button) => {
      const selected = button.dataset.modeValue === (value || "skip");
      button.classList.toggle("selected", selected);
      button.setAttribute("aria-pressed", selected ? "true" : "false");
    });
    const label = form.querySelector(`[data-mode-label="${name}"]`);
    if (label) label.textContent = modeLabels[value || "skip"] || value || "건너뛰기";
    updateModeFields(name, value || "skip");
    if (name === "event_mode") updateScheduleBuilder();
  }

  function updateModeFields(name, value) {
    const prefix = name.replace("_mode", "");
    form.querySelectorAll(`[data-${prefix}-mode-field]`).forEach((item) => {
      const allowed = String(item.dataset[`${prefix}ModeField`] || "").split(/\s+/).filter(Boolean);
      item.hidden = !allowed.includes(value || "skip");
    });
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
      const sections = [body.event_section, body.sop_section, ...(body.action_sections || [])].filter(Boolean);
      return `
        <strong>SOP 실행 흐름 추천</strong>
        <div class="registration-result-summary">
          <span class="badge">SOP 추가</span>
          <span>${escapeHtml(body?.recommended_next_step || "필요한 섹션만 선택하세요.")}</span>
        </div>
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
      agentSuggestions.innerHTML = `<p class="muted">아직 반영할 제안이 없습니다. 설명을 조금 더 적고 추천을 받아보세요.</p>`;
      return;
    }
    agentSuggestions.innerHTML = `
      <div class="registration-agent-suggestion-list">
        ${sections.slice(0, 8).map((item, index) => {
          const payload = encodeURIComponent(JSON.stringify(item.apply || {}));
          return `
            <article class="registration-agent-suggestion-card">
              <span class="badge">${escapeHtml(item.section || "제안")}</span>
              <strong>${escapeHtml(item.label || "추천")}</strong>
              <p>${escapeHtml(item.description || "")}</p>
              <button type="button" class="secondary-button" data-apply-suggestion="${index}" data-apply-json="${payload}">반영</button>
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

  function renderLinkCandidates(kind, targetField, body) {
    const labels = {
      sops: "SOP",
      workflow_definitions: "업무 흐름",
      event_types: "Event",
      actions: "Action",
    };
    const candidates = body?.groups?.[kind] || [];
    setPicker(`
      <div class="registration-picker-heading">
        <div>
          <strong>${escapeHtml(labels[kind] || "항목")} 선택</strong>
          <p class="muted">입력한 설명과 현재 폴더 기준으로 연결 후보를 찾았습니다.</p>
        </div>
        <button type="button" class="secondary-button" data-picker-close>닫기</button>
      </div>
      <div class="registration-result-list">
        ${candidates.length ? candidates.map((item) => `
          <button
            type="button"
            class="registration-result-card selectable"
            data-pick-link="${escapeHtml(item.value || "")}"
            data-target-field="${escapeHtml(targetField || "")}"
          >
            <strong>${escapeHtml(item.label || item.value || "후보")}</strong>
            <span>${escapeHtml(item.description || item.value || "")}</span>
          </button>
        `).join("") : `<p class="muted">선택할 후보가 없습니다. 설명을 더 구체적으로 적거나 직접 ID를 입력하세요.</p>`}
      </div>
    `);
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
      setFlowStage("preview");
    } else if (action === "explorer") {
      html = renderExplorer(body);
    } else if (action === "preview") {
      html = renderPreview(body);
      setFlowStage("create");
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
      setFlowStage("validate");
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

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: "POST",
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

  function setDraftButtons(enabled) {
    form.querySelector('[data-registration-action="validate"]')?.toggleAttribute("disabled", !enabled);
    form.querySelector('[data-registration-action="publish"]')?.toggleAttribute("disabled", !enabled);
  }

  async function handleLinkPicker(kind, targetField) {
    const payload = collectPayload();
    const search = encodeURIComponent(payload.raw_request || payload.title || payload.business_goal || payload.description || "");
    const scope = encodeURIComponent(payload.scope || "all");
    const folder = encodeURIComponent(payload.folder || "");
    const response = await fetch(`${form.dataset.linkCandidatesUrl}&q=${search}&scope=${scope}&folder=${folder}`, {
      headers: {"Accept": "application/json"},
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || response.statusText);
    renderLinkCandidates(kind, targetField, body);
  }

  async function handleAction(action) {
    const payload = collectPayload();
    try {
      if (action === "plan") {
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
      if (value && targetField) setFieldValue(targetField, value);
      setResult("ok", "연결 항목을 선택했습니다", value);
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
    const connectorButton = event.target.closest("[data-connector-kind]");
    if (connectorButton) {
      setConnectorKind(connectorButton.dataset.connectorKind || "");
      return;
    }
    const sectionModeButton = event.target.closest("[data-section-mode]");
    if (sectionModeButton) {
      setSectionMode(sectionModeButton.dataset.sectionMode || "", sectionModeButton.dataset.modeValue || "skip");
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
      setFlowStage("preview");
      setResult("ok", "Agent 제안을 반영했습니다", "선택한 제안이 해당 섹션에 들어갔습니다. 필요하면 실행 전 확인으로 이어가세요.");
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

  form.addEventListener("input", (event) => {
    if (event.target.closest("[data-schedule-field]") || event.target.closest("[data-schedule-weekday]")) {
      updateScheduleBuilder();
      return;
    }
    const directCron = event.target.closest("[data-schedule-cron-direct]");
    if (directCron) {
      const cronField = formField("cron");
      if (cronField) cronField.value = directCron.value || "";
    }
  });

  form.addEventListener("change", (event) => {
    if (event.target.closest("[data-schedule-field]") || event.target.closest("[data-schedule-weekday]")) {
      updateScheduleBuilder();
    }
  });

  setFlowStage(currentStep);
  ["event_mode", "sop_mode", "action_mode"].forEach((name) => {
    const field = formField(name);
    setSectionMode(name, field?.value || "skip");
  });
  setConnectorKind(selectedConnectorKind() || "manual");
  updateScheduleBuilder();
  ["linked_sop_ref", "linked_workflow_definition_key", "linked_event_types", "linked_action_keys"].forEach(updateSelectedLink);
})();
