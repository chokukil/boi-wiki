(() => {
  const panels = Array.from(document.querySelectorAll("[data-evidence-tray]"));
  if (!panels.length) return;

  const panelItems = new WeakMap();

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

  function employeeId(panel) {
    return panel.dataset.employeeId || new URLSearchParams(window.location.search).get("employee_id") || "100001";
  }

  function targetType(panel) {
    return panel.dataset.targetType || "";
  }

  function targetId(panel) {
    return panel.dataset.targetId || "";
  }

  function targetRef(panel) {
    return panel.dataset.targetRef || "";
  }

  function displayTarget(panel) {
    return targetId(panel) || targetRef(panel) || "";
  }

  function resultsNode(panel) {
    return panel.querySelector("[data-evidence-results]");
  }

  function roleValue(panel) {
    return panel.querySelector("[data-evidence-role]")?.value || panel.dataset.attachmentRole || "evidence";
  }

  function noteValue(panel) {
    const explicit = panel.querySelector("[data-evidence-note]")?.value;
    if (explicit) return explicit;
    return panel.closest("form")?.querySelector("textarea[name='note']")?.value || "";
  }

  function fileInput(panel) {
    return panel.querySelector("[data-evidence-file]");
  }

  function humanSize(bytes) {
    const value = Number(bytes || 0);
    if (!Number.isFinite(value) || value <= 0) return "0 B";
    if (value < 1024) return `${value} B`;
    if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }

  function artifactLabel(artifact) {
    return artifact?.filename || artifact?.display_label || artifact?.artifact_id || "Data Lake artifact";
  }

  function artifactNote(artifact) {
    return artifact?.human_note
      || artifact?.source_context?.human_note
      || artifact?.attachments?.[0]?.human_note
      || "원본은 BoI 본문 대신 Data Lake URL과 profile로 연결됩니다.";
  }

  function artifactSummary(artifact) {
    const attachment = Array.isArray(artifact?.attachments) ? artifact.attachments[0] : null;
    return {
      artifact_id: artifact?.artifact_id || "",
      filename: artifact?.filename || "",
      display_label: artifact?.display_label || artifact?.filename || artifact?.artifact_id || "",
      content_type: artifact?.content_type || "",
      size_bytes: artifact?.size_bytes || 0,
      sha256: artifact?.sha256 || "",
      download_url: artifact?.download_url || "",
      profile: artifact?.profile || null,
      attachment_role: attachment?.attachment_role || artifact?.attachment_role || roleValueFromArtifact(artifact),
      validation_state: attachment?.validation_state || artifact?.validation_state || "uploaded",
    };
  }

  function roleValueFromArtifact(artifact) {
    return artifact?.source_context?.attachment_role || "evidence";
  }

  function currentItems(panel) {
    return panelItems.get(panel) || [];
  }

  function hiddenArtifactFields(panel) {
    const form = panel.closest("form");
    const fields = [
      ...panel.querySelectorAll("[data-evidence-artifacts-field], [data-inbox-artifacts-field]"),
      ...(form ? Array.from(form.querySelectorAll("[data-evidence-artifacts-field], [data-inbox-artifacts-field]")) : []),
    ];
    return Array.from(new Set(fields));
  }

  function syncArtifactFields(panel, items) {
    const summaries = (items || [])
      .map((artifact) => artifactSummary(artifact))
      .filter((artifact) => artifact.artifact_id);
    for (const field of hiddenArtifactFields(panel)) {
      field.value = JSON.stringify(summaries);
    }
  }

  function setControlsDisabled(panel, disabled) {
    panel.dataset.evidenceDisabled = disabled ? "true" : "false";
    for (const control of panel.querySelectorAll("[data-evidence-file], [data-evidence-role], [data-evidence-upload]")) {
      control.disabled = Boolean(disabled);
    }
  }

  function render(panel, items, message = "") {
    const target = resultsNode(panel);
    const safeItems = Array.isArray(items) ? items : [];
    panelItems.set(panel, safeItems);
    syncArtifactFields(panel, safeItems);
    if (!target) return;
    if (!safeItems.length) {
      target.innerHTML = `<p class="muted">${escapeHtml(message || "아직 연결된 파일이 없습니다.")}</p>`;
      return;
    }
    target.innerHTML = `
      <div class="artifact-chip-list">
        ${safeItems.map((artifact) => `
          <article class="artifact-chip evidence-artifact-card">
            <div>
              <strong>${escapeHtml(artifactLabel(artifact))}</strong>
              <span>${escapeHtml(artifact.attachment_role || roleValueFromArtifact(artifact))} · ${escapeHtml(artifact.content_type || "artifact")} · ${escapeHtml(humanSize(artifact.size_bytes))}</span>
              <small>${escapeHtml(artifactNote(artifact))}</small>
              <details>
                <summary>기술 세부정보</summary>
                <code>${escapeHtml(artifact.artifact_id || "")}</code>
                <span>${escapeHtml(artifact.sha256 || "")}</span>
                <span>${escapeHtml(targetType(panel))}:${escapeHtml(displayTarget(panel))}</span>
              </details>
            </div>
            <div class="artifact-card-actions">
              <a href="${escapeHtml(artifact.download_url || "#")}" target="_blank" rel="noreferrer">원본 보기</a>
              <button type="button" data-evidence-remove="${escapeHtml(artifact.artifact_id || "")}">삭제</button>
            </div>
          </article>
        `).join("")}
      </div>
    `;
  }

  async function loadStatus(panel) {
    try {
      const response = await fetch(`/api/data-lake/status?employee_id=${encodeURIComponent(employeeId(panel))}`);
      const body = await response.json().catch(() => ({detail: response.statusText}));
      if (!response.ok) return true;
      if (body.enabled === false || body.status === "disabled") {
        setControlsDisabled(panel, true);
        render(panel, [], "파일 첨부는 Data Lake 활성화 후 사용할 수 있습니다. 판단 기록과 조치 내용은 계속 저장할 수 있습니다.");
        return false;
      }
      setControlsDisabled(panel, false);
      return true;
    } catch (_error) {
      return true;
    }
  }

  async function refresh(panel) {
    const target = resultsNode(panel);
    if (!target) return;
    if (!targetType(panel) || (!targetId(panel) && !targetRef(panel))) {
      render(panel, [], "단계를 선택하면 해당 위치에 연결된 파일을 볼 수 있습니다.");
      return;
    }
    const params = new URLSearchParams({
      employee_id: employeeId(panel),
      target_type: targetType(panel),
    });
    if (targetId(panel)) params.set("target_id", targetId(panel));
    if (targetRef(panel)) params.set("target_ref", targetRef(panel));
    try {
      const response = await fetch(`/api/data-lake/artifacts?${params.toString()}`);
      const body = await response.json().catch(() => ({detail: response.statusText}));
      if (!response.ok) {
        const detail = body.detail || body;
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      }
      if (body.status === "disabled") {
        setControlsDisabled(panel, true);
        render(panel, [], "파일 첨부는 Data Lake 활성화 후 사용할 수 있습니다. 판단 기록과 조치 내용은 계속 저장할 수 있습니다.");
        return;
      }
      setControlsDisabled(panel, false);
      render(panel, body.items || []);
    } catch (error) {
      render(panel, currentItems(panel), `파일 목록을 불러오지 못했습니다: ${error.message || String(error)}`);
    }
  }

  async function upload(panel, files) {
    const uploadFiles = Array.from(files || fileInput(panel)?.files || []);
    const button = panel.querySelector("[data-evidence-upload]");
    const input = fileInput(panel);
    if (!uploadFiles.length) {
      render(panel, currentItems(panel), "업로드할 파일을 먼저 선택하세요.");
      return;
    }
    if (!targetType(panel) || (!targetId(panel) && !targetRef(panel))) {
      render(panel, currentItems(panel), "먼저 첨부할 업무 단계나 판단 대상을 선택하세요.");
      return;
    }
    const previousText = button?.textContent;
    if (button) {
      button.disabled = true;
      button.textContent = "업로드 중...";
    }
    try {
      for (const file of uploadFiles) {
        const sourceContext = {
          source: panel.dataset.attachedFromSurface || "evidence_tray",
          attached_from_surface: panel.dataset.attachedFromSurface || "evidence_tray",
          target_type: targetType(panel),
          attachment_role: roleValue(panel),
          validation_state: panel.dataset.validationState || "uploaded",
          human_note: noteValue(panel),
        };
        if (targetId(panel)) sourceContext.target_id = targetId(panel);
        if (targetRef(panel)) sourceContext.target_ref = targetRef(panel);
        if (panel.dataset.reportId) sourceContext.report_id = panel.dataset.reportId;
        const formData = new FormData();
        formData.append("file", file);
        formData.append("visibility", panel.dataset.visibility || "private");
        formData.append("source_context", JSON.stringify(sourceContext));
        const response = await fetch(`/api/data-lake/artifacts/upload?employee_id=${encodeURIComponent(employeeId(panel))}`, {
          method: "POST",
          body: formData,
        });
        const body = await response.json().catch(() => ({detail: response.statusText}));
        if (!response.ok) {
          const detail = body.detail || body;
          throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
        }
        if (body.status === "disabled") {
          setControlsDisabled(panel, true);
          render(panel, currentItems(panel), "파일 첨부는 Data Lake 활성화 후 사용할 수 있습니다. 판단 기록과 조치 내용은 계속 저장할 수 있습니다.");
          return;
        }
      }
      if (input) input.value = "";
      await refresh(panel);
    } catch (error) {
      render(panel, currentItems(panel), `파일 첨부 실패: ${error.message || String(error)}`);
    } finally {
      if (button) {
        button.disabled = panel.dataset.evidenceDisabled === "true";
        button.textContent = previousText || "Data Lake 저장";
      }
    }
  }

  async function remove(panel, artifactId) {
    if (!artifactId) return;
    const params = new URLSearchParams({
      employee_id: employeeId(panel),
      target_type: targetType(panel),
      user_confirmed: "true",
    });
    if (targetId(panel)) params.set("target_id", targetId(panel));
    if (targetRef(panel)) params.set("target_ref", targetRef(panel));
    try {
      await fetch(`/api/data-lake/artifacts/${encodeURIComponent(artifactId)}/attach?${params.toString()}`, {
        method: "DELETE",
      });
    } catch (_error) {
      // Keep the tray responsive even if an optional Data Lake backend is down.
    }
    const localItems = currentItems(panel).filter((artifact) => artifact.artifact_id !== artifactId);
    render(panel, localItems);
    await refresh(panel);
  }

  async function saveReportEvidence(panel) {
    const button = panel.querySelector("[data-evidence-save-report]");
    const status = panel.querySelector("[data-evidence-save-status]");
    const reportId = panel.dataset.reportId || targetId(panel);
    const refs = currentItems(panel).map((artifact) => artifactSummary(artifact)).filter((artifact) => artifact.artifact_id);
    if (!reportId) {
      if (status) status.textContent = "보고서 식별자가 없습니다.";
      return;
    }
    if (!refs.length) {
      if (status) status.textContent = "먼저 Data Lake에 파일을 저장하세요.";
      return;
    }
    const previousText = button?.textContent;
    if (button) {
      button.disabled = true;
      button.textContent = "저장 중...";
    }
    try {
      const response = await fetch(`/api/inbox/reports/${encodeURIComponent(reportId)}/attach-evidence?employee_id=${encodeURIComponent(employeeId(panel))}`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({evidence_refs: refs, note: noteValue(panel), user_confirmed: true}),
      });
      const body = await response.json().catch(() => ({detail: response.statusText}));
      if (!response.ok) {
        const detail = body.detail || body;
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      }
      if (status) status.textContent = "보고서 보강 파일로 저장되었습니다.";
    } catch (error) {
      if (status) status.textContent = `저장 실패: ${error.message || String(error)}`;
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = previousText || "보강 파일 저장";
      }
    }
  }

  function attachEvents(panel) {
    panel.addEventListener("click", (event) => {
      const uploadButton = event.target.closest("[data-evidence-upload]");
      if (uploadButton) {
        void upload(panel);
        return;
      }
      const saveReportButton = event.target.closest("[data-evidence-save-report]");
      if (saveReportButton) {
        void saveReportEvidence(panel);
        return;
      }
      const removeButton = event.target.closest("[data-evidence-remove]");
      if (removeButton) {
        void remove(panel, removeButton.dataset.evidenceRemove || "");
      }
    });
    panel.addEventListener("dragover", (event) => {
      if (fileInput(panel)?.disabled) return;
      event.preventDefault();
      panel.classList.add("drag-over");
    });
    panel.addEventListener("dragleave", () => panel.classList.remove("drag-over"));
    panel.addEventListener("drop", (event) => {
      if (fileInput(panel)?.disabled) return;
      event.preventDefault();
      panel.classList.remove("drag-over");
      void upload(panel, event.dataTransfer?.files || []);
    });
  }

  window.BoiEvidenceTray = {
    refresh,
    refreshAll: () => panels.forEach((panel) => void refresh(panel)),
    setTarget: (panel, nextTargetId) => {
      if (panel) {
        panel.dataset.targetId = nextTargetId || "";
        return refresh(panel);
      }
      return Promise.resolve();
    },
  };

  panels.forEach((panel) => {
    attachEvents(panel);
    void loadStatus(panel).then(() => refresh(panel));
  });
})();
