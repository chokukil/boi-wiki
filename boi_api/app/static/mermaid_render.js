(function () {
  const CDN_URL = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js";
  let loadPromise = null;

  function diagrams(root) {
    return Array.from((root || document).querySelectorAll(".mermaid-diagram"));
  }

  function setStatus(diagram, message, state) {
    diagram.dataset.mermaidState = state;
    const status = diagram.querySelector(".mermaid-status");
    if (status) status.textContent = message;
  }

  function openFallback(diagram, message) {
    setStatus(diagram, message, "fallback");
    const details = diagram.querySelector(".mermaid-source-fallback");
    if (details) details.open = true;
  }

  function loadMermaid() {
    if (window.mermaid) return Promise.resolve(window.mermaid);
    if (loadPromise) return loadPromise;
    loadPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = CDN_URL;
      script.async = true;
      script.onload = () => window.mermaid ? resolve(window.mermaid) : reject(new Error("Mermaid library unavailable"));
      script.onerror = () => reject(new Error("Mermaid library load failed"));
      document.head.appendChild(script);
      window.setTimeout(() => {
        if (!window.mermaid) reject(new Error("Mermaid library load timed out"));
      }, 8000);
    });
    return loadPromise;
  }

  async function render(root) {
    const pending = diagrams(root).filter((diagram) => diagram.dataset.mermaidState !== "rendered");
    if (!pending.length) return;

    let mermaid;
    try {
      mermaid = await loadMermaid();
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: "default",
        flowchart: { htmlLabels: false, useMaxWidth: true }
      });
    } catch (error) {
      pending.forEach((diagram) => openFallback(diagram, "Mermaid renderer unavailable. Showing source."));
      return;
    }

    for (const diagram of pending) {
      const node = diagram.querySelector(".mermaid");
      if (!node) continue;
      try {
        setStatus(diagram, "Rendering Mermaid diagram...", "rendering");
        await mermaid.run({ nodes: [node] });
        setStatus(diagram, "Mermaid diagram rendered.", "rendered");
      } catch (error) {
        openFallback(diagram, "Mermaid render failed. Showing source.");
      }
    }
  }

  document.addEventListener("DOMContentLoaded", () => render(document));
  document.addEventListener("boi:markdown-rendered", (event) => render(event.target || document));

  const observer = new MutationObserver((mutations) => {
    if (mutations.some((mutation) => Array.from(mutation.addedNodes).some((node) => node.nodeType === 1 && (node.matches?.(".mermaid-diagram") || node.querySelector?.(".mermaid-diagram"))))) {
      render(document);
    }
  });
  document.addEventListener("DOMContentLoaded", () => observer.observe(document.body, { childList: true, subtree: true }));
})();
