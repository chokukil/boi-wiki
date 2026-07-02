(function () {
  const modeButtons = Array.from(document.querySelectorAll("[data-ops-mode]"));
  const views = Array.from(document.querySelectorAll("[data-ops-view]"));
  const runDataEl = document.querySelector("[data-selected-run-json]");
  const detailPanel = document.querySelector("[data-ops-detail-panel]");
  let runs = [];
  try {
    runs = JSON.parse(runDataEl?.textContent || "[]");
  } catch (_error) {
    runs = [];
  }
  const runById = new Map(runs.map((run) => [String(run.run_id || ""), run]));

  function setMode(mode) {
    modeButtons.forEach((button) => button.classList.toggle("active", button.dataset.opsMode === mode));
    views.forEach((view) => view.classList.toggle("hidden", view.dataset.opsView !== mode));
  }

  modeButtons.forEach((button) => {
    button.addEventListener("click", () => setMode(button.dataset.opsMode || "map"));
  });

  function setText(selector, value) {
    const element = detailPanel?.querySelector(selector);
    if (element) element.textContent = value || "";
  }

  function selectRun(runId) {
    const run = runById.get(String(runId || ""));
    if (!run || !detailPanel) return;
    setText("[data-detail-title]", run.sop_title || "");
    setText("[data-detail-summary]", run.summary || run.latest_summary || "");
    setText("[data-detail-stage]", run.current_stage_label || "");
    setText("[data-detail-why]", `${run.current_stage_label || "현재"} 단계에서 확인이 필요합니다.`);
    setText("[data-detail-context]", run.business_brief || "업무 맥락 확인 필요");
    const focus = Array.isArray(run.focus_points) && run.focus_points.length ? run.focus_points.join(" · ") : "일반 진행 상태";
    setText("[data-detail-focus]", focus);
    setText("[data-detail-next]", focus.includes("근거 부족") ? "부족 근거를 먼저 확인한 뒤 승인 또는 반려를 결정하세요." : "검증 보고서 또는 SOP Lens에서 근거를 확인하세요.");
    const lens = detailPanel.querySelector("[data-detail-lens]");
    if (lens && run.url) lens.setAttribute("href", run.url);
    const report = detailPanel.querySelector("[data-detail-report]");
    if (report) report.setAttribute("href", run.report_url || `/inbox?employee_id=${encodeURIComponent(document.querySelector(".ops-map")?.dataset.employeeId || "")}`);
    document.querySelectorAll("[data-run-preview], [data-run-row], [data-sop-node]").forEach((item) => {
      const itemRunId = item.dataset.runId || item.dataset.defaultRunId || "";
      item.classList.toggle("selected", itemRunId === String(runId || ""));
    });
  }

  document.querySelectorAll("[data-run-preview]").forEach((item) => {
    item.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      selectRun(item.dataset.runId || "");
    });
  });

  document.querySelectorAll("[data-sop-node]").forEach((item) => {
    item.addEventListener("click", () => selectRun(item.dataset.defaultRunId || ""));
  });

  document.querySelectorAll("[data-decision-action]").forEach((button) => {
    button.addEventListener("click", () => {
      setText("[data-detail-next]", "BoI Inbox 승인/조치에서 사유를 남기고 처리합니다.");
    });
  });
})();
