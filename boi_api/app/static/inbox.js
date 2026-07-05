(() => {
  const forms = Array.from(document.querySelectorAll("[data-inbox-decision-form]"));
  if (!forms.length) return;

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

  function employeeId() {
    return new URLSearchParams(window.location.search).get("employee_id") || "100001";
  }

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
