(() => {
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

  function employeeId() {
    return new URLSearchParams(window.location.search).get("employee_id") || "100001";
  }

  const workflowPanels = Array.from(document.querySelectorAll("[data-inbox-workflow-lazy]"));
  const workflowCache = new Map();
  const workflowPanelsByRef = new Map();
  const workflowQueue = new Map();
  const workflowInFlightRefs = new Set();
  const visibleWorkflowPanels = new Set();
  let workflowBatchBusy = false;
  let workflowBatchTimer = 0;
  let workflowAbortController = null;
  let workflowPrefetchObserver = null;
  let workflowVisibleObserver = null;

  function taskRefForPanel(panel) {
    return String(panel?.dataset.taskRef || "").trim();
  }

  function workflowButton(panel) {
    return panel?.querySelector("[data-inbox-workflow-load]");
  }

  function setWorkflowExpanded(panel, expanded, {userInitiated = false} = {}) {
    const result = panel?.querySelector("[data-inbox-workflow-result]");
    const button = workflowButton(panel);
    if (!result || !button || button.dataset.loaded !== "true") return;
    result.hidden = !expanded;
    button.textContent = expanded ? "흐름 접기" : "흐름 보기";
    button.setAttribute("aria-expanded", expanded ? "true" : "false");
    if (userInitiated) {
      if (expanded) delete panel.dataset.userCollapsed;
      else panel.dataset.userCollapsed = "true";
    }
  }

  function setWorkflowLoading(panel, active) {
    const target = panel?.querySelector("[data-inbox-workflow-result]");
    const status = panel?.querySelector("[data-inbox-workflow-status]");
    const button = workflowButton(panel);
    panel?.classList.toggle("is-loading", active);
    if (button) button.disabled = active;
    if (!active) {
      if (button) button.disabled = false;
      if (target && button?.dataset.loaded !== "true" && target.querySelector(".inbox-workflow-skeleton")) {
        target.hidden = true;
        target.innerHTML = "";
      }
      return;
    }
    if (status) status.textContent = "업무 흐름을 불러오는 중입니다.";
    if (target && button?.dataset.loaded !== "true") {
      target.hidden = false;
      target.innerHTML = `<div class="inbox-workflow-skeleton" aria-hidden="true"><span></span><span></span><span></span></div>`;
    }
  }

  function renderWorkflow(panel, canvas) {
    const target = panel.querySelector("[data-inbox-workflow-result]");
    if (!target || !canvas?.source) throw new Error("표시할 업무 흐름이 없습니다.");
    target.innerHTML = `
      <div class="mermaid-diagram task-console-workflow-canvas inbox-workflow-canvas" data-mermaid-state="pending" data-mermaid-source="${escapeHtml(canvas.source)}">
        <div class="boi-agent-artifact-title">
          <strong>${escapeHtml(canvas.title || "관련 업무 흐름")}</strong>
          ${canvas.current_stage_label ? `<span>${escapeHtml(canvas.current_stage_label)}</span>` : ""}
        </div>
        <div class="mermaid">${escapeHtml(canvas.source)}</div>
        <p class="mermaid-status" aria-live="polite">업무 흐름 그림을 준비하고 있습니다.</p>
      </div>`;
    target.hidden = false;
    panel.classList.remove("is-loading", "has-error");
    panel.classList.add("is-loaded");
    const button = workflowButton(panel);
    if (button) {
      button.dataset.loaded = "true";
      button.disabled = false;
      button.textContent = "흐름 접기";
      button.setAttribute("aria-expanded", "true");
    }
    const status = panel.querySelector("[data-inbox-workflow-status]");
    if (status) status.textContent = "";
    document.dispatchEvent(new CustomEvent("boi:markdown-rendered", {bubbles: true}));
  }

  function showWorkflowError(panel) {
    const status = panel?.querySelector("[data-inbox-workflow-status]");
    const target = panel?.querySelector("[data-inbox-workflow-result]");
    const button = workflowButton(panel);
    panel?.classList.remove("is-loading");
    panel?.classList.add("has-error");
    if (target && button?.dataset.loaded !== "true") {
      target.hidden = true;
      target.innerHTML = "";
    }
    if (button) {
      button.disabled = false;
      button.textContent = "다시 시도";
      button.setAttribute("aria-expanded", "false");
    }
    if (status) status.textContent = "업무 흐름을 불러오지 못했습니다.";
  }

  function panelsForRef(taskRef) {
    return workflowPanelsByRef.get(taskRef) || new Set();
  }

  function applyWorkflowEntry(entry) {
    const taskRef = String(entry?.task_ref || "");
    if (!taskRef) return;
    const panels = panelsForRef(taskRef);
    if (entry.state === "ready" && entry.canvas?.source) {
      workflowCache.set(taskRef, entry);
      panels.forEach((panel) => {
        panel.dataset.prefetched = "true";
        const shouldRender = (visibleWorkflowPanels.has(panel) || panel.dataset.manualOpen === "true")
          && panel.dataset.userCollapsed !== "true";
        if (shouldRender) renderWorkflow(panel, entry.canvas);
        else setWorkflowLoading(panel, false);
        delete panel.dataset.manualOpen;
      });
      return;
    }
    panels.forEach((panel) => {
      if (visibleWorkflowPanels.has(panel) || panel.dataset.manualOpen === "true") showWorkflowError(panel);
      else setWorkflowLoading(panel, false);
      delete panel.dataset.manualOpen;
    });
  }

  function scheduleWorkflowBatch(delay = 40) {
    window.clearTimeout(workflowBatchTimer);
    workflowBatchTimer = window.setTimeout(() => void flushWorkflowBatch(), delay);
  }

  async function flushWorkflowBatch() {
    if (workflowBatchBusy || !workflowQueue.size || document.hidden) return;
    const batch = [...workflowQueue.values()]
      .sort((left, right) => right.priority - left.priority)
      .slice(0, 4);
    batch.forEach((item) => {
      workflowQueue.delete(item.taskRef);
      workflowInFlightRefs.add(item.taskRef);
    });
    workflowBatchBusy = true;
    workflowAbortController = new AbortController();
    try {
      const response = await fetch(`/api/inbox/workflow-canvases?employee_id=${encodeURIComponent(employeeId())}`, {
        method: "POST",
        credentials: "same-origin",
        headers: {Accept: "application/json", "Content-Type": "application/json"},
        body: JSON.stringify({task_refs: batch.map((item) => item.taskRef)}),
        signal: workflowAbortController.signal,
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "업무 흐름을 불러오지 못했습니다.");
      const byRef = new Map((body.items || []).map((item) => [item.task_ref, item]));
      batch.forEach((item) => applyWorkflowEntry(byRef.get(item.taskRef) || {task_ref: item.taskRef, state: "unavailable"}));
    } catch (error) {
      if (error?.name !== "AbortError") {
        batch.forEach((item) => panelsForRef(item.taskRef).forEach((panel) => {
          if (visibleWorkflowPanels.has(panel) || panel.dataset.manualOpen === "true") showWorkflowError(panel);
          else setWorkflowLoading(panel, false);
          delete panel.dataset.manualOpen;
        }));
      }
    } finally {
      batch.forEach((item) => workflowInFlightRefs.delete(item.taskRef));
      workflowBatchBusy = false;
      workflowAbortController = null;
      if (workflowQueue.size) scheduleWorkflowBatch(20);
    }
  }

  function queueWorkflow(panel, {manual = false, render = false} = {}) {
    const taskRef = taskRefForPanel(panel);
    if (!taskRef || panel.dataset.userCollapsed === "true" && !manual) return;
    if (render || manual) visibleWorkflowPanels.add(panel);
    const cached = workflowCache.get(taskRef);
    if (cached) {
      if (render || manual) applyWorkflowEntry(cached);
      return;
    }
    if (render || manual) setWorkflowLoading(panel, true);
    if (workflowInFlightRefs.has(taskRef)) return;
    const queued = workflowQueue.get(taskRef) || {taskRef, priority: 0};
    queued.priority = Math.max(queued.priority, manual ? 3 : render ? 2 : 1);
    workflowQueue.set(taskRef, queued);
    scheduleWorkflowBatch(manual ? 0 : 40);
  }

  document.addEventListener("click", (event) => {
    const workflowButton = event.target.closest("[data-inbox-workflow-load]");
    if (!workflowButton) return;
    const panel = workflowButton.closest("[data-inbox-workflow-lazy]");
    const result = panel?.querySelector("[data-inbox-workflow-result]");
    if (workflowButton.dataset.loaded === "true" && result) {
      setWorkflowExpanded(panel, result.hidden, {userInitiated: true});
      return;
    }
    if (!panel) return;
    delete panel.dataset.userCollapsed;
    panel.dataset.manualOpen = "true";
    queueWorkflow(panel, {manual: true, render: true});
  });

  workflowPanels.forEach((panel) => {
    const taskRef = taskRefForPanel(panel);
    if (!taskRef) return;
    if (!workflowPanelsByRef.has(taskRef)) workflowPanelsByRef.set(taskRef, new Set());
    workflowPanelsByRef.get(taskRef).add(panel);
    const button = workflowButton(panel);
    if (panel.dataset.workflowPreloaded === "true" && button) {
      button.dataset.loaded = "true";
      panel.classList.add("is-loaded");
    }
  });

  const saveData = Boolean(navigator.connection?.saveData);
  if (workflowPanels.length > 1 && !saveData && "IntersectionObserver" in window) {
    workflowPrefetchObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting && entry.target.dataset.workflowPreloaded !== "true") {
          queueWorkflow(entry.target, {render: false});
        }
      });
    }, {rootMargin: "400px 0px", threshold: 0});
    workflowVisibleObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          visibleWorkflowPanels.add(entry.target);
          if (entry.target.dataset.workflowPreloaded !== "true" && entry.target.dataset.userCollapsed !== "true") {
            queueWorkflow(entry.target, {render: true});
          }
        } else {
          visibleWorkflowPanels.delete(entry.target);
        }
      });
    }, {threshold: 0.05});
    workflowPanels.slice(1).forEach((panel) => {
      workflowPrefetchObserver.observe(panel);
      workflowVisibleObserver.observe(panel);
    });
  }

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && workflowQueue.size) scheduleWorkflowBatch(0);
  });

  window.addEventListener("pagehide", () => {
    window.clearTimeout(workflowBatchTimer);
    workflowAbortController?.abort();
    workflowPrefetchObserver?.disconnect();
    workflowVisibleObserver?.disconnect();
  });

  const reportRows = Array.from(document.querySelectorAll("[data-inbox-report-row][data-report-id]"));
  let reportPollTimer = 0;
  let reportPollBusy = false;

  function pendingReportRows() {
    return reportRows.filter((row) => !row.querySelector("[data-inbox-report-link]"));
  }

  function scheduleReportPoll(delay = 5000) {
    window.clearTimeout(reportPollTimer);
    if (!pendingReportRows().length) return;
    reportPollTimer = window.setTimeout(() => void pollReportStatus(), delay);
  }

  async function pollReportStatus() {
    const pendingRows = pendingReportRows();
    if (!pendingRows.length || reportPollBusy || document.hidden) {
      if (pendingRows.length) scheduleReportPoll();
      return;
    }
    reportPollBusy = true;
    const ids = pendingRows.map((row) => row.dataset.reportId).filter(Boolean);
    try {
      const query = new URLSearchParams({employee_id: employeeId(), report_ids: ids.join(",")});
      const response = await fetch(`/api/inbox/reports/status?${query.toString()}`, {
        headers: {Accept: "application/json"},
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "보고서 상태를 확인하지 못했습니다.");
      const byId = new Map((body.items || []).map((item) => [item.report_id, item]));
      pendingRows.forEach((row) => {
        const item = byId.get(row.dataset.reportId);
        if (!item) return;
        const state = row.querySelector("[data-inbox-report-state]");
        if (item.report_state === "ready" && item.report_boi_url) {
          const link = document.createElement("a");
          link.className = "button primary";
          link.dataset.inboxReportLink = "";
          link.href = item.report_boi_url;
          link.textContent = "검증된 보고서 BoI";
          state?.replaceWith(link);
          return;
        }
        if (state) state.textContent = item.label || "보고서 준비 중";
      });
    } catch (_error) {
      // The coordinator retries independently. Keep the Inbox usable and poll later.
    } finally {
      reportPollBusy = false;
      scheduleReportPoll();
    }
  }

  if (reportRows.length) {
    scheduleReportPoll(1500);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) scheduleReportPoll(250);
    });
  }

  const forms = Array.from(document.querySelectorAll("[data-inbox-decision-form]"));
  if (!forms.length) return;

  function artifactsForForm(form) {
    const field = form.querySelector("[data-inbox-artifacts-field]");
    try {
      const parsed = JSON.parse(field?.value || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch (_error) {
      return [];
    }
  }

  function setArtifactsForForm(form, artifacts) {
    const field = form.querySelector("[data-inbox-artifacts-field]");
    if (field) field.value = JSON.stringify(artifacts);
  }

  function artifactLabel(artifact) {
    return artifact?.filename || artifact?.display_label || artifact?.artifact_id || "Data Lake artifact";
  }

  function safeArtifactSummary(artifact, attachment = null) {
    return {
      artifact_id: artifact?.artifact_id || "",
      filename: artifact?.filename || "",
      display_label: artifact?.display_label || artifact?.filename || artifact?.artifact_id || "",
      content_type: artifact?.content_type || "",
      size_bytes: artifact?.size_bytes || 0,
      sha256: artifact?.sha256 || "",
      download_url: artifact?.download_url || "",
      profile: artifact?.profile || null,
      attachment_role: attachment?.attachment_role || artifact?.attachment_role || "evidence",
      validation_state: attachment?.validation_state || artifact?.validation_state || "uploaded",
    };
  }

  function renderArtifacts(form, message = "") {
    const target = form.querySelector("[data-inbox-artifact-results]");
    if (!target) return;
    const artifacts = artifactsForForm(form);
    target.innerHTML = artifacts.length ? `
      <div class="artifact-chip-list">
        ${artifacts.map((artifact) => `
          <article class="artifact-chip evidence-artifact-card">
            <div>
              <strong>${escapeHtml(artifactLabel(artifact))}</strong>
              <span>${escapeHtml(artifact.attachment_role || "evidence")} · ${escapeHtml(artifact.content_type || "artifact")} · ${escapeHtml(String(artifact.size_bytes || 0))} bytes</span>
              <small>판단 기록에는 원본 대신 stable URL, checksum, profile만 남습니다.</small>
            </div>
            <div class="artifact-card-actions">
              <a href="${escapeHtml(artifact.download_url || "#")}" target="_blank" rel="noreferrer">원본 보기</a>
              <button type="button" data-inbox-artifact-remove="${escapeHtml(artifact.artifact_id || "")}">삭제</button>
            </div>
          </article>
        `).join("")}
      </div>
    ` : `<p class="muted">${escapeHtml(message || "아직 첨부한 판단 근거 파일이 없습니다.")}</p>`;
  }

  async function uploadInboxArtifacts(button) {
    const form = button.closest("[data-inbox-decision-form]");
    const panel = button.closest("[data-inbox-artifact-panel]");
    const fileInput = panel?.querySelector("[data-inbox-artifact-file]");
    const files = Array.from(fileInput?.files || []);
    if (!form || !panel || !files.length) {
      if (form) renderArtifacts(form, "업로드할 파일을 먼저 선택하세요.");
      return;
    }
    const previousText = button.textContent;
    button.disabled = true;
    button.textContent = "업로드 중...";
    const note = form.querySelector("textarea[name='note']")?.value || "";
    const role = panel.querySelector("[data-inbox-artifact-role]")?.value || "evidence";
    const taskRef = panel.dataset.taskRef || "";
    const reportId = panel.dataset.reportId || "";
    const artifacts = artifactsForForm(form);
    try {
      for (const file of files) {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("visibility", "private");
        formData.append("source_context", JSON.stringify({
          source: "boi_inbox",
          attached_from_surface: "boi_inbox_decision",
          target_type: "inbox_task",
          target_ref: taskRef,
          report_id: reportId,
          attachment_role: role,
          validation_state: "uploaded",
          human_note: note,
        }));
        const response = await fetch(`/api/data-lake/artifacts/upload?employee_id=${encodeURIComponent(employeeId())}`, {
          method: "POST",
          body: formData,
        });
        const body = await response.json().catch(() => ({detail: response.statusText}));
        if (!response.ok) {
          const detail = body.detail || body;
          throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
        }
        if (body.status === "disabled") {
          renderArtifacts(form, "Data Lake가 비활성화되어 파일을 저장하지 않았습니다. 판단 기록은 계속 남길 수 있습니다.");
          return;
        }
        const artifact = safeArtifactSummary(body.artifact || {}, body.attachment || null);
        if (artifact.artifact_id && !artifacts.some((item) => item.artifact_id === artifact.artifact_id)) {
          artifacts.push(artifact);
        }
      }
      setArtifactsForForm(form, artifacts);
      renderArtifacts(form);
    } catch (error) {
      renderArtifacts(form, `파일 첨부 실패: ${error.message || String(error)}`);
    } finally {
      button.disabled = false;
      button.textContent = previousText || "파일 첨부";
      if (fileInput) fileInput.value = "";
    }
  }

  async function removeInboxArtifact(button) {
    const form = button.closest("[data-inbox-decision-form]");
    const panel = button.closest("[data-inbox-artifact-panel]");
    const artifactId = button.dataset.inboxArtifactRemove || "";
    if (!form || !artifactId) return;
    const taskRef = panel?.dataset.taskRef || "";
    try {
      await fetch(`/api/data-lake/artifacts/${encodeURIComponent(artifactId)}/attach?employee_id=${encodeURIComponent(employeeId())}&target_type=inbox_task&target_ref=${encodeURIComponent(taskRef)}&user_confirmed=true`, {
        method: "DELETE",
      });
    } catch (_error) {
      // Local state removal is still useful if the detach endpoint is disabled.
    }
    const artifacts = artifactsForForm(form).filter((artifact) => artifact.artifact_id !== artifactId);
    setArtifactsForForm(form, artifacts);
    renderArtifacts(form);
  }

  document.addEventListener("click", (event) => {
    const uploadButton = event.target.closest("[data-inbox-artifact-upload]");
    if (uploadButton) {
      void uploadInboxArtifacts(uploadButton);
      return;
    }
    const removeButton = event.target.closest("[data-inbox-artifact-remove]");
    if (removeButton) {
      void removeInboxArtifact(removeButton);
    }
  });

  forms.forEach((form) => renderArtifacts(form));
})();
