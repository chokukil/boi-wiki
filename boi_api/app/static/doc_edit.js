(function () {
  function panel() {
    return document.querySelector(".body-editor-panel");
  }

  function resultText(text, isError) {
    const result = document.querySelector(".body-draft-result");
    if (!result) return;
    result.textContent = text;
    result.classList.toggle("error", Boolean(isError));
  }

  document.addEventListener("click", async function (event) {
    const editButton = event.target.closest(".edit-body-button");
    if (editButton) {
      const editor = panel();
      if (editor) {
        editor.hidden = false;
        editor.querySelector(".body-draft-textarea")?.focus();
      }
      return;
    }

    const cancelButton = event.target.closest(".cancel-body-edit");
    if (cancelButton) {
      const editor = panel();
      if (editor) editor.hidden = true;
      resultText("not applied · not committed", false);
      return;
    }

    const saveButton = event.target.closest(".save-body-draft");
    if (!saveButton) return;
    const editor = panel();
    if (!editor) return;
    const textarea = editor.querySelector(".body-draft-textarea");
    saveButton.disabled = true;
    resultText("saving draft...", false);
    try {
      const response = await fetch(editor.dataset.saveUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          base_sha256: editor.dataset.baseSha,
          proposed_body: textarea ? textarea.value : "",
          author: editor.dataset.employeeId,
          note: "inline body editor"
        })
      });
      const payload = await response.json();
      if (!response.ok) {
        const detail = payload.detail || {};
        throw new Error(detail.message || detail || "HTTP " + response.status);
      }
      resultText(`${payload.status} · ${payload.draft_id} · draft only, not applied, not committed`, false);
    } catch (error) {
      resultText("draft failed: " + error.message, true);
    } finally {
      saveButton.disabled = false;
    }
  });
})();
