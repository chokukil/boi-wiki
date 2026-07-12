(function () {
  const SOURCE_OPTIONS = [
    { kind: "boi", label: "BoI 문서", searchable: true, kinds: ["document", "sop", "workflow", "dictionary", "skill"] },
    { kind: "event", label: "업무 이벤트", searchable: true, kinds: ["event"] },
    { kind: "action_result", label: "Action 결과", searchable: true, kinds: ["action"] },
    { kind: "data_artifact", label: "데이터", searchable: false },
    { kind: "file", label: "파일", searchable: false },
    { kind: "human_note", label: "담당자 메모", searchable: false },
    { kind: "external_ai", label: "외부 AI 요약", searchable: false },
  ];
  const SOURCE_LABELS = Object.fromEntries(SOURCE_OPTIONS.map((item) => [item.kind, item.label]));
  const BINDING_LABELS = {
    event: "업무 이벤트",
    action_result: "Action 결과",
    artifact: "데이터/결과물",
    data_field: "데이터 값",
    state: "상태 변화",
    none: "연결되지 않음",
  };
  const MODE_COPY = {
    manual: {
      completion: "담당자가 확인하고 체크할 완료 모습을 적어주세요.",
      evidence: "담당자가 업무를 마치기 전에 확인할 자료를 골라주세요.",
      example: "담당자가 확인 결과와 판단을 기록했어요",
    },
    copilot: {
      completion: "AI가 자료를 준비한 뒤 담당자가 마지막으로 확인할 모습을 적어주세요.",
      evidence: "AI가 찾아오거나 담당자가 직접 넣을 자료를 골라주세요.",
      example: "AI가 준비한 자료를 담당자가 확인했어요",
    },
    autopilot: {
      completion: "시스템에서 실제로 확인할 수 있는 변화나 결과를 적어주세요.",
      evidence: "자동으로 조회할 수 있는 이벤트, Action 결과 또는 데이터를 연결해주세요.",
      example: "연결된 시스템에서 완료 상태가 확인되었어요",
    },
  };

  const clone = (value) => JSON.parse(JSON.stringify(value || {}));
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
  const uid = (prefix) => `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 9)}`;

  function sourceKindFromRef(ref) {
    const value = String(ref || "").toLowerCase();
    if (value.startsWith("event:") || value.includes(":event-types:")) return "event";
    if (value.startsWith("action:")) return "action_result";
    if (value.startsWith("data:") || value.includes("artifact")) return "data_artifact";
    if (value.startsWith("boi:") || value.startsWith("workflow:") || value.startsWith("skill:")) return "boi";
    return "human_note";
  }

  function friendlyText(value, kind) {
    const text = String(value || "").trim();
    if (!text) return "";
    const known = {
      review_note: "담당자 검토 기록",
      alarm_context: "Alarm 맥락",
      trend_history: "Trend 이력",
      raw_data: "Raw Data",
      action_results: "Action 결과",
      current_event: "현재 업무 이벤트",
    };
    if (known[text]) return known[text];
    if (/^(boi|event|action|workflow|skill|data):/i.test(text)) {
      if (text.includes(":dictionary:")) {
        const term = text.split(":").pop() || "업무 용어";
        return term.toLowerCase() === "alarm" ? "Alarm" : term.replaceAll("-", " ");
      }
      if (text.includes(":event-types:") || text.startsWith("event:")) return "업무 이벤트 확인 자료";
      if (text.startsWith("action:")) return "Action 실행 결과";
      if (text.startsWith("workflow:") || text.includes(":workflows:")) return "관련 업무 흐름";
      if (text.startsWith("data:")) return "연결된 데이터";
      return kind === "check" ? "업무 완료 상태가 확인되었어요" : "연결된 BoI 자료";
    }
    return text.replace(/식별됨$/u, "확인되었어요").replace(/확인됨$/u, "확인되었어요").replace(/기록됨$/u, "기록되었어요");
  }

  function normalizeDesign(task) {
    const mode = ["manual", "copilot", "autopilot"].includes(task?.execution_mode) ? task.execution_mode : "copilot";
    const raw = task?.completion_design && typeof task.completion_design === "object" ? clone(task.completion_design) : {};
    const checks = Array.isArray(raw.checks) && raw.checks.length
      ? raw.checks
      : (Array.isArray(task?.exit_criteria) ? task.exit_criteria : []).map((label) => ({ label }));
    const evidence = Array.isArray(raw.evidence) && raw.evidence.length
      ? raw.evidence
      : (Array.isArray(task?.required_evidence) ? task.required_evidence : []).map((label) => ({ label }));
    return {
      version: 1,
      checks: checks.map((item) => {
        const value = typeof item === "object" ? item : { label: item };
        const binding = value.binding && typeof value.binding === "object" ? clone(value.binding) : {};
        return {
          check_id: value.check_id || uid("check"),
          label: friendlyText(value.label || binding.ref, "check"),
          confirmation: value.confirmation || (mode === "autopilot" ? "system" : "human"),
          binding,
        };
      }).filter((item) => item.label),
      evidence: evidence.map((item) => {
        const value = typeof item === "object" ? item : { label: item };
        const ref = String(value.ref || (/^(boi|event|action|workflow|skill|data):/i.test(String(value.label || "")) ? value.label : ""));
        const sourceKind = value.source_kind || sourceKindFromRef(ref);
        return {
          evidence_id: value.evidence_id || uid("evidence"),
          label: friendlyText(value.label || ref, "evidence"),
          source_kind: sourceKind,
          ref,
          provided_by: value.provided_by || (mode === "manual" ? "human" : mode === "autopilot" ? "system" : "agent"),
          required: value.required !== false,
        };
      }).filter((item) => item.label),
    };
  }

  function projection(design) {
    return {
      exit_criteria: (design?.checks || []).map((item) => String(item.label || "").trim()).filter(Boolean),
      required_evidence: (design?.evidence || []).map((item) => String(item.ref || item.label || "").trim()).filter(Boolean),
    };
  }

  function readiness(mode, design) {
    const checks = design?.checks || [];
    const evidence = design?.evidence || [];
    if (!checks.length || !evidence.length) {
      return { status: "incomplete", label: "완료 항목을 더 적어주세요", automation_ready: false };
    }
    if (mode !== "autopilot") {
      return { status: "human_confirmation", label: "담당자 확인으로 완료", automation_ready: false };
    }
    const checksReady = checks.every((item) => item.confirmation === "system" && item.binding?.kind && item.binding.kind !== "none" && (item.binding.ref || item.binding.field));
    const evidenceReady = evidence.filter((item) => item.required !== false).every((item) => item.provided_by === "system" && item.ref);
    const ready = checksReady && evidenceReady;
    return { status: ready ? "ready" : "needs_connection", label: ready ? "자동 확인 가능" : "연결 필요", automation_ready: ready };
  }

  function bindingKindForSource(sourceKind) {
    return { event: "event", action_result: "action_result", data_artifact: "artifact" }[sourceKind] || "none";
  }

  function createEditor(container, options = {}) {
    if (!container) return null;
    const state = {
      mode: "copilot",
      design: { version: 1, checks: [], evidence: [] },
      picker: null,
      searchResults: [],
      searchBusy: false,
      searchTimer: null,
      hydrating: false,
    };

    function notify() {
      if (state.hydrating) return;
      options.onChange?.(clone(state.design), readiness(state.mode, state.design));
    }

    function connectionRows() {
      const rows = [];
      state.design.checks.forEach((item) => {
        if (!item.binding?.ref && !item.binding?.field) return;
        rows.push(`<article><div><strong>${escapeHtml(item.label)}</strong><span>${escapeHtml(BINDING_LABELS[item.binding.kind] || "자동 확인")}</span></div><code>${escapeHtml(item.binding.ref || item.binding.field)}</code></article>`);
      });
      state.design.evidence.forEach((item) => {
        if (!item.ref) return;
        rows.push(`<article><div><strong>${escapeHtml(item.label)}</strong><span>${escapeHtml(SOURCE_LABELS[item.source_kind] || "확인 자료")}</span></div><code>${escapeHtml(item.ref)}</code><label><input type="checkbox" data-completion-required="${escapeHtml(item.evidence_id)}" ${item.required !== false ? "checked" : ""} /> 꼭 확인할 자료</label></article>`);
      });
      return rows.length ? rows.join("") : "<p>아직 시스템에 연결된 항목이 없습니다.</p>";
    }

    function pickerHtml() {
      if (!state.picker) return "";
      const option = SOURCE_OPTIONS.find((item) => item.kind === state.picker.sourceKind) || SOURCE_OPTIONS[0];
      const targetLabel = state.picker.checkId ? "완료 상태 연결" : "확인할 자료 추가";
      const results = state.searchResults.map((item) => `<button type="button" data-completion-search-result="${escapeHtml(item.evidence_id)}"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.summary || SOURCE_LABELS[option.kind])}</span></button>`).join("");
      return `<section class="task-completion-picker"><header><strong>${escapeHtml(targetLabel)} · ${escapeHtml(option.label)}</strong><button type="button" aria-label="닫기" data-completion-picker-close>×</button></header><div><input data-completion-picker-input placeholder="${option.searchable ? "이름이나 업무 용어로 검색" : "화면에 보일 쉬운 이름"}" value="${escapeHtml(state.picker.query || "")}" /><button type="button" data-completion-picker-add ${option.searchable ? "hidden" : ""}>추가</button></div>${option.searchable ? `<div class="task-completion-search-results">${state.searchBusy ? "<p>찾고 있습니다.</p>" : results || "<p>검색어를 입력하면 연결할 후보가 표시됩니다.</p>"}</div>` : ""}</section>`;
    }

    function render() {
      const copy = MODE_COPY[state.mode] || MODE_COPY.copilot;
      const status = readiness(state.mode, state.design);
      const statusClass = status.status === "needs_connection" || status.status === "incomplete" ? "needs-attention" : "ready";
      container.innerHTML = `
        <section class="task-completion-block">
          <header><div><strong>언제 이 일이 끝났다고 볼까요?</strong><p>${escapeHtml(copy.completion)}</p></div><span class="task-completion-status ${statusClass}">${escapeHtml(status.label)}</span></header>
          <div class="task-completion-list">
            ${state.design.checks.map((item, index) => `<div class="task-completion-row"><textarea rows="2" data-completion-check-label="${escapeHtml(item.check_id)}" aria-label="완료된 모습 ${index + 1}">${escapeHtml(item.label)}</textarea><div class="task-completion-row-actions"><button type="button" title="위로 이동" aria-label="위로 이동" data-completion-move-check="${escapeHtml(item.check_id)}" data-direction="-1">↑</button><button type="button" title="아래로 이동" aria-label="아래로 이동" data-completion-move-check="${escapeHtml(item.check_id)}" data-direction="1">↓</button>${state.mode === "autopilot" ? `<button type="button" class="text-button" data-completion-connect-check="${escapeHtml(item.check_id)}">${item.binding?.ref || item.binding?.field ? "연결 변경" : "연결 선택"}</button>` : ""}<button type="button" title="삭제" aria-label="삭제" data-completion-remove-check="${escapeHtml(item.check_id)}">×</button></div></div>`).join("") || `<button type="button" class="task-completion-example" data-completion-example>${escapeHtml(copy.example)}</button>`}
          </div>
          <button type="button" class="task-completion-add" data-completion-add-check>＋ 완료된 모습 추가</button>
        </section>
        <section class="task-completion-block">
          <header><div><strong>무엇을 확인하면 될까요?</strong><p>${escapeHtml(copy.evidence)}</p></div></header>
          <div class="task-evidence-list">${state.design.evidence.map((item, index) => `<article><span>${escapeHtml(SOURCE_LABELS[item.source_kind] || "확인 자료")}</span><strong>${escapeHtml(item.label)}</strong><div><button type="button" title="위로 이동" aria-label="위로 이동" data-completion-move-evidence="${escapeHtml(item.evidence_id)}" data-direction="-1">↑</button><button type="button" title="아래로 이동" aria-label="아래로 이동" data-completion-move-evidence="${escapeHtml(item.evidence_id)}" data-direction="1">↓</button><button type="button" title="삭제" aria-label="삭제" data-completion-remove-evidence="${escapeHtml(item.evidence_id)}">×</button></div></article>`).join("") || "<p>아직 확인할 자료가 없습니다.</p>"}</div>
          <div class="task-evidence-source-menu">${SOURCE_OPTIONS.map((item) => `<button type="button" data-completion-source="${item.kind}">${escapeHtml(item.label)}</button>`).join("")}</div>
          ${pickerHtml()}
        </section>
        ${state.mode === "autopilot" && status.status === "needs_connection" ? `<aside class="task-completion-guidance"><strong>자동으로 확인할 연결이 더 필요합니다.</strong><p>업무 이벤트, Action 결과 또는 데이터 연결을 보완하세요. 지금 정하기 어렵다면 Copilot으로 전환할 수 있습니다.</p><button type="button" data-completion-switch-copilot>Copilot으로 전환</button></aside>` : ""}
        <details class="task-completion-connections"><summary>연결 정보</summary><div>${connectionRows()}</div></details>
      `;
    }

    function move(list, idKey, id, direction) {
      const index = list.findIndex((item) => item[idKey] === id);
      const target = index + Number(direction || 0);
      if (index < 0 || target < 0 || target >= list.length) return;
      [list[index], list[target]] = [list[target], list[index]];
      render();
      notify();
    }

    function addEvidence(item, sourceKind) {
      const ref = String(item?.evidence_id || item?.ref || "").trim();
      const label = String(item?.title || item?.label || state.picker?.query || "").trim();
      if (!label) return;
      const providedBy = state.mode === "manual" ? "human" : state.mode === "autopilot" ? "system" : "agent";
      if (!state.design.evidence.some((entry) => entry.ref && entry.ref === ref)) {
        state.design.evidence.push({ evidence_id: uid("evidence"), label, source_kind: sourceKind, ref, provided_by: providedBy, required: true });
      }
      if (state.picker?.checkId) {
        const check = state.design.checks.find((entry) => entry.check_id === state.picker.checkId);
        if (check) {
          check.confirmation = "system";
          check.binding = { kind: bindingKindForSource(sourceKind), ref, field: "", operator: "", value: null };
        }
      }
      state.picker = null;
      state.searchResults = [];
      render();
      notify();
    }

    async function searchPicker(query) {
      const option = SOURCE_OPTIONS.find((item) => item.kind === state.picker?.sourceKind);
      if (!option?.searchable || !query.trim() || !options.search) {
        state.searchResults = [];
        state.searchBusy = false;
        render();
        return;
      }
      state.searchBusy = true;
      render();
      try {
        state.searchResults = await options.search(query.trim(), option.kinds);
      } catch (_error) {
        state.searchResults = [];
      }
      state.searchBusy = false;
      render();
      container.querySelector("[data-completion-picker-input]")?.focus();
    }

    container.addEventListener("input", (event) => {
      const checkId = event.target.dataset.completionCheckLabel;
      if (checkId) {
        const check = state.design.checks.find((item) => item.check_id === checkId);
        if (check) check.label = event.target.value;
        notify();
        return;
      }
      if (event.target.matches("[data-completion-picker-input]")) {
        state.picker.query = event.target.value;
        clearTimeout(state.searchTimer);
        state.searchTimer = window.setTimeout(() => searchPicker(state.picker?.query || ""), 280);
      }
    });

    container.addEventListener("change", (event) => {
      const evidenceId = event.target.dataset.completionRequired;
      if (!evidenceId) return;
      const item = state.design.evidence.find((entry) => entry.evidence_id === evidenceId);
      if (item) item.required = event.target.checked;
      notify();
    });

    container.addEventListener("click", (event) => {
      const button = event.target.closest("button");
      if (!button) return;
      if (button.matches("[data-completion-add-check]")) {
        state.design.checks.push({ check_id: uid("check"), label: "", confirmation: state.mode === "autopilot" ? "system" : "human", binding: {} });
        render();
        container.querySelector("[data-completion-check-label]:last-of-type")?.focus();
        notify();
        return;
      }
      if (button.matches("[data-completion-example]")) {
        state.design.checks.push({ check_id: uid("check"), label: MODE_COPY[state.mode].example, confirmation: state.mode === "autopilot" ? "system" : "human", binding: {} });
        render();
        notify();
        return;
      }
      if (button.dataset.completionRemoveCheck) {
        state.design.checks = state.design.checks.filter((item) => item.check_id !== button.dataset.completionRemoveCheck);
        render(); notify(); return;
      }
      if (button.dataset.completionMoveCheck) {
        move(state.design.checks, "check_id", button.dataset.completionMoveCheck, button.dataset.direction); return;
      }
      if (button.dataset.completionRemoveEvidence) {
        state.design.evidence = state.design.evidence.filter((item) => item.evidence_id !== button.dataset.completionRemoveEvidence);
        render(); notify(); return;
      }
      if (button.dataset.completionMoveEvidence) {
        move(state.design.evidence, "evidence_id", button.dataset.completionMoveEvidence, button.dataset.direction); return;
      }
      if (button.dataset.completionConnectCheck) {
        state.picker = { sourceKind: "event", checkId: button.dataset.completionConnectCheck, query: "" };
        state.searchResults = [];
        render();
        container.querySelector("[data-completion-picker-input]")?.focus();
        return;
      }
      if (button.dataset.completionSource) {
        state.picker = { sourceKind: button.dataset.completionSource, checkId: state.picker?.checkId || "", query: "" };
        state.searchResults = [];
        render();
        container.querySelector("[data-completion-picker-input]")?.focus();
        return;
      }
      if (button.matches("[data-completion-picker-close]")) {
        state.picker = null; state.searchResults = []; render(); return;
      }
      if (button.matches("[data-completion-picker-add]")) {
        addEvidence({ label: state.picker?.query || "" }, state.picker?.sourceKind || "human_note"); return;
      }
      if (button.dataset.completionSearchResult) {
        const item = state.searchResults.find((entry) => entry.evidence_id === button.dataset.completionSearchResult);
        if (item) addEvidence(item, state.picker?.sourceKind || sourceKindFromRef(item.evidence_id));
        return;
      }
      if (button.matches("[data-completion-switch-copilot]")) {
        options.onModeRequest?.("copilot");
      }
    });

    return {
      setTask(task) {
        state.hydrating = true;
        state.mode = ["manual", "copilot", "autopilot"].includes(task?.execution_mode) ? task.execution_mode : "copilot";
        state.design = normalizeDesign(task || {});
        state.picker = null;
        state.searchResults = [];
        render();
        state.hydrating = false;
      },
      setMode(mode) {
        if (!["manual", "copilot", "autopilot"].includes(mode) || mode === state.mode) return;
        state.mode = mode;
        state.design.checks.forEach((item) => { item.confirmation = mode === "autopilot" ? "system" : "human"; });
        state.design.evidence.forEach((item) => { item.provided_by = mode === "manual" ? "human" : mode === "autopilot" ? "system" : "agent"; });
        render();
        notify();
      },
      getDesign() { return clone(state.design); },
      getProjection() { return projection(state.design); },
      getReadiness() { return readiness(state.mode, state.design); },
      render,
    };
  }

  window.BoiTaskCompletion = {
    createEditor,
    normalizeDesign,
    projection,
    readiness,
    sourceOptions: clone(SOURCE_OPTIONS),
  };
})();
