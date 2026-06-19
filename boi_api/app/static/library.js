(function () {
  const rootSelector = "#boi-library";
  const linkSelector = ".folder-link, .breadcrumb a";
  const resizeStorageKey = "boiWiki.folderSidebarWidth";
  const resizeMin = 220;
  const resizeMax = 520;

  if ("scrollRestoration" in window.history) {
    window.history.scrollRestoration = "manual";
  }

  function libraryRoot() {
    return document.querySelector(rootSelector);
  }

  function shouldHandleClick(event, link) {
    if (!link || !libraryRoot()) return false;
    if (!link.closest(rootSelector)) return false;
    if (!link.matches(linkSelector)) return false;
    if (event.defaultPrevented || event.button !== 0) return false;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;

    const url = new URL(link.href, window.location.href);
    return url.origin === window.location.origin && url.pathname === "/";
  }

  function partialUrl(url) {
    const next = new URL(url, window.location.href);
    next.searchParams.set("partial", "library");
    return next;
  }

  function clampSidebarWidth(width) {
    const numeric = Number(width);
    if (!Number.isFinite(numeric)) return 270;
    return Math.min(resizeMax, Math.max(resizeMin, Math.round(numeric)));
  }

  function setSidebarWidth(root, width, persist) {
    const nextWidth = clampSidebarWidth(width);
    root.style.setProperty("--folder-sidebar-width", `${nextWidth}px`);
    const handle = root.querySelector("[data-folder-resize-handle]");
    if (handle) {
      handle.setAttribute("aria-valuenow", String(nextWidth));
    }
    if (persist) {
      window.localStorage.setItem(resizeStorageKey, String(nextWidth));
    }
    return nextWidth;
  }

  function restoreSidebarWidth(root) {
    const stored = window.localStorage.getItem(resizeStorageKey);
    if (stored) {
      setSidebarWidth(root, stored, false);
    }
  }

  function initSidebarResize() {
    const root = libraryRoot();
    if (!root) return;
    restoreSidebarWidth(root);

    const sidebar = root.querySelector(".folder-sidebar");
    const handle = root.querySelector("[data-folder-resize-handle]");
    if (!sidebar || !handle || handle.dataset.resizeReady === "true") return;
    handle.dataset.resizeReady = "true";

    function currentWidth() {
      return sidebar.getBoundingClientRect().width;
    }

    handle.addEventListener("pointerdown", function (event) {
      event.preventDefault();
      const startX = event.clientX;
      const startWidth = currentWidth();

      function onPointerMove(moveEvent) {
        moveEvent.preventDefault();
        setSidebarWidth(root, startWidth + moveEvent.clientX - startX, true);
      }

      function onPointerUp() {
        document.removeEventListener("pointermove", onPointerMove);
        document.removeEventListener("pointerup", onPointerUp);
        document.removeEventListener("pointercancel", onPointerUp);
        document.body.classList.remove("is-resizing-sidebar");
      }

      document.body.classList.add("is-resizing-sidebar");
      document.addEventListener("pointermove", onPointerMove);
      document.addEventListener("pointerup", onPointerUp);
      document.addEventListener("pointercancel", onPointerUp);
    });

    handle.addEventListener("keydown", function (event) {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const delta = event.key === "ArrowRight" ? 16 : -16;
      setSidebarWidth(root, currentWidth() + delta, true);
    });
  }

  async function loadLibrary(url, options) {
    const root = libraryRoot();
    if (!root) {
      window.location.href = url;
      return;
    }

    const scrollY = window.scrollY;
    root.classList.add("is-loading");
    root.setAttribute("aria-busy", "true");

    const response = await fetch(partialUrl(url), {
      headers: { "X-Requested-With": "fetch" },
    });
    if (!response.ok) {
      throw new Error("Library partial request failed");
    }

    const html = await response.text();
    const template = document.createElement("template");
    template.innerHTML = html.trim();
    const nextRoot = template.content.querySelector(rootSelector);
    if (!nextRoot) {
      throw new Error("Library partial response missing root");
    }

    root.replaceWith(nextRoot);
    initSidebarResize();
    if (options.push) {
      window.history.pushState({ boiLibrary: true }, "", url);
    }
    window.scrollTo(0, scrollY);
  }

  document.addEventListener("click", async function (event) {
    const link = event.target.closest("a");
    if (!shouldHandleClick(event, link)) return;

    event.preventDefault();
    try {
      await loadLibrary(link.href, { push: true });
    } catch (error) {
      console.error(error);
      window.location.href = link.href;
    }
  });

  window.addEventListener("popstate", function () {
    loadLibrary(window.location.href, { push: false }).catch(function () {
      window.location.reload();
    });
  });

  initSidebarResize();
})();
