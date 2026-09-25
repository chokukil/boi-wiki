(function () {
  const root = document.querySelector("[data-harness-review]");
  if (!root) return;
  const candidateId = root.dataset.candidateId || "";
  const versionId = root.dataset.versionId || "";
  const employeeId = new URL(window.location.href).searchParams.get("employee_id") || "100001";
  const message = root.querySelector("[data-harness-message]");
  const note = () => root.querySelector("[data-harness-note]")?.value.trim() || "";
  const recordResult = (operation, result) => {
    root.dataset.harnessOperation = operation;
    root.dataset.harnessStatus = String(result.status || result.candidate_status || "");
    root.dataset.harnessProductionChanged = String(Boolean(result.production_changed));
    root.dataset.harnessRevision = String(result.revision || result.candidate_revision || "");
  };
  const send = async (path, payload) => {
    if (message) message.textContent = "검토 내용을 반영하고 있습니다.";
    const response = await fetch(`${path}?employee_id=${encodeURIComponent(employeeId)}`, {
      method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(payload),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "요청을 처리하지 못했습니다.");
    if (message) message.textContent = payload.rehearsal ? "운영 변경 없이 연습을 마쳤습니다." : "검토 결과를 기록했습니다.";
    return result;
  };
  root.querySelectorAll("[data-harness-review-action]").forEach((button) => button.addEventListener("click", async () => {
    try {
      if (!note()) throw new Error("검토 메모를 입력해주세요.");
      const result = await send(`/api/v2/harness-candidates/${encodeURIComponent(candidateId)}/review`, { decision: button.dataset.harnessReviewAction, expected_eval_id: root.dataset.evalId, note: note() });
      recordResult("review", result);
      window.location.reload();
    } catch (error) { if (message) message.textContent = error.message; }
  }));
  root.querySelectorAll("[data-harness-release]").forEach((button) => button.addEventListener("click", async () => {
    try {
      if (!root.querySelector("[data-harness-confirm]")?.checked) throw new Error("운영 반영 확인이 필요합니다.");
      const rehearsal = button.dataset.rehearsal === "true";
      const result = await send(`/api/v2/harness-candidates/${encodeURIComponent(candidateId)}/release`, { expected_version_id: versionId, note: note() || "검토 화면에서 승인", user_confirmed: true, rehearsal });
      recordResult(rehearsal ? "rehearsal" : "release", result);
      if (button.dataset.rehearsal !== "true") window.location.reload();
    } catch (error) { if (message) message.textContent = error.message; }
  }));
  root.querySelector("[data-harness-rollback]")?.addEventListener("click", async () => {
    try {
      if (!root.querySelector("[data-harness-confirm]")?.checked) throw new Error("되돌리기 확인이 필요합니다.");
      const result = await send(`/api/v2/harness-candidates/${encodeURIComponent(candidateId)}/rollback`, { note: note() || "검토 화면에서 rollback", user_confirmed: true, rehearsal: false });
      recordResult("rollback", result);
      window.location.reload();
    } catch (error) { if (message) message.textContent = error.message; }
  });
})();
