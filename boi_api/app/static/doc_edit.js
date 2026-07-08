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

  function relatedStatus(editor, text, isError) {
    const status = editor.querySelector(".related-update-status");
    if (!status) return;
    status.textContent = text;
    status.classList.toggle("error", Boolean(isError));
  }

  function bodyPayload(editor) {
    const textarea = editor.querySelector(".body-draft-textarea");
    return {
      base_sha256: editor.dataset.baseSha,
      proposed_body: textarea ? textarea.value : "",
      author: editor.dataset.employeeId,
      note: "inline body editor"
    };
  }

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload)
    });
    const body = await response.json();
    if (!response.ok) {
      const detail = body.detail || body;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return body;
  }

  function renderReasonTags(container, reasons) {
    for (const reason of reasons || []) {
      const tag = document.createElement("span");
      tag.className = "related-update-reason";
      tag.textContent = reason.kind || reason.label || "related";
      if (reason.detail) tag.title = reason.detail;
      container.appendChild(tag);
    }
  }

  function renderImpact(editor, payload) {
    const list = editor.querySelector(".related-update-list");
    const summary = editor.querySelector(".related-update-summary");
    const createButton = editor.querySelector(".create-related-update-job");
    const applyButton = editor.querySelector(".apply-related-update-job");
    if (!list || !summary) return;
    list.replaceChildren();
    editor._relatedImpact = payload;
    editor._relatedJob = null;
    const items = payload.items || [];
    summary.textContent = items.length
      ? `영향 문서 ${payload.total || items.length}개 · 초안 생성 전 검토`
      : "영향 문서가 없습니다.";
    for (const item of items) {
      const target = item.target || {};
      const card = document.createElement("article");
      card.className = "related-update-card";
      const title = document.createElement("strong");
      title.textContent = target.title || target.boi_id || "관련 문서";
      const meta = document.createElement("small");
      meta.textContent = `${target.type || "boi"} · ${item.patch_mode || "review_note"}`;
      const reasons = document.createElement("div");
      reasons.className = "related-update-reasons";
      renderReasonTags(reasons, item.reasons || []);
      card.append(title, meta, reasons);
      list.appendChild(card);
    }
    if (createButton) createButton.disabled = !items.length;
    if (applyButton) applyButton.disabled = true;
  }

  function renderJob(editor, job) {
    const list = editor.querySelector(".related-update-list");
    const summary = editor.querySelector(".related-update-summary");
    const applyButton = editor.querySelector(".apply-related-update-job");
    if (!list || !summary) return;
    list.replaceChildren();
    editor._relatedJob = job;
    const patches = job.patches || [];
    const ready = patches.filter((patch) => patch.status === "draft_ready");
    summary.textContent = `업데이트 큐 ${patches.length}건 · 적용 가능 ${ready.length}건`;
    for (const patch of patches) {
      const card = document.createElement("article");
      card.className = "related-update-card patch-card";
      const label = document.createElement("label");
      label.className = "related-update-patch-label";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = patch.patch_id || "";
      checkbox.dataset.patchId = patch.patch_id || "";
      checkbox.disabled = patch.status !== "draft_ready";
      checkbox.checked = patch.status === "draft_ready";
      const title = document.createElement("strong");
      title.textContent = (patch.target && patch.target.title) || patch.target_boi_id || patch.patch_id || "patch";
      label.append(checkbox, title);
      const meta = document.createElement("small");
      meta.textContent = `${patch.status || "draft"} · ${patch.patch_mode || "review_note"} · ${patch.reason || "related"}`;
      card.append(label, meta);
      if (patch.diff) {
        const details = document.createElement("details");
        const summaryNode = document.createElement("summary");
        summaryNode.textContent = "Diff";
        const pre = document.createElement("pre");
        pre.className = "related-update-diff";
        pre.textContent = patch.diff;
        details.append(summaryNode, pre);
        card.appendChild(details);
      }
      list.appendChild(card);
    }
    if (applyButton) applyButton.disabled = !ready.length;
  }

  async function analyzeRelated(editor) {
    if (!editor.dataset.impactUrl) return null;
    if (!editor.dataset.loaded) await loadEditor(editor);
    relatedStatus(editor, "analyzing...", false);
    const payload = await postJson(editor.dataset.impactUrl, {
      ...bodyPayload(editor),
      max_items: 20
    });
    renderImpact(editor, payload);
    relatedStatus(editor, payload.impacted_count ? "impact ready" : "no impact", false);
    return payload;
  }

  async function createRelatedJob(editor) {
    if (!editor.dataset.relatedUpdateJobsUrl) return null;
    if (!editor._relatedImpact) await analyzeRelated(editor);
    relatedStatus(editor, "drafting...", false);
    const payload = await postJson(editor.dataset.relatedUpdateJobsUrl, {
      ...bodyPayload(editor),
      max_items: 20,
      user_confirmed: true
    });
    renderJob(editor, payload);
    relatedStatus(editor, payload.status || "drafted", false);
    return payload;
  }

  async function applyRelatedJob(editor) {
    const job = editor._relatedJob;
    if (!job || !job.apply_url) return null;
    const selected = Array.from(editor.querySelectorAll(".related-update-list input[data-patch-id]:checked"))
      .map((input) => input.dataset.patchId)
      .filter(Boolean);
    if (!selected.length) {
      relatedStatus(editor, "select a patch", true);
      return null;
    }
    relatedStatus(editor, "applying...", false);
    const payload = await postJson(job.apply_url, {
      patch_ids: selected,
      user_confirmed: true,
      author: editor.dataset.employeeId,
      note: "related update queue"
    });
    renderJob(editor, payload);
    relatedStatus(editor, payload.ok ? "applied" : "apply failed", !payload.ok);
    return payload;
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
    editor.dataset.impactUrl = payload.impact_url || editor.dataset.impactUrl || "";
    editor.dataset.relatedUpdateJobsUrl = payload.related_update_jobs_url || editor.dataset.relatedUpdateJobsUrl || "";
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
      body: JSON.stringify(bodyPayload(editor))
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
        await analyzeRelated(editor);
        resultText(payload.ok ? "preview valid" : "preview has validation errors", !payload.ok);
      } catch (error) {
        resultText("preview failed: " + error.message, true);
        relatedStatus(editor, "impact failed", true);
      } finally {
        previewButton.disabled = false;
      }
      return;
    }

    const relatedPreviewButton = event.target.closest(".preview-related-update");
    if (relatedPreviewButton) {
      relatedPreviewButton.disabled = true;
      try {
        await analyzeRelated(editor);
      } catch (error) {
        relatedStatus(editor, "impact failed: " + error.message, true);
      } finally {
        relatedPreviewButton.disabled = false;
      }
      return;
    }

    const relatedJobButton = event.target.closest(".create-related-update-job");
    if (relatedJobButton) {
      relatedJobButton.disabled = true;
      try {
        await createRelatedJob(editor);
      } catch (error) {
        relatedStatus(editor, "draft failed: " + error.message, true);
      } finally {
        relatedJobButton.disabled = !((editor._relatedImpact || {}).items || []).length;
      }
      return;
    }

    const relatedApplyButton = event.target.closest(".apply-related-update-job");
    if (relatedApplyButton) {
      relatedApplyButton.disabled = true;
      try {
        await applyRelatedJob(editor);
      } catch (error) {
        relatedStatus(editor, "apply failed: " + error.message, true);
      } finally {
        const patches = ((editor._relatedJob || {}).patches || []).filter((patch) => patch.status === "draft_ready");
        relatedApplyButton.disabled = !patches.length;
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
        await analyzeRelated(editor);
        resultText(`${payload.status} · ${payload.commit_status} · ${payload.commit_hash || "no commit hash"}`, false);
      } catch (error) {
        resultText("apply failed: " + error.message, true);
        relatedStatus(editor, "impact failed", true);
      } finally {
        applyButton.disabled = false;
      }
    }
  });
})();
