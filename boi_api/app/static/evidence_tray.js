(() => {
  const panels = Array.from(document.querySelectorAll("[data-evidence-tray]"));
  if (!panels.length) return;

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

  function resultsNode(panel) {
    return panel.querySelector("[data-evidence-results]");
  }

  function roleValue(panel) {
    return panel.querySelector("[data-evidence-role]")?.value || panel.dataset.attachmentRole || "evidence";
  }

  function noteValue(panel) {
    return panel.querySelector("[data-evidence-note]")?.value || "";
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

  function render(panel, items, message = "") {
    const target = resultsNode(panel);
    if (!target) return;
    if (!Array.isArray(items) || !items.length) {
      target.innerHTML = `<p class="muted">${escapeHtml(message || "아직 연결된 파일이 없습니다.")}</p>`;
      return;
    }
    target.innerHTML = `
      <div class="artifact-chip-list">
        ${items.map((artifact) => `
          <article class="artifact-chip evidence-artifact-card">
            <div>
              <strong>${escapeHtml(artifactLabel(artifact))}</strong>
              <span>${escapeHtml(artifact.attachment_role || "evidence")} · ${escapeHtml(artifact.content_type || "artifact")} · ${escapeHtml(humanSize(artifact.size_bytes))}</span>
              <small>${escapeHtml(artifactNote(artifact))}</small>
              <details>
                <summary>기술 세부정보</summary>
                <code>${escapeHtml(artifact.artifact_id || "")}</code>
                <span>${escapeHtml(artifact.sha256 || "")}</span>
                <span>${escapeHtml(targetType(panel))}:${escapeHtml(targetId(panel))}</span>
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

  async function refresh(panel) {
    const target = resultsNode(panel);
    if (!target) return;
    if (!targetType(panel) || !targetId(panel)) {
      render(panel, [], "단계를 선택하면 해당 위치에 연결된 파일을 볼 수 있습니다.");
      return;
    }
    const params = new URLSearchParams({
      employee_id: employeeId(panel),
      target_type: targetType(panel),
      target_id: targetId(panel),
    });
    try {
      const response = await fetch(`/api/data-lake/artifacts?${params.toString()}`);
      const body = await response.json().catch(() => ({detail: response.statusText}));
      if (!response.ok) {
        const detail = body.detail || body;
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      }
      if (body.status === "disabled") {
        render(panel, [], "파일 첨부는 Data Lake 활성화 후 사용할 수 있습니다. 판단 기록은 계속 남길 수 있습니다.");
        return;
      }
      render(panel, body.items || []);
    } catch (error) {
      render(panel, [], `파일 목록을 불러오지 못했습니다: ${error.message || String(error)}`);
    }
  }

  async function upload(panel, files) {
    const uploadFiles = Array.from(files || fileInput(panel)?.files || []);
    const button = panel.querySelector("[data-evidence-upload]");
    const input = fileInput(panel);
    if (!uploadFiles.length) {
      render(panel, [], "업로드할 파일을 먼저 선택하세요.");
      return;
    }
    if (!targetType(panel) || !targetId(panel)) {
      render(panel, [], "먼저 첨부할 업무 단계나 판단 대상을 선택하세요.");
      return;
    }
    const previousText = button?.textContent;
    if (button) {
      button.disabled = true;
      button.textContent = "업로드 중...";
    }
    try {
      for (const file of uploadFiles) {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("visibility", panel.dataset.visibility || "private");
        formData.append("source_context", JSON.stringify({
          source: panel.dataset.attachedFromSurface || "evidence_tray",
          attached_from_surface: panel.dataset.attachedFromSurface || "evidence_tray",
          target_type: targetType(panel),
          target_id: targetId(panel),
          attachment_role: roleValue(panel),
          validation_state: panel.dataset.validationState || "uploaded",
          human_note: noteValue(panel),
        }));
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
          render(panel, [], "파일 첨부는 Data Lake 활성화 후 사용할 수 있습니다. 판단 기록은 계속 남길 수 있습니다.");
          return;
        }
      }
      if (input) input.value = "";
      await refresh(panel);
    } catch (error) {
      render(panel, [], `파일 첨부 실패: ${error.message || String(error)}`);
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = previousText || "파일 첨부";
      }
    }
  }

  async function remove(panel, artifactId) {
    if (!artifactId) return;
    const params = new URLSearchParams({
      employee_id: employeeId(panel),
      target_type: targetType(panel),
      target_id: targetId(panel),
      user_confirmed: "true",
    });
    try {
      await fetch(`/api/data-lake/artifacts/${encodeURIComponent(artifactId)}/attach?${params.toString()}`, {
        method: "DELETE",
      });
    } catch (_error) {
      // Keep the tray responsive even if an optional Data Lake backend is down.
    }
    await refresh(panel);
  }

  function attachEvents(panel) {
    panel.addEventListener("click", (event) => {
      const uploadButton = event.target.closest("[data-evidence-upload]");
      if (uploadButton) {
        void upload(panel);
        return;
      }
      const removeButton = event.target.closest("[data-evidence-remove]");
      if (removeButton) {
        void remove(panel, removeButton.dataset.evidenceRemove || "");
      }
    });
    panel.addEventListener("dragover", (event) => {
      event.preventDefault();
      panel.classList.add("drag-over");
    });
    panel.addEventListener("dragleave", () => panel.classList.remove("drag-over"));
    panel.addEventListener("drop", (event) => {
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
    void refresh(panel);
  });
})();
