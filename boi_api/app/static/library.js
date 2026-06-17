(function () {
  const rootSelector = "#boi-library";
  const linkSelector = ".folder-link, .breadcrumb a";

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
})();
