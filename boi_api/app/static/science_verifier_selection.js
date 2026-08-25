(() => {
  const root = document.querySelector("[data-science-document-ref][data-science-verifier-url]");
  const launcher = root?.querySelector("[data-science-selection-launcher]");
  if (!root || !launcher) return;

  launcher.addEventListener("click", () => {
    const selection = window.getSelection();
    const exact = String(selection?.toString() || "").trim();
    const body = root.querySelector(".markdown-body");
    if (!selection || !exact || !body || !selection.anchorNode || !selection.focusNode) {
      window.alert("본문에서 과학적으로 검토할 문장을 먼저 선택하세요.");
      return;
    }
    if (!body.contains(selection.anchorNode) || !body.contains(selection.focusNode)) {
      window.alert("문서 본문 안의 문장을 선택하세요.");
      return;
    }
    sessionStorage.setItem("boi.science.selection.v1", JSON.stringify({
      document_ref: root.dataset.scienceDocumentRef,
      exact,
      transferred_at: new Date().toISOString(),
    }));
    window.location.assign(root.dataset.scienceVerifierUrl);
  });
})();
