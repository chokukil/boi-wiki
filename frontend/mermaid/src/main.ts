import mermaid from "mermaid";

type MermaidApi = typeof mermaid;

declare global {
  interface Window {
    BoiMermaidRender?: (root?: ParentNode) => Promise<void>;
  }
}

const MAX_LOAD_ATTEMPTS = 2;
const RENDER_TIMEOUT_MS = 20_000;
let renderQueue = Promise.resolve();
let renderSequence = 0;
let initialized = false;

function diagrams(root: ParentNode = document): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(".mermaid-diagram"));
}

function sourceFor(diagram: HTMLElement): string {
  return diagram.dataset.mermaidSource || diagram.querySelector<HTMLElement>(".mermaid")?.textContent || "";
}

function statusElement(diagram: HTMLElement): HTMLElement {
  let status = diagram.querySelector<HTMLElement>(".mermaid-status");
  if (!status) {
    status = document.createElement("p");
    status.className = "mermaid-status";
    status.setAttribute("aria-live", "polite");
    diagram.appendChild(status);
  }
  return status;
}

function setState(diagram: HTMLElement, state: string, message: string): void {
  diagram.dataset.mermaidState = state;
  statusElement(diagram).textContent = message;
  diagram.dispatchEvent(new CustomEvent("boi:mermaid-rendered", { bubbles: true, detail: { state } }));
}

function retryButton(diagram: HTMLElement): HTMLButtonElement {
  let button = diagram.querySelector<HTMLButtonElement>("[data-mermaid-retry]");
  if (button) return button;
  button = document.createElement("button");
  button.type = "button";
  button.className = "button secondary mermaid-retry";
  button.dataset.mermaidRetry = "";
  button.textContent = "다시 그리기";
  button.addEventListener("click", () => {
    button!.hidden = true;
    diagram.dataset.mermaidState = "pending";
    void render(diagram.parentElement || document);
  });
  statusElement(diagram).insertAdjacentElement("afterend", button);
  return button;
}

function fail(diagram: HTMLElement, error: unknown, kind: "load" | "syntax"): void {
  const message = error instanceof Error ? error.message : String(error || "unknown error");
  diagram.dataset.mermaidErrorKind = kind;
  diagram.dataset.mermaidError = message;
  diagram.querySelector<HTMLElement>(".mermaid-source-fallback")?.removeAttribute("open");
  setState(diagram, "failed", kind === "syntax" ? "그림의 내용을 해석하지 못했습니다." : "그림을 불러오지 못했습니다.");
  retryButton(diagram).hidden = false;
}

function initialize(api: MermaidApi): void {
  if (initialized) return;
  api.initialize({
    startOnLoad: false,
    securityLevel: "strict",
    theme: "default",
    flowchart: { htmlLabels: false, useMaxWidth: true },
  });
  initialized = true;
}

async function withTimeout<T>(operation: Promise<T>): Promise<T> {
  let timer = 0;
  const timeout = new Promise<never>((_, reject) => {
    timer = window.setTimeout(() => reject(new Error("Mermaid render timed out")), RENDER_TIMEOUT_MS);
  });
  return Promise.race([operation, timeout]).finally(() => window.clearTimeout(timer));
}

async function renderDiagram(diagram: HTMLElement): Promise<void> {
  if (!diagram.isConnected || diagram.dataset.mermaidState === "rendered") return;
  const node = diagram.querySelector<HTMLElement>(".mermaid");
  if (!node) return;
  retryButton(diagram).hidden = true;
  setState(diagram, "rendering", "흐름 그림을 그리고 있습니다.");
  const source = sourceFor(diagram).trim();
  if (!source) {
    fail(diagram, new Error("empty Mermaid source"), "syntax");
    return;
  }
  initialize(mermaid);
  for (let attempt = 1; attempt <= MAX_LOAD_ATTEMPTS; attempt += 1) {
    try {
      diagram.dataset.mermaidAttempts = String(attempt);
      const renderId = `boi-mermaid-${Date.now()}-${renderSequence += 1}`;
      const result = await withTimeout(mermaid.render(renderId, source));
      node.innerHTML = result.svg;
      result.bindFunctions?.(node);
      delete diagram.dataset.mermaidError;
      delete diagram.dataset.mermaidErrorKind;
      setState(diagram, "rendered", "흐름 그림이 준비되었습니다.");
      return;
    } catch (error) {
      if (attempt < MAX_LOAD_ATTEMPTS) {
        await new Promise((resolve) => window.setTimeout(resolve, 180 * attempt));
        continue;
      }
      const message = error instanceof Error ? error.message : String(error || "");
      const syntax = /parse|syntax|lexical|diagram type/i.test(message);
      fail(diagram, error, syntax ? "syntax" : "load");
    }
  }
}

async function renderNow(root: ParentNode = document): Promise<void> {
  const pending = diagrams(root).filter((diagram) => diagram.dataset.mermaidState !== "rendered");
  for (const diagram of pending) await renderDiagram(diagram);
}

function render(root: ParentNode = document): Promise<void> {
  renderQueue = renderQueue.catch(() => undefined).then(() => renderNow(root));
  return renderQueue;
}

window.BoiMermaidRender = render;
document.addEventListener("DOMContentLoaded", () => void render(document));
document.addEventListener("boi:markdown-rendered", (event) => void render(event.target as ParentNode));

const observer = new MutationObserver((mutations) => {
  const added = mutations.some((mutation) => Array.from(mutation.addedNodes).some((node) => (
    node instanceof Element && (node.matches(".mermaid-diagram") || Boolean(node.querySelector(".mermaid-diagram")))
  )));
  if (added) void render(document);
});

document.addEventListener("DOMContentLoaded", () => observer.observe(document.body, { childList: true, subtree: true }));
