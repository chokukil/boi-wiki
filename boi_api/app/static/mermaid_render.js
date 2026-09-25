(function () {
  const SCRIPT_URLS = [
    "/static/vendor/mermaid/mermaid.min.js",
  ];
  let loadPromise = null;
  let renderQueue = Promise.resolve();
  let mermaidRenderLock = Promise.resolve();
  let renderSequence = 0;
  const RENDER_TIMEOUT_MS = 20000;

  function diagrams(root) {
    return Array.from((root || document).querySelectorAll(".mermaid-diagram"));
  }

  function setStatus(diagram, message, state) {
    diagram.dataset.mermaidState = state;
    if (state === "rendering") diagram.dataset.mermaidStartedAt = String(Date.now());
    else delete diagram.dataset.mermaidStartedAt;
    const status = diagram.querySelector(".mermaid-status");
    if (status) status.textContent = message;
    if (state === "rendered" || state === "fallback") {
      diagram.dispatchEvent(new CustomEvent("boi:mermaid-rendered", {
        bubbles: true,
        detail: { state }
      }));
    }
  }

  function openFallback(diagram, message) {
    setStatus(diagram, message, "fallback");
    const details = diagram.querySelector(".mermaid-source-fallback");
    if (details) details.open = true;
  }

  function renderWithLock(factory) {
    const operation = mermaidRenderLock.catch(() => {}).then(factory);
    mermaidRenderLock = operation.catch(() => {});
    return operation;
  }

  function loadScript(url) {
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      let settled = false;
      const fail = (error) => {
        if (settled) return;
        settled = true;
        script.remove();
        reject(error);
      };
      script.src = url;
      script.async = true;
      script.onload = () => {
        if (settled) return;
        if (!window.mermaid) {
          fail(new Error(`Mermaid library unavailable from ${url}`));
          return;
        }
        settled = true;
        resolve(window.mermaid);
      };
      script.onerror = () => fail(new Error(`Mermaid library load failed from ${url}`));
      document.head.appendChild(script);
      window.setTimeout(() => {
        if (!window.mermaid) fail(new Error(`Mermaid library load timed out from ${url}`));
      }, 30000);
    });
  }

  function loadMermaid() {
    if (window.mermaid) return Promise.resolve(window.mermaid);
    if (loadPromise) return loadPromise;
    loadPromise = (async () => {
      let lastError;
      for (const url of SCRIPT_URLS) {
        try {
          return await loadScript(url);
        } catch (error) {
          lastError = error;
        }
      }
      loadPromise = null;
      throw lastError || new Error("Mermaid library unavailable");
    })();
    return loadPromise;
  }

  function withTimeout(factory, timeoutMs, message) {
    let timer;
    const timeout = new Promise((_, reject) => {
      timer = window.setTimeout(() => reject(new Error(message)), timeoutMs);
    });
    const operation = Promise.resolve().then(factory);
    return Promise.race([operation, timeout]).finally(() => window.clearTimeout(timer));
  }

  async function renderNow(root) {
    const pending = diagrams(root).filter((diagram) => {
      const state = diagram.dataset.mermaidState || "pending";
      const startedAt = Number(diagram.dataset.mermaidStartedAt || 0);
      const stale = state === "rendering" && startedAt > 0 && Date.now() - startedAt > RENDER_TIMEOUT_MS;
      return diagram.isConnected && state !== "rendered" && (state !== "rendering" || stale);
    });
    if (!pending.length) return;
    pending.forEach((diagram) => setStatus(diagram, "Rendering Mermaid diagram...", "rendering"));

    let mermaid;
    const libraryStartedAt = performance.now();
    try {
      mermaid = await loadMermaid();
      const libraryMs = Math.round(performance.now() - libraryStartedAt);
      pending.forEach((diagram) => { diagram.dataset.mermaidLibraryMs = String(libraryMs); });
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
        diagram.dataset.mermaidAttempts = String(Number(diagram.dataset.mermaidAttempts || 0) + 1);
        const source = diagram.dataset.mermaidSource || node.textContent || "";
        const renderId = `boi-mermaid-${Date.now()}-${renderSequence += 1}`;
        const queuedAt = performance.now();
        const result = await renderWithLock(() => {
          const startedAt = performance.now();
          diagram.dataset.mermaidQueueMs = String(Math.round(startedAt - queuedAt));
          return withTimeout(
            () => mermaid.render(renderId, source),
            RENDER_TIMEOUT_MS,
            "Mermaid render timed out."
          ).finally(() => { diagram.dataset.mermaidRenderMs = String(Math.round(performance.now() - startedAt)); });
        });
        node.innerHTML = typeof result === "string" ? result : result.svg;
        if (typeof result?.bindFunctions === "function") result.bindFunctions(node);
        delete diagram.dataset.mermaidError;
        setStatus(diagram, "Mermaid diagram rendered.", "rendered");
      } catch (error) {
        const message = String(error?.message || error || "Mermaid render failed");
        diagram.dataset.mermaidError = message;
        diagram.dataset.mermaidLastFailure = message;
        openFallback(diagram, "Mermaid render failed. Showing source.");
      }
    }
  }

  function render(root) {
    renderQueue = renderQueue
      .catch(() => {})
      .then(() => renderNow(root || document));
    return renderQueue;
  }

  // Agent artifacts should not wait behind every document diagram in the
  // global observer queue. Calling this entry point immediately marks the
  // supplied result diagrams as rendering, so the observer safely skips them.
  window.BoiMermaidRender = (root) => renderNow(root || document);

  document.addEventListener("DOMContentLoaded", () => render(document));
  document.addEventListener("DOMContentLoaded", () => {
    const warm = () => loadMermaid().catch(() => {});
    if ("requestIdleCallback" in window) window.requestIdleCallback(warm, { timeout: 1500 });
    else window.setTimeout(warm, 500);
  });
  document.addEventListener("boi:markdown-rendered", (event) => render(event.target || document));

  const observer = new MutationObserver((mutations) => {
    if (mutations.some((mutation) => Array.from(mutation.addedNodes).some((node) => node.nodeType === 1 && (node.matches?.(".mermaid-diagram") || node.querySelector?.(".mermaid-diagram"))))) {
      render(document);
    }
  });
  document.addEventListener("DOMContentLoaded", () => observer.observe(document.body, { childList: true, subtree: true }));
})();
