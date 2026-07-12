(() => {
  const root = document.querySelector("[data-action-catalog]");
  if (!root) return;
  const employeeId = root.dataset.employeeId || "";
  const detail = root.querySelector("[data-action-detail-content]");
  const empty = root.querySelector("[data-action-detail-empty]");
  let activeButton = null;

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));

  const render = (action) => {
    const fields = action.input_fields || [];
    const usage = action.workflow_usage || [];
    detail.innerHTML = `
      <header class="action-detail-header">
        <div>
          <span class="badge">${escapeHtml(action.connector_kind)}</span>
          <span class="badge">${escapeHtml(action.risk_level)}</span>
          ${action.approval_required ? '<span class="badge warning">확인 필요</span>' : ''}
        </div>
        <h2>${escapeHtml(action.title)}</h2>
        <p>${escapeHtml(action.description)}</p>
      </header>
      <section class="action-detail-section">
        <h3>사용 중인 업무 흐름</h3>
        ${usage.length ? `<ul>${usage.map((item) => `<li><a href="${escapeHtml(item.url)}">${escapeHtml(item.title)}</a>${item.sops?.length ? ` · SOP ${item.sops.length}개` : ''}</li>`).join("")}</ul>` : '<p class="muted">아직 연결된 업무 흐름이 없습니다.</p>'}
      </section>
      <section class="action-detail-section">
        <h3>먼저 시험해보기</h3>
        <form data-action-preview-form>
          ${fields.length ? fields.map((field) => `<label>${escapeHtml(field.label)}${field.required ? ' <span aria-label="필수">*</span>' : ''}<input name="${escapeHtml(field.name)}" ${field.required ? 'required' : ''} /></label>`).join("") : '<p class="muted">추가 입력 없이 시험할 수 있습니다.</p>'}
          <div class="button-row"><button class="button secondary" type="submit">요청 확인</button><button class="button primary" type="button" data-action-dry-run ${action.enabled ? '' : 'disabled'}>Dry-run 실행</button></div>
        </form>
        <div class="action-preview-result" data-action-preview-result aria-live="polite"></div>
      </section>
      <details class="technical-details action-connection-details">
        <summary>연결 정보</summary>
        <p><code>${escapeHtml(action.action_key)}</code></p>
        <p>Event: ${escapeHtml((action.event_types || []).join(", ") || "연결 없음")}</p>
        ${action.doc_url ? `<a class="button secondary" href="${escapeHtml(action.doc_url)}">명세 보기</a>` : ''}
        <h3>API 연동 예시</h3>
        <pre>curl -X POST "&lt;BOI_BASE_URL&gt;/api/actions/invoke" \\
  -H "Authorization: Bearer &lt;BOI_PAT&gt;" \\
  -H "Content-Type: application/json" \\
  -d '${escapeHtml(JSON.stringify(action.api_example.payload))}'</pre>
      </details>`;
    detail.hidden = false;
    empty.hidden = true;

    const form = detail.querySelector("[data-action-preview-form]");
    const output = detail.querySelector("[data-action-preview-result]");
    const payloadFromForm = () => Object.fromEntries(new FormData(form).entries());
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      output.textContent = "입력과 연결 상태를 확인하고 있습니다.";
      const response = await fetch(`/api/actions/catalog/${encodeURIComponent(action.action_key)}/preview?employee_id=${encodeURIComponent(employeeId)}`, {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({payload: payloadFromForm()}),
      });
      const value = await response.json();
      output.textContent = value.message || (response.ok ? "확인했습니다." : "확인하지 못했습니다.");
    });
    detail.querySelector("[data-action-dry-run]")?.addEventListener("click", async () => {
      if (!form.reportValidity()) return;
      output.textContent = "외부 변경 없이 시험하고 있습니다.";
      const response = await fetch(`/api/actions/invoke?employee_id=${encodeURIComponent(employeeId)}`, {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({action_key: action.action_key, payload: payloadFromForm(), dry_run: true}),
      });
      const value = await response.json();
      output.textContent = response.ok ? "Dry-run을 완료했습니다." : (value.detail?.message || value.detail || "Dry-run을 완료하지 못했습니다.");
    });
  };

  root.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-action-open]");
    if (!button) return;
    activeButton?.classList.remove("active");
    activeButton = button;
    button.classList.add("active");
    empty.hidden = true;
    detail.hidden = false;
    detail.innerHTML = '<p class="muted">Action 연결을 확인하고 있습니다.</p>';
    const response = await fetch(`/api/actions/catalog/${encodeURIComponent(button.dataset.actionOpen)}?employee_id=${encodeURIComponent(employeeId)}`);
    const payload = await response.json();
    if (!response.ok) {
      detail.innerHTML = '<p>Action 정보를 불러오지 못했습니다.</p>';
      return;
    }
    render(payload.action);
  });
})();
