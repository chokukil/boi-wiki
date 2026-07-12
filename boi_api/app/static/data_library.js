(() => {
  const root = document.querySelector("[data-data-library]");
  if (!root) return;

  const employeeId = root.dataset.employeeId || "";
  const form = root.querySelector("[data-data-library-upload-form]");
  const operationStatus = root.querySelector("[data-data-library-status]");
  const storeStatus = root.querySelector("[data-data-library-store-status]");
  const fileInput = root.querySelector("[data-data-library-file]");
  const fileName = root.querySelector("[data-data-library-file-name]");
  const filePicker = root.querySelector("[data-data-library-file-picker]");
  const list = root.querySelector("[data-data-library-list]");
  const count = root.querySelector("[data-data-library-count]");
  const more = root.querySelector("[data-data-library-more]");
  let uploadReady = root.dataset.uploadReady === "true";
  let uploadInFlight = false;
  let statusTimer = 0;
  let checkingStatus = false;

  const statusLabel = (state, ready, stale) => {
    if (ready && !stale) return "자료 추가 가능";
    if (state === "checking") return "저장소 연결 확인 중";
    if (state === "not_configured") return "운영자 설정 필요";
    return "저장소 연결이 지연되고 있습니다";
  };

  const setUploadControls = (ready) => {
    uploadReady = Boolean(ready);
    root.dataset.uploadReady = uploadReady ? "true" : "false";
    const controlsEnabled = uploadReady && !uploadInFlight;
    form?.querySelectorAll("input, button[type='submit']").forEach((control) => {
      control.disabled = !controlsEnabled;
    });
    filePicker?.setAttribute("aria-disabled", controlsEnabled ? "false" : "true");
  };

  const scheduleStatusCheck = () => {
    window.clearTimeout(statusTimer);
    if (root.dataset.uploadState === "not_configured") return;
    statusTimer = window.setTimeout(checkStorageStatus, 2000);
  };

  const applyStoreState = (artifactStore = {}) => {
    const state = String(artifactStore.state || "checking");
    const stale = Boolean(artifactStore.stale);
    const ready = Boolean(artifactStore.upload_ready) && !stale;
    root.dataset.uploadState = state;
    setUploadControls(ready);
    if (storeStatus) {
      storeStatus.textContent = statusLabel(state, ready, stale);
      storeStatus.dataset.state = ready ? "ready" : state;
    }
    scheduleStatusCheck();
  };

  async function checkStorageStatus() {
    if (checkingStatus || document.hidden) {
      scheduleStatusCheck();
      return;
    }
    checkingStatus = true;
    try {
      const response = await fetch(
        `/api/data-lake/status?employee_id=${encodeURIComponent(employeeId)}`,
        { headers: { Accept: "application/json" }, cache: "no-store" },
      );
      if (response.ok) {
        const payload = await response.json();
        applyStoreState(payload.artifact_store || {});
      }
    } catch (_error) {
      root.dataset.uploadState = "unavailable";
      setUploadControls(false);
      if (storeStatus) {
        storeStatus.textContent = "저장소 연결이 지연되고 있습니다";
        storeStatus.dataset.state = "unavailable";
      }
    } finally {
      checkingStatus = false;
      scheduleStatusCheck();
    }
  }

  const addText = (parent, tag, value, className = "") => {
    const node = document.createElement(tag);
    node.textContent = String(value ?? "");
    if (className) node.className = className;
    parent.appendChild(node);
    return node;
  };

  const validationLabel = (value) => ({
    uploaded: "보관됨",
    profiled: "내용 확인됨",
    review_required: "검토 필요",
    verified_evidence: "확인된 근거",
  })[String(value || "uploaded")] || "보관됨";

  const artifactRow = (item = {}) => {
    const row = document.createElement("article");
    row.className = "data-library-row";

    const main = document.createElement("div");
    main.className = "data-library-row-main";
    const title = document.createElement("div");
    addText(title, "span", item.profile?.kind || "file", "badge");
    addText(title, "strong", item.filename || "이름 없는 자료");
    main.appendChild(title);
    addText(main, "small", item.created_at || "");
    row.appendChild(main);

    if (item.human_note) addText(row, "p", item.human_note);
    const meta = document.createElement("div");
    meta.className = "data-library-meta";
    addText(meta, "span", `${Number(item.size_bytes || 0).toLocaleString("ko-KR")} bytes`);
    addText(meta, "span", `업무 연결 ${Array.isArray(item.attachments) ? item.attachments.length : 0}건`);
    addText(meta, "span", validationLabel(item.validation_state));
    row.appendChild(meta);

    const buttons = document.createElement("div");
    buttons.className = "button-row";
    const download = document.createElement("a");
    download.className = "button secondary";
    const downloadUrl = String(item.download_url || "#");
    download.href = `${downloadUrl}${downloadUrl.includes("?") ? "&" : "?"}employee_id=${encodeURIComponent(employeeId)}`;
    download.textContent = "원본 받기";
    buttons.appendChild(download);
    if (item.target_id) addText(buttons, "span", "연결된 업무 자료", "muted");
    row.appendChild(buttons);

    const details = document.createElement("details");
    details.className = "technical-details";
    addText(details, "summary", "연결 정보");
    const idLine = document.createElement("p");
    addText(idLine, "code", item.artifact_id || "");
    details.appendChild(idLine);
    addText(details, "p", `checksum ${item.sha256 || ""}`);
    row.appendChild(details);
    return row;
  };

  const refreshVisibleCount = () => {
    if (!count || !list) return;
    count.textContent = `최근 ${list.querySelectorAll(":scope > .data-library-row").length}건`;
  };

  const insertArtifact = (item, { prepend = false } = {}) => {
    if (!list) return;
    list.querySelector("[data-data-library-empty]")?.remove();
    const row = artifactRow(item);
    if (prepend) list.prepend(row);
    else list.appendChild(row);
    refreshVisibleCount();
  };

  const refreshArtifactList = async () => {
    if (!list) return;
    const params = new URLSearchParams({ employee_id: employeeId, limit: "30" });
    const response = await fetch(`/api/data-lake/artifacts?${params.toString()}`, {
      headers: { Accept: "application/json" },
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "최근 자료를 갱신하지 못했습니다.");
    list.replaceChildren();
    (payload.items || []).forEach((item) => insertArtifact(item));
    if (more) {
      more.dataset.nextCursor = payload.next_cursor || "";
      more.hidden = !payload.next_cursor;
    }
    refreshVisibleCount();
  };

  fileInput?.addEventListener("change", () => {
    if (fileName) fileName.textContent = fileInput.files?.[0]?.name || "선택한 파일 없음";
  });

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!uploadReady) {
      if (operationStatus) operationStatus.textContent = "저장소 연결을 확인하고 있습니다.";
      scheduleStatusCheck();
      return;
    }
    const submit = form.querySelector("button[type='submit']");
    const data = new FormData(form);
    const note = String(data.get("note") || "").trim();
    data.delete("note");
    data.set("visibility", "private");
    data.set("source_context", JSON.stringify({
      attached_from_surface: "data_library",
      attachment_role: "reference",
      human_note: note,
    }));
    uploadInFlight = true;
    setUploadControls(uploadReady);
    root.setAttribute("aria-busy", "true");
    if (operationStatus) operationStatus.textContent = "자료를 안전하게 보관하고 있습니다.";
    try {
      const response = await fetch(`/api/data-lake/artifacts/upload?employee_id=${encodeURIComponent(employeeId)}`, {
        method: "POST",
        body: data,
      });
      const payload = await response.json();
      if (!response.ok || payload.status === "disabled") {
        if (response.status === 503) applyStoreState({ state: "unavailable", upload_ready: false, stale: false });
        throw new Error(payload.message || payload.detail || payload.reason || "자료를 보관하지 못했습니다.");
      }
      if (operationStatus) operationStatus.textContent = "자료를 보관했습니다.";
      try {
        await refreshArtifactList();
      } catch (_refreshError) {
        insertArtifact({ ...payload.artifact, attachments: payload.attachment ? [payload.attachment] : [] }, { prepend: true });
      }
      form.reset();
      if (fileName) fileName.textContent = "선택한 파일 없음";
    } catch (error) {
      if (operationStatus) operationStatus.textContent = error?.message || "자료를 보관하지 못했습니다.";
    } finally {
      root.removeAttribute("aria-busy");
      uploadInFlight = false;
      setUploadControls(uploadReady);
    }
  });

  more?.addEventListener("click", async () => {
    const cursor = more.dataset.nextCursor || "";
    if (!cursor || !list) return;
    more.disabled = true;
    list.setAttribute("aria-busy", "true");
    try {
      const params = new URLSearchParams({ employee_id: employeeId, limit: "30", cursor });
      const response = await fetch(`/api/data-lake/artifacts?${params.toString()}`, { headers: { Accept: "application/json" } });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "자료를 더 불러오지 못했습니다.");
      (payload.items || []).forEach((item) => insertArtifact(item));
      more.dataset.nextCursor = payload.next_cursor || "";
      more.hidden = !payload.next_cursor;
    } catch (error) {
      if (operationStatus) operationStatus.textContent = error?.message || "자료를 더 불러오지 못했습니다.";
    } finally {
      more.disabled = false;
      list.removeAttribute("aria-busy");
    }
  });

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && !uploadReady) checkStorageStatus();
  });
  window.addEventListener("pagehide", () => window.clearTimeout(statusTimer));
  scheduleStatusCheck();
})();
