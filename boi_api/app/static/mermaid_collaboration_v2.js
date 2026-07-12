(function () {
  async function createDraft(diagram) {
    if (diagram.dataset.workflowDraftId) return JSON.parse(diagram.dataset.workflowDraftResult || "{}");
    const source = diagram.dataset.mermaidSource || diagram.querySelector(".mermaid")?.textContent || "";
    const title = diagram.dataset.mermaidTitle || "업무 흐름 초안";
    const response = await fetch("/api/mermaid/workflow-draft", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, mermaid_source: source, current_url: location.pathname, scope: "private" }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : `HTTP ${response.status}`);
    diagram.dataset.workflowDraftId = payload.draft?.draft_id || "ready";
    diagram.dataset.workflowDraftResult = JSON.stringify(payload);
    return payload;
  }

  function showResult(diagram, message, href, label) {
    let result = diagram.querySelector("[data-v2-mermaid-result]");
    if (!result) {
      result = document.createElement("div");
      result.className = "mermaid-v2-result";
      result.dataset.v2MermaidResult = "";
      diagram.appendChild(result);
    }
    result.innerHTML = "";
    const text = document.createElement("span");
    text.textContent = message;
    result.appendChild(text);
    if (href) {
      const link = document.createElement("a");
      link.href = href;
      link.textContent = label || "이어가기";
      result.appendChild(link);
    }
  }

  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-v2-mermaid-action]");
    if (!button) return;
    const diagram = button.closest("[data-v2-mermaid]");
    if (!diagram || button.disabled) return;
    const action = button.dataset.v2MermaidAction;
    button.disabled = true;
    try {
      if (action === "agent") {
        sessionStorage.setItem("boiAgentV2Mermaid", diagram.dataset.mermaidSource || "");
        location.href = "/agent?from=mermaid";
        return;
      }
      const payload = await createDraft(diagram);
      const draft = payload.draft || {};
      const draftId = draft.draft_id || "";
      if (action === "event") {
        showResult(diagram, "Task 후보를 만들었습니다.", `/sops/new?focus=event&mermaid_draft_id=${encodeURIComponent(draftId)}`, "업무 이벤트 연결");
      } else if (action === "actions") {
        const count = (draft.candidate_links?.actions || []).length;
        showResult(diagram, `관련 Action 후보 ${count}건을 찾았습니다.`, draft.sop_builder_url || "", "Task별로 확인");
      } else if (action === "sop" || action === "create_sop_draft") {
        showResult(diagram, `SOP 초안으로 이어갈 Task 후보 ${(draft.workflow_tasks || []).length}개를 준비했습니다.`, draft.sop_builder_url || "", "SOP에서 다듬기");
      } else {
        showResult(diagram, `Task 후보 ${(draft.workflow_tasks || []).length}개를 만들었습니다.`, draft.sop_builder_url || "", "SOP에서 다듬기");
      }
    } catch (error) {
      showResult(diagram, `흐름을 이어가지 못했습니다. ${error.message}`);
    } finally {
      button.disabled = false;
    }
  });
})();
