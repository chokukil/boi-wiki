(function () {
  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function prettyJson(value) {
    return JSON.stringify(value, null, 2);
  }

  async function loadRaw(button) {
    const output = button.parentElement.querySelector(".raw-json-output");
    if (!output || output.dataset.loaded === "true") {
      if (output) output.hidden = false;
      return;
    }
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Loading...";
    try {
      const response = await fetch(button.dataset.rawUrl, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error("HTTP " + response.status);
      const payload = await response.json();
      output.textContent = prettyJson(payload.row || payload);
      output.dataset.loaded = "true";
      output.hidden = false;
      button.textContent = "Raw JSON 새로고침";
    } catch (error) {
      output.textContent = "Raw JSON load failed: " + error.message;
      output.hidden = false;
      button.textContent = original;
    } finally {
      button.disabled = false;
    }
  }

  async function previewEventPattern(button) {
    const output = document.querySelector(".event-pattern-preview-result");
    if (!output) return;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "이력 확인 중...";
    output.className = "event-pattern-preview-result loading";
    output.innerHTML = "<p>현재 필터 조건의 Event 이력을 확인하고 있습니다.</p>";
    try {
      const employeeId = button.dataset.employeeId || "";
      const response = await fetch(`/api/events/patterns/preview?employee_id=${encodeURIComponent(employeeId)}`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          q: button.dataset.q || "",
          event_type: button.dataset.eventType || "",
          trace_id: button.dataset.traceId || "",
          event_id: button.dataset.eventId || "",
          from_time: button.dataset.fromTime || "",
          to_time: button.dataset.toTime || "",
          limit: Number(button.dataset.limit || 50),
        }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || response.statusText);
      const warning = body.low_sample_warning ? `<span class="badge warning">참고 데이터가 적음</span>` : "";
      output.className = "event-pattern-preview-result ok";
      output.innerHTML = `
        <strong>Event 정의 초안 후보</strong>
        <div class="registration-result-list">
          <div class="registration-result-card"><strong>샘플</strong><span>${escapeHtml(body.sample_size)}건 ${warning}</span></div>
          <div class="registration-result-card"><strong>신뢰도</strong><span>${escapeHtml(body.confidence_label || "-")}</span></div>
          <div class="registration-result-card"><strong>추천 Event</strong><span>${escapeHtml(body.suggested_event_type || "확인 필요")}</span></div>
        </div>
        <p>${escapeHtml(body.summary || "")}</p>
        <details>
          <summary>샘플 이력 보기</summary>
          <pre>${escapeHtml(prettyJson(body.samples || []))}</pre>
        </details>
      `;
    } catch (error) {
      output.className = "event-pattern-preview-result error";
      output.innerHTML = `<strong>검토할 수 없습니다</strong><p>${escapeHtml(error.message || String(error))}</p>`;
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  document.addEventListener("click", function (event) {
    const patternButton = event.target.closest(".event-pattern-preview-button");
    if (patternButton) {
      event.preventDefault();
      previewEventPattern(patternButton);
      return;
    }
    const button = event.target.closest(".load-raw-event");
    if (!button) return;
    event.preventDefault();
    loadRaw(button);
  });
})();
