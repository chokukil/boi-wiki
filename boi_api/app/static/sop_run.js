(function () {
  const stageNodes = Array.from(document.querySelectorAll("[data-stage-node]"));
  const panelTitle = document.querySelector("[data-stage-panel-title]");
  const panelSummary = document.querySelector("[data-stage-panel-summary]");
  const panelStatus = document.querySelector("[data-stage-panel-status]");
  const panelNext = document.querySelector("[data-stage-panel-next]");
  if (!stageNodes.length || !panelTitle || !panelSummary || !panelStatus || !panelNext) return;

  function selectStage(node) {
    stageNodes.forEach((item) => {
      const isActive = item === node;
      item.classList.toggle("active", isActive);
      item.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
    panelTitle.textContent = node.dataset.stageTitle || "SOP 단계";
    panelSummary.textContent = node.dataset.stageSummary || "이 단계의 업무 맥락을 확인합니다.";
    panelStatus.textContent = node.dataset.stageStatus || "상태 확인";
    panelNext.textContent = node.dataset.stageNext || "검증 보고서와 원본 기록을 확인하세요.";
  }

  stageNodes.forEach((node) => {
    node.addEventListener("click", () => selectStage(node));
  });
})();
