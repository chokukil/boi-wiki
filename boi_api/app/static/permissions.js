(function () {
  const admin = document.querySelector("[data-rbac-admin]");
  if (!admin || admin.dataset.initialized === "true") return;
  admin.dataset.initialized = "true";

  const params = new URLSearchParams(window.location.search);
  const employeeId = params.get("employee_id") || document.getElementById("boi-agent-root")?.dataset.employeeId || "100001";
  const result = admin.querySelector("[data-rbac-result]");

  function setResult(message, kind) {
    if (!result) return;
    result.textContent = message;
    result.dataset.state = kind || "info";
  }

  function apiPath(path) {
    const url = new URL(path, window.location.origin);
    url.searchParams.set("employee_id", employeeId);
    return url.toString();
  }

  async function postJson(path, body) {
    const response = await fetch(apiPath(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || payload.message || `HTTP ${response.status}`);
    }
    return payload;
  }

  async function getJson(path) {
    const response = await fetch(apiPath(path));
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || payload.message || `HTTP ${response.status}`);
    }
    return payload;
  }

  function formValues(form) {
    const data = new FormData(form);
    return Object.fromEntries(data.entries());
  }

  function disableForm(form, disabled) {
    form.querySelectorAll("button").forEach((node) => {
      node.disabled = disabled;
    });
  }

  function reloadSoon() {
    window.setTimeout(() => window.location.reload(), 1200);
  }

  async function submitTeam(form) {
    const values = formValues(form);
    await postJson("/api/rbac/teams", {
      team_id: String(values.team_id || "").trim(),
      display_name: String(values.display_name || "").trim(),
      description: String(values.description || "").trim(),
      status: values.status || "active",
    });
    setResult("팀 정보를 저장했습니다. 목록을 갱신합니다.", "success");
    reloadSoon();
  }

  async function submitMember(form) {
    const values = formValues(form);
    const teamId = String(values.team_id || "").trim();
    await postJson(`/api/rbac/teams/${encodeURIComponent(teamId)}/members`, {
      employee_id: String(values.employee_id || "").trim(),
      role: values.role || "member",
      action: values.action || "add",
    });
    setResult("팀 멤버 변경을 반영했습니다. 목록을 갱신합니다.", "success");
    reloadSoon();
  }

  async function submitBinding(form) {
    const data = new FormData(form);
    const roles = data.getAll("roles").map(String).filter(Boolean);
    if (!roles.length) {
      throw new Error("역할을 하나 이상 선택하세요.");
    }
    await postJson("/api/rbac/bindings", {
      subject_type: data.get("subject_type") || "employee",
      subject_id: String(data.get("subject_id") || "").trim(),
      roles,
      scope: String(data.get("scope") || "global").trim() || "global",
      resource: String(data.get("resource") || "").trim(),
    });
    setResult("역할 부여를 저장했습니다. 목록을 갱신합니다.", "success");
    reloadSoon();
  }

  async function submitDocAccess(form) {
    const values = formValues(form);
    const boiId = String(values.boi_id || "").trim();
    if (!boiId) {
      throw new Error("BoI ID를 입력하세요.");
    }
    const body = await getJson(`/api/docs/${encodeURIComponent(boiId)}/access`);
    const access = body.access || {};
    const labels = [
      access.can_read ? "읽기 가능" : "읽기 불가",
      access.can_use_in_agent_context ? "Agent context 가능" : "Agent context 제한",
      access.can_edit ? "수정 가능" : "수정 제한",
    ];
    const detail = [
      access.visibility ? `visibility=${access.visibility}` : "",
      access.classification ? `classification=${access.classification}` : "",
      access.acl_policy ? `acl=${access.acl_policy}` : "",
    ].filter(Boolean).join(" · ");
    setResult(`${boiId}: ${labels.join(" · ")}${detail ? ` (${detail})` : ""}`, access.can_read ? "success" : "error");
  }

  const handlers = {
    team: submitTeam,
    member: submitMember,
    binding: submitBinding,
    "doc-access": submitDocAccess,
  };

  admin.querySelectorAll("[data-rbac-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const type = form.dataset.rbacForm || "";
      const handler = handlers[type];
      if (!handler) return;
      disableForm(form, true);
      setResult("처리 중...", "loading");
      try {
        await handler(form);
      } catch (error) {
        setResult(`실패: ${error.message}`, "error");
        disableForm(form, false);
      }
    });
  });
})();
