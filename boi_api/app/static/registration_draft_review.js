(() => {
  const root = document.querySelector("[data-action-draft-review]");
  if (!root) return;

  const status = root.querySelector("[data-draft-status]");
  const validationState = root.querySelector("[data-validation-state]");
  const validationDetail = root.querySelector("[data-validation-detail]");
  const output = root.querySelector("[data-draft-output]");
  const validateButton = root.querySelector("[data-validate-draft]");
  const publishButton = root.querySelector("[data-publish-draft]");

  async function post(url, body = {}) {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {"Content-Type": "application/json", "Accept": "application/json"},
      body: JSON.stringify(body),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail || payload);
      throw new Error(detail || `HTTP ${response.status}`);
    }
    return payload;
  }

  function renderDraft(draft) {
    const validation = draft?.validation || {};
    status.textContent = draft?.status || "draft";
    validationState.textContent = validation.valid ? "통과" : "수정 필요";
    validationDetail.textContent = validation.valid
      ? (validation.checks || []).join(", ")
      : [...(validation.errors || []), ...(validation.warnings || [])].join(" · ");
    publishButton.disabled = !validation.valid || draft?.status === "publish_requested";
    output.textContent = JSON.stringify({
      draft_id: draft?.draft_id,
      status: draft?.status,
      valid: Boolean(validation.valid),
      checks: validation.checks || [],
      catalog_applied: Boolean(draft?.catalog_applied),
    }, null, 2);
  }

  validateButton.addEventListener("click", async () => {
    validateButton.disabled = true;
    try {
      renderDraft((await post(root.dataset.validateUrl)).draft);
    } catch (error) {
      output.textContent = `검증 실패: ${error.message}`;
    } finally {
      validateButton.disabled = false;
    }
  });

  publishButton.addEventListener("click", async () => {
    publishButton.disabled = true;
    try {
      renderDraft((await post(root.dataset.publishUrl, {
        operation: "registration_draft_publish",
        user_confirmed: true,
        note: "Agent Playground exact Flow publish request",
      })).draft);
    } catch (error) {
      output.textContent = `게시 요청 실패: ${error.message}`;
      publishButton.disabled = false;
    }
  });
})();
