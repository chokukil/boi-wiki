(function () {
  function panel() {
    return document.querySelector(".body-editor-panel");
  }

  function resultText(text, isError) {
    const result = document.querySelector(".body-edit-result");
    if (!result) return;
    result.textContent = text;
    result.classList.toggle("error", Boolean(isError));
  }

  function fillList(selector, items) {
    const list = document.querySelector(selector);
    if (!list) return;
    list.replaceChildren();
    for (const item of items || []) {
      const li = document.createElement("li");
      li.textContent = item;
      list.appendChild(li);
    }
  }

  function renderSuggestions(items) {
    const container = document.querySelector(".body-fix-suggestions");
    if (!container) return;
    container.replaceChildren();
    for (const item of items || []) {
      const box = document.createElement("div");
      box.className = "fix-suggestion";
      const title = document.createElement("strong");
      title.textContent = item.title || "Fix suggestion";
      const description = document.createElement("p");
      description.textContent = item.description || "";
      box.append(title, description);
      container.appendChild(box);
    }
  }

  function renderValidation(payload) {
    const report = payload.validation_report || payload.validation || {};
    const panel = document.querySelector(".body-validation-panel");
    const summary = document.querySelector(".body-validation-summary");
    const preview = document.querySelector(".body-edit-preview");
    if (panel) panel.hidden = false;
    if (summary) summary.textContent = `${payload.status || "validated"} · ${report.ok ? "통과" : "수정 필요"}`;
    fillList(".body-validation-errors", report.errors || []);
    fillList(".body-validation-warnings", report.warnings || []);
    renderSuggestions(payload.fix_suggestions || []);
    const html = payload.body_preview_html || (payload.preview && payload.preview.html);
    if (preview && html) {
      preview.innerHTML = html;
      preview.dispatchEvent(new CustomEvent("boi:markdown-rendered", { bubbles: true }));
    }
  }

  async function loadEditor(editor) {
    if (!editor || editor.dataset.loaded === "true") return;
    const loading = editor.querySelector(".body-editor-loading");
    resultText("body source loading...", false);
    if (loading) loading.textContent = "Body source loading...";
    const response = await fetch(editor.dataset.editorUrl, { headers: { Accept: "application/json" } });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "HTTP " + response.status);
    }
    editor.dataset.previewUrl = payload.preview_url || "";
    editor.dataset.applyUrl = payload.apply_url || "";
    editor.dataset.baseSha = payload.base_sha256 || "";
    const textarea = editor.querySelector(".body-draft-textarea");
    if (textarea) textarea.value = payload.body || "";
    if (loading) loading.textContent = "Body source loaded.";
    editor.dataset.loaded = "true";
    resultText("ready", false);
  }

  async function postBodyEdit(editor, url, phase) {
    if (!editor.dataset.loaded) {
      await loadEditor(editor);
    }
    const textarea = editor.querySelector(".body-draft-textarea");
    resultText(phase, false);
    const response = await fetch(url, {
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
      if (detail.validation_report) renderValidation(detail);
      throw new Error(detail.message || detail.status || detail || "HTTP " + response.status);
    }
    renderValidation(payload);
    return payload;
  }

  document.addEventListener("click", async function (event) {
    const editButton = event.target.closest(".edit-body-button");
    if (editButton) {
      const editor = panel();
      if (editor) {
        editor.hidden = false;
        try {
          await loadEditor(editor);
          editor.querySelector(".body-draft-textarea")?.focus();
        } catch (error) {
          resultText("editor load failed: " + error.message, true);
        }
      }
      return;
    }

    const cancelButton = event.target.closest(".cancel-body-edit");
    if (cancelButton) {
      const editor = panel();
      if (editor) editor.hidden = true;
      resultText("ready", false);
      return;
    }

    const editor = panel();
    if (!editor) return;

    const previewButton = event.target.closest(".preview-body-edit");
    if (previewButton) {
      previewButton.disabled = true;
      try {
        const payload = await postBodyEdit(editor, editor.dataset.previewUrl, "검증 중...");
        resultText(payload.ok ? "preview valid" : "preview has validation errors", !payload.ok);
      } catch (error) {
        resultText("preview failed: " + error.message, true);
      } finally {
        previewButton.disabled = false;
      }
      return;
    }

    const applyButton = event.target.closest(".apply-body-edit");
    if (applyButton) {
      applyButton.disabled = true;
      try {
        await postBodyEdit(editor, editor.dataset.previewUrl, "검증 중...");
        const payload = await postBodyEdit(editor, editor.dataset.applyUrl, "적용 및 커밋 중...");
        if (payload.sha256) editor.dataset.baseSha = payload.sha256;
        resultText(`${payload.status} · ${payload.commit_status} · ${payload.commit_hash || "no commit hash"}`, false);
      } catch (error) {
        resultText("apply failed: " + error.message, true);
      } finally {
        applyButton.disabled = false;
      }
    }
  });
})();
