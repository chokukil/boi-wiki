(function () {
  const labels = new Map();

  function employeeId() {
    return new URL(window.location.href).searchParams.get("employee_id") || "100001";
  }

  function values(picker) {
    const field = picker.querySelector("[data-directory-value]");
    return String(field?.value || "").split(/[,\n]/).map((item) => item.trim()).filter(Boolean);
  }

  function setValues(picker, next) {
    const field = picker.querySelector("[data-directory-value]");
    if (!field) return;
    field.value = [...new Set(next)].join(", ");
    field.dispatchEvent(new Event("change", { bubbles: true }));
    renderChips(picker);
  }

  function renderChips(picker) {
    const target = picker.querySelector("[data-directory-chips]");
    if (!target) return;
    target.innerHTML = "";
    values(picker).forEach((id) => {
      const chip = document.createElement("span");
      chip.className = "directory-chip";
      const text = document.createElement("span");
      text.textContent = labels.get(id) || id;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.setAttribute("aria-label", `${text.textContent} 선택 해제`);
      remove.textContent = "×";
      remove.addEventListener("click", () => setValues(picker, values(picker).filter((item) => item !== id)));
      chip.append(text, remove);
      target.appendChild(chip);
    });
  }

  async function search(picker) {
    const query = picker.querySelector("[data-directory-query]");
    const options = picker.querySelector("[data-directory-options]");
    if (!query || !options) return;
    const kind = picker.dataset.directoryKind === "teams" ? "teams" : "people";
    const url = new URL(`/api/v2/directory/${kind}`, window.location.origin);
    url.searchParams.set("employee_id", employeeId());
    url.searchParams.set("q", query.value.trim());
    options.hidden = false;
    options.innerHTML = '<span class="muted">찾고 있습니다.</span>';
    try {
      const response = await fetch(url, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error("directory unavailable");
      const payload = await response.json();
      options.innerHTML = "";
      (payload.items || []).forEach((item) => {
        const id = String(item.employee_id || item.team_id || "");
        if (!id || values(picker).includes(id)) return;
        const label = item.employee_id
          ? `${item.name || id} · ${id}${(item.teams || []).length ? ` · ${(item.teams || []).join(", ")}` : ""}`
          : String(item.name || id);
        labels.set(id, label);
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = label;
        button.addEventListener("click", () => {
          setValues(picker, [...values(picker), id]);
          query.value = "";
          options.hidden = true;
        });
        options.appendChild(button);
      });
      if (!options.childElementCount) options.innerHTML = '<span class="muted">선택할 수 있는 항목이 없습니다.</span>';
    } catch (_error) {
      options.innerHTML = '<span class="muted">사람·팀 목록을 불러오지 못했습니다.</span>';
    }
  }

  function initialize(root) {
    root.querySelectorAll?.("[data-directory-picker]").forEach((picker) => {
      if (picker.dataset.directoryReady === "true") {
        renderChips(picker);
        return;
      }
      picker.dataset.directoryReady = "true";
      const query = picker.querySelector("[data-directory-query]");
      let timer = 0;
      query?.addEventListener("focus", () => search(picker));
      query?.addEventListener("input", () => {
        window.clearTimeout(timer);
        timer = window.setTimeout(() => search(picker), 180);
      });
      renderChips(picker);
    });
  }

  async function saveAssignment(editor) {
    const status = editor.querySelector("[data-task-assignment-status]");
    const button = editor.querySelector("[data-task-assignment-save]");
    const taskRef = editor.dataset.taskRef || "";
    if (!taskRef || !button) return;
    button.disabled = true;
    if (status) status.textContent = "배정을 저장하고 있습니다.";
    const payload = { completion_policy: "any_assignee", expected_revision: Number(editor.dataset.revision || 0), user_confirmed: true };
    editor.querySelectorAll("[data-assignment-field]").forEach((field) => {
      payload[field.dataset.assignmentField] = String(field.value || "").split(",").map((item) => item.trim()).filter(Boolean);
    });
    try {
      const response = await fetch(`/api/tasks/${encodeURIComponent(taskRef)}/assignment?employee_id=${encodeURIComponent(employeeId())}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "배정을 저장하지 못했습니다.");
      editor.dataset.revision = String(result.assignment_design?.revision || payload.expected_revision + 1);
      if (status) status.textContent = "배정이 저장되었습니다.";
    } catch (error) {
      if (status) status.textContent = error.message || "배정을 저장하지 못했습니다.";
    } finally {
      button.disabled = false;
    }
  }

  document.addEventListener("DOMContentLoaded", () => initialize(document));
  document.addEventListener("click", (event) => {
    const save = event.target.closest("[data-task-assignment-save]");
    if (save) saveAssignment(save.closest("[data-task-assignment]"));
  });
  window.BoiDirectoryPicker = { sync: initialize };
})();
