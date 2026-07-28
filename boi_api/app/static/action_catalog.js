(() => {
  const root = document.querySelector("[data-action-catalog]");
  if (!root) return;
  const employeeId = root.dataset.employeeId || "";
  const authMode = root.dataset.authMode || "dev";
  const detail = root.querySelector("[data-action-detail-content]");
  const empty = root.querySelector("[data-action-detail-empty]");
  let activeButton = null;
  const withIdentity = (path) => {
    const url = new URL(path, window.location.origin);
    if (authMode === "dev" && employeeId) {
      url.searchParams.set("employee_id", employeeId);
    }
    return `${url.pathname}${url.search}`;
  };

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));

  const render = (action) => {
    const fields = action.input_fields || [];
    const usage = action.workflow_usage || [];
    const flowReference = action.flow_reference_summary || null;
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
      ${flowReference ? `
      <section class="action-detail-section action-flow-reference">
        <div class="action-flow-reference-heading">
          <div>
            <span class="badge status">Langflow Flow</span>
            ${flowReference.uses_boi_knowledge ? '<span class="badge">Wiki·Ontology</span>' : ''}
            <h3>이 Action이 실행하는 Flow</h3>
            <strong>${escapeHtml(flowReference.name)}</strong>
            ${flowReference.project_name ? `<p>${escapeHtml(flowReference.project_name)} 프로젝트</p>` : ''}
          </div>
          <button class="button secondary" type="button" data-action-flow-load>Flow 보기</button>
        </div>
        <div class="action-flow-live-view" data-action-flow-view hidden></div>
      </section>` : ''}
      <section class="action-detail-section">
        <h3>사용 중인 업무 흐름</h3>
        ${usage.length ? `<ul>${usage.map((item) => `<li><a href="${escapeHtml(item.url)}">${escapeHtml(item.title)}</a>${item.sops?.length ? ` · SOP ${item.sops.length}개` : ''}</li>`).join("")}</ul>` : '<p class="muted">아직 연결된 업무 흐름이 없습니다.</p>'}
      </section>
      <section class="action-detail-section">
        <h3>먼저 시험해보기</h3>
        <form data-action-preview-form>
          ${fields.length ? fields.map((field) => `<label>${escapeHtml(field.label)}${field.required ? ' <span aria-label="필수">*</span>' : ''}<input name="${escapeHtml(field.name)}" ${field.required ? 'required' : ''} /></label>`).join("") : '<p class="muted">추가 입력 없이 시험할 수 있습니다.</p>'}
          <div class="button-row"><button class="button secondary" type="submit">요청 확인</button><button class="button secondary" type="button" data-action-dry-run ${action.enabled ? '' : 'disabled'}>Dry-run 실행</button><button class="button primary" type="button" data-action-run ${action.enabled ? '' : 'disabled'}>실제 실행</button></div>
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

    const flowButton = detail.querySelector("[data-action-flow-load]");
    const flowRoot = detail.querySelector("[data-action-flow-view]");
    flowButton?.addEventListener("click", async () => {
      if (!flowRoot) return;
      if (flowRoot.dataset.loaded === "true") {
        flowRoot.hidden = !flowRoot.hidden;
        flowButton.textContent = flowRoot.hidden ? "Flow 보기" : "Flow 접기";
        return;
      }
      flowButton.disabled = true;
      flowRoot.hidden = false;
      flowRoot.innerHTML = '<p class="muted">현재 Flow 구조와 검증 상태를 확인하고 있습니다.</p>';
      try {
        const response = await fetch(withIdentity(
          `/api/actions/catalog/${encodeURIComponent(action.action_key)}/flow`,
        ));
        const payload = await response.json();
        if (!response.ok) {
          const detailMessage = typeof payload.detail === "string"
            ? payload.detail
            : payload.detail && typeof payload.detail.message === "string"
            ? payload.detail.message
            : "Flow 정보를 불러오지 못했습니다.";
          throw new Error(detailMessage);
        }
        const view = payload.flow_view || {};
        const flow = view.flow || {};
        const nodes = (flow.nodes || []).filter((node) => node.on_execution_path);
        const status = view.checksum_state === "drifted"
          ? "변경되어 재검증 필요"
          : view.live_state === "available"
          ? "현재 Flow 확인됨"
          : "마지막 검증 정보";
        const nodeMarkup = nodes.length
          ? `<ol class="action-flow-pipeline">${nodes.map((node) => `
              <li data-role="${escapeHtml(node.role || "component")}">
                <span>${escapeHtml(node.label || node.component_kind || "Component")}</span>
                <small>${escapeHtml(node.component_kind || "")}</small>
              </li>`).join("")}</ol>`
          : '<p class="muted">표시할 실행 경로가 없습니다.</p>';
        const links = view.links || {};
        const linkMarkup = `
          <div class="button-row action-flow-links">
            ${links.playground ? `<a class="button secondary" href="${escapeHtml(links.playground)}">Playground에서 열기</a>` : ''}
            ${links.langflow ? `<a class="button secondary" href="${escapeHtml(links.langflow)}" target="_blank" rel="noopener">Langflow Canvas 열기</a>` : ''}
          </div>`;
        const technical = view.technical || {};
        const technicalMarkup = Object.keys(technical).length
          ? `<details class="technical-details">
              <summary>기술 세부정보</summary>
              <dl>
                <div><dt>Flow ID</dt><dd><code>${escapeHtml(technical.flow_id || "")}</code></dd></div>
                <div><dt>Version</dt><dd>${escapeHtml(technical.artifact_version || "")}</dd></div>
                <div><dt>Checksum</dt><dd><code>${escapeHtml(technical.artifact_checksum || "")}</code></dd></div>
              </dl>
            </details>`
          : "";
        flowRoot.innerHTML = `
          <div class="action-flow-live-heading">
            <div>
              <strong>${escapeHtml(flow.name || flowReference.name)}</strong>
              <p>${escapeHtml(flow.description || "등록된 Action의 실제 실행 경로입니다.")}</p>
            </div>
            <span class="badge ${view.checksum_state === "drifted" ? "warning" : "status"}">${escapeHtml(status)}</span>
          </div>
          <p class="action-flow-meta">${escapeHtml(view.owner_label || "")} · ${escapeHtml(view.project_name || "")} · Component ${Number(flow.node_count || 0)}개</p>
          ${nodeMarkup}
          ${linkMarkup}
          ${technicalMarkup}`;
        flowRoot.dataset.loaded = "true";
        flowButton.textContent = "Flow 접기";
        flowButton.disabled = false;
      } catch (error) {
        flowRoot.innerHTML = `<p class="muted">${escapeHtml(error.message)}</p>`;
        flowButton.disabled = false;
      }
    });

    const form = detail.querySelector("[data-action-preview-form]");
    const output = detail.querySelector("[data-action-preview-result]");
    const fieldTypes = Object.fromEntries(fields.map((field) => [field.name, field.type || "string"]));
    const payloadFromForm = () => Object.fromEntries(
      [...new FormData(form).entries()].map(([name, rawValue]) => {
        if (fieldTypes[name] !== "array") return [name, rawValue];
        return [
          name,
          String(rawValue || "")
            .split(/[\n,]/)
            .map((value) => value.trim())
            .filter(Boolean),
        ];
      }),
    );
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      output.textContent = "입력과 연결 상태를 확인하고 있습니다.";
      const response = await fetch(withIdentity(`/api/actions/catalog/${encodeURIComponent(action.action_key)}/preview`), {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({payload: payloadFromForm()}),
      });
      const value = await response.json();
      output.textContent = value.message || (response.ok ? "확인했습니다." : "확인하지 못했습니다.");
    });
    detail.querySelector("[data-action-dry-run]")?.addEventListener("click", async () => {
      if (!form.reportValidity()) return;
      output.textContent = "외부 변경 없이 시험하고 있습니다.";
      const response = await fetch(withIdentity("/api/actions/invoke"), {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({action_key: action.action_key, payload: payloadFromForm(), dry_run: true}),
      });
      const value = await response.json();
      output.textContent = response.ok ? "Dry-run을 완료했습니다." : (value.detail?.message || value.detail || "Dry-run을 완료하지 못했습니다.");
    });
    detail.querySelector("[data-action-run]")?.addEventListener("click", async () => {
      if (!form.reportValidity()) return;
      if (!window.confirm("이 Action을 현재 로그인한 사용자의 권한으로 실행할까요?")) return;
      output.textContent = "현재 사용자 권한으로 Action을 실행하고 있습니다.";
      const response = await fetch(withIdentity("/api/actions/invoke"), {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({action_key: action.action_key, payload: payloadFromForm(), dry_run: false}),
      });
      const value = await response.json();
      output.textContent = response.ok
        ? "Action 실행을 완료했습니다."
        : (value.detail?.message || value.detail || "Action을 실행하지 못했습니다.");
    });
  };

  root.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-action-open]");
    if (!button) return;
    activeButton?.classList.remove("active");
    activeButton = button;
    button.classList.add("active");
    const location = new URL(window.location.href);
    location.searchParams.set("action_key", button.dataset.actionOpen);
    window.history.replaceState({}, "", `${location.pathname}${location.search}`);
    empty.hidden = true;
    detail.hidden = false;
    detail.innerHTML = '<p class="muted">Action 연결을 확인하고 있습니다.</p>';
    const response = await fetch(withIdentity(
      `/api/actions/catalog/${encodeURIComponent(button.dataset.actionOpen)}`,
    ));
    const payload = await response.json();
    if (!response.ok) {
      detail.innerHTML = '<p>Action 정보를 불러오지 못했습니다.</p>';
      return;
    }
    render(payload.action);
  });

  const initialActionKey = new URLSearchParams(window.location.search).get("action_key") || "";
  if (initialActionKey) {
    const initialButton = [...root.querySelectorAll("[data-action-open]")]
      .find((button) => button.dataset.actionOpen === initialActionKey);
    initialButton?.click();
  }
})();
