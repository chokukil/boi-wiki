#!/usr/bin/env node
import { execFileSync, spawn } from "node:child_process";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { get } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

const BASE_URL = (process.env.BOI_BASE_URL || "http://127.0.0.1:8765").replace(/\/$/, "");
const EMPLOYEE_ID = process.env.BOI_CAPTURE_EMPLOYEE_ID || "100001";

const DOCUMENTS = [
  ["종합 가이드", "boi:public:boi-wiki-manual:guide:final-operator-guide"],
  ["BoI Agent", "boi:public:boi-wiki-manual:agent:using-boi-agent"],
  ["Work Learning", "boi:public:boi-wiki-manual:agent:work-learning-system"],
  ["Living Knowledge", "boi:public:boi-wiki-manual:knowledge:living-knowledge-system"],
  ["Inbox와 Task", "boi:public:boi-wiki-manual:inbox:inbox-and-task-guide"],
  ["업무 이벤트", "boi:public:boi-wiki-manual:workflows:business-event-definition-guide"],
  ["SOP Builder", "boi:public:boi-wiki-manual:sop-workflows:workflow-task-builder-step-by-step"],
  ["자료 보관함", "boi:public:boi-wiki-manual:data-lake:data-lake-artifact-lifecycle"],
  ["Event", "boi:public:boi-wiki-manual:workflows:event-contract-guide"],
  ["Action", "boi:public:boi-wiki-manual:actions:multi-action-connector-guide"],
  ["MCP", "boi:public:boi-wiki-manual:mcp:register-and-use-boi-wiki-mcp"],
  ["운영 Runbook", "boi:public:boi-wiki-manual:operations:operator-runbook"],
  ["Architecture", "boi:team:platform:boi-wiki-architecture-v0.1"],
];

const MOBILE_DOCUMENTS = new Set([
  "boi:public:boi-wiki-manual:guide:final-operator-guide",
  "boi:public:boi-wiki-manual:agent:using-boi-agent",
  "boi:public:boi-wiki-manual:inbox:inbox-and-task-guide",
  "boi:public:boi-wiki-manual:sop-workflows:workflow-task-builder-step-by-step",
  "boi:public:boi-wiki-manual:workflows:business-event-definition-guide",
]);

function chromePath() {
  const candidates = [
    process.env.CHROME_BIN,
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
  ].filter(Boolean);
  const selected = candidates.find((item) => existsSync(item));
  if (!selected) throw new Error("Chrome/Chromium binary not found");
  return selected;
}

function getJson(url, timeoutMs = 2000) {
  return new Promise((resolve, reject) => {
    const request = get(url, (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => { body += chunk; });
      response.on("end", () => {
        try { resolve(JSON.parse(body)); }
        catch (error) { reject(error); }
      });
    });
    request.on("error", reject);
    request.setTimeout(timeoutMs, () => request.destroy(new Error(`timeout: ${url}`)));
  });
}

async function waitJson(url, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    try { return await getJson(url); }
    catch (error) { lastError = error; await sleep(150); }
  }
  throw lastError || new Error(`timeout: ${url}`);
}

class Cdp {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.nextId = 1;
    this.pending = new Map();
    this.listeners = new Map();
  }

  async connect() {
    this.ws = new WebSocket(this.wsUrl);
    await new Promise((resolve, reject) => {
      this.ws.addEventListener("open", resolve, { once: true });
      this.ws.addEventListener("error", reject, { once: true });
    });
    this.ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        const pending = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) pending.reject(new Error(message.error.message || JSON.stringify(message.error)));
        else pending.resolve(message.result || {});
        return;
      }
      for (const listener of this.listeners.get(message.method) || []) listener(message.params || {});
    });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }

  on(method, listener) {
    if (!this.listeners.has(method)) this.listeners.set(method, new Set());
    this.listeners.get(method).add(listener);
  }

  once(method) {
    return new Promise((resolve) => {
      const handler = (payload) => {
        this.listeners.get(method)?.delete(handler);
        resolve(payload);
      };
      this.on(method, handler);
    });
  }

  async eval(expression) {
    const result = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
      userGesture: true,
    });
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || "browser expression failed");
    }
    return result.result?.value;
  }

  close() { this.ws?.close(); }
}

async function waitUntil(cdp, expression, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  let lastValue;
  while (Date.now() < deadline) {
    lastValue = await cdp.eval(expression);
    if (lastValue) return lastValue;
    await sleep(160);
  }
  throw new Error(`timeout waiting for ${expression}; last=${JSON.stringify(lastValue)}`);
}

async function setViewport(cdp, width, height) {
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width,
    height,
    deviceScaleFactor: 1,
    mobile: width < 600,
  });
}

async function inspectDocument(cdp, label, boiId, width, height, runtimeErrors) {
  await setViewport(cdp, width, height);
  runtimeErrors.length = 0;
  const loaded = cdp.once("Page.loadEventFired");
  await cdp.send("Page.navigate", {
    url: `${BASE_URL}/docs/${encodeURIComponent(boiId)}?employee_id=${encodeURIComponent(EMPLOYEE_ID)}`,
  });
  await loaded;
  await waitUntil(cdp, `document.readyState === "complete" && !!document.querySelector("main.doc-page")`);
  await cdp.eval(`(async () => {
    const height = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
    for (let y = 0; y < height; y += Math.max(320, window.innerHeight * 0.7)) {
      window.scrollTo(0, y);
      await new Promise((resolve) => setTimeout(resolve, 35));
    }
    window.scrollTo(0, 0);
    return true;
  })()`);
  await cdp.eval(`(async () => {
    for (const image of document.querySelectorAll('img[src*="current-guide/"]')) {
      image.loading = "eager";
      image.scrollIntoView({ block: "center" });
      await new Promise((resolve) => setTimeout(resolve, 60));
    }
    window.scrollTo(0, 0);
    return true;
  })()`);
  await waitUntil(
    cdp,
    `(() => {
      const roots = [...document.querySelectorAll(".mermaid")];
      return roots.every((root) => {
        const svg = root.querySelector("svg");
        return !!svg && svg.getBoundingClientRect().width > 8 && svg.getBoundingClientRect().height > 8;
      });
    })()`,
    30000,
  );
  await cdp.eval(`Promise.race([
    Promise.all([...document.querySelectorAll('img[src*="current-guide/"]')].map((image) => {
      if (image.complete) return Promise.resolve();
      return new Promise((resolve) => {
        image.addEventListener("load", resolve, { once: true });
        image.addEventListener("error", resolve, { once: true });
      });
    })),
    new Promise((resolve) => setTimeout(resolve, 10000)),
  ]).then(() => true)`);
  await sleep(250);
  const result = await cdp.eval(`(() => {
    const diagrams = [...document.querySelectorAll(".mermaid")];
    const images = [...document.querySelectorAll('img[src*="current-guide/"]')];
    const bodyStyle = getComputedStyle(document.querySelector("main.doc-page") || document.body);
    return {
      title: document.title,
      mermaidCount: diagrams.length,
      renderedMermaidCount: diagrams.filter((root) => {
        const svg = root.querySelector("svg");
        return !!svg && svg.getBoundingClientRect().width > 8 && svg.getBoundingClientRect().height > 8;
      }).length,
      imageCount: images.length,
      brokenImages: images.filter((item) => !item.complete || item.naturalWidth < 1).map((item) => item.getAttribute("src")),
      documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      bodyFontSize: Number.parseFloat(bodyStyle.fontSize || "0"),
    };
  })()`);
  const errors = [...runtimeErrors];
  const ok = (
    result.mermaidCount === result.renderedMermaidCount
    && result.brokenImages.length === 0
    && result.documentOverflow <= 2
    && result.bodyFontSize >= 14
    && errors.length === 0
  );
  return { label, boiId, viewport: `${width}x${height}`, ok, errors, ...result };
}

async function main() {
  execFileSync("curl", ["-fsS", `${BASE_URL}/api/runtime/config?employee_id=${EMPLOYEE_ID}`], { stdio: "ignore" });
  const profile = mkdtempSync(join(tmpdir(), "boi-manual-ui-check-"));
  const port = 9980 + Math.floor(Math.random() * 15);
  const chrome = spawn(chromePath(), [
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`,
    "about:blank",
  ], { stdio: "ignore" });
  let cdp;
  const rows = [];
  const runtimeErrors = [];
  try {
    const targets = await waitJson(`http://127.0.0.1:${port}/json/list`);
    const target = targets.find((item) => item.type === "page" && item.webSocketDebuggerUrl);
    if (!target) throw new Error("Chrome page target was not available");
    cdp = new Cdp(target.webSocketDebuggerUrl);
    await cdp.connect();
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    cdp.on("Runtime.exceptionThrown", (event) => {
      runtimeErrors.push(event.exceptionDetails?.exception?.description || event.exceptionDetails?.text || "runtime exception");
    });
    cdp.on("Runtime.consoleAPICalled", (event) => {
      if (event.type !== "error" && event.type !== "assert") return;
      runtimeErrors.push((event.args || []).map((item) => item.value || item.description || "").join(" "));
    });
    for (const [label, boiId] of DOCUMENTS) {
      try {
        rows.push(await inspectDocument(cdp, label, boiId, 1440, 1000, runtimeErrors));
      } catch (error) {
        throw new Error(`${label} (${boiId}) at 1440x1000: ${error.message}`, { cause: error });
      }
      if (MOBILE_DOCUMENTS.has(boiId)) {
        try {
          rows.push(await inspectDocument(cdp, label, boiId, 390, 844, runtimeErrors));
        } catch (error) {
          throw new Error(`${label} (${boiId}) at 390x844: ${error.message}`, { cause: error });
        }
      }
    }
  } finally {
    cdp?.close();
    chrome.kill("SIGTERM");
    await sleep(150);
    rmSync(profile, { recursive: true, force: true });
  }
  const failures = rows.filter((item) => !item.ok);
  console.log(JSON.stringify({ ok: failures.length === 0, checked: rows.length, failures, rows }, null, 2));
  if (failures.length) process.exitCode = 1;
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
