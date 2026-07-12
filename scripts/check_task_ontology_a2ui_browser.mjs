#!/usr/bin/env node
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { get } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

const baseUrl = (process.argv.find((item) => item.startsWith("--base-url=")) || "--base-url=http://127.0.0.1:8765").split("=")[1].replace(/\/$/, "");
const outputPath = (process.argv.find((item) => item.startsWith("--output=")) || "--output=").split("=")[1];
const screenshotDir = (process.argv.find((item) => item.startsWith("--screenshot-dir=")) || "--screenshot-dir=").split("=")[1];
const timeoutMs = Number((process.argv.find((item) => item.startsWith("--timeout-ms=")) || "--timeout-ms=30000").split("=")[1]);
const viewports = [{ name: "desktop", width: 1440, height: 1000 }, { name: "compact", width: 1180, height: 850 }, { name: "mobile", width: 390, height: 844 }];

function chromePath() {
  const paths = [process.env.CHROME_BIN, "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser", "/snap/bin/chromium"].filter(Boolean);
  const found = paths.find((item) => existsSync(item));
  if (!found) throw new Error("Chrome/Chromium binary not found");
  return found;
}

function fetchJson(url, timeout = 5000) {
  return new Promise((resolve, reject) => {
    const request = get(url, (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => { body += chunk; });
      response.on("end", () => {
        try { resolve(JSON.parse(body)); } catch (error) { reject(error); }
      });
    });
    request.on("error", reject);
    request.setTimeout(timeout, () => request.destroy(new Error(`timeout: ${url}`)));
  });
}

async function waitForJson(url) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try { return await fetchJson(url); } catch (_error) { await sleep(100); }
  }
  throw new Error(`browser endpoint not ready: ${url}`);
}

class Cdp {
  constructor(url) { this.url = url; this.ws = null; this.id = 1; this.pending = new Map(); this.listeners = new Map(); }
  async connect() {
    this.ws = new WebSocket(this.url);
    await new Promise((resolve, reject) => { this.ws.addEventListener("open", resolve, { once: true }); this.ws.addEventListener("error", reject, { once: true }); });
    this.ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        const pending = this.pending.get(message.id); this.pending.delete(message.id);
        message.error ? pending.reject(new Error(message.error.message)) : pending.resolve(message.result || {});
      } else if (message.method) for (const fn of this.listeners.get(message.method) || []) fn(message.params || {});
    });
  }
  send(method, params = {}) { const id = this.id++; this.ws.send(JSON.stringify({ id, method, params })); return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject })); }
  on(method, fn) { if (!this.listeners.has(method)) this.listeners.set(method, new Set()); this.listeners.get(method).add(fn); }
  once(method) { return new Promise((resolve) => { const fn = (value) => { this.listeners.get(method)?.delete(fn); resolve(value); }; this.on(method, fn); }); }
  async eval(expression) {
    const result = await this.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true, userGesture: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    return result.result?.value;
  }
  async screenshot(path) { const result = await this.send("Page.captureScreenshot", { format: "png", fromSurface: true }); if (path) writeFileSync(path, Buffer.from(result.data, "base64")); }
  close() { this.ws?.close(); }
}

async function wait(cdp, expression, timeout = timeoutMs) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) { if (await cdp.eval(expression)) return true; await sleep(120); }
  throw new Error(`timeout waiting for ${expression}`);
}

async function navigate(cdp, url, selector) {
  const loaded = cdp.once("Page.loadEventFired");
  await cdp.send("Page.navigate", { url });
  await loaded;
  await wait(cdp, `document.readyState === "complete" && !!document.querySelector(${JSON.stringify(selector)})`);
}

async function runViewport(cdp, viewport) {
  await cdp.send("Emulation.setDeviceMetricsOverride", { width: viewport.width, height: viewport.height, deviceScaleFactor: 1, mobile: viewport.width < 600 });
  const failures = [];
  await navigate(cdp, `${baseUrl}/knowledge-graph?employee_id=100001`, ".knowledge-graph-canvas");
  await wait(cdp, `document.querySelector('.knowledge-graph-canvas canvas')?.width > 20`);
  const graph = await cdp.eval(`(() => ({ canvas: !!document.querySelector('.knowledge-graph-canvas canvas'), details: !!document.querySelector('[data-knowledge-node-details]'), rawRef: document.querySelector('#graph-source-ref')?.value?.startsWith('boi:'), overflow: Math.max(0, document.documentElement.scrollWidth-innerWidth), consoleTitle: document.title }))()`);
  if (!graph.canvas) failures.push("ontology canvas is blank");
  if (!graph.details) failures.push("ontology node details are missing");
  if (graph.rawRef) failures.push("raw ontology ref is visible");
  if (graph.overflow > 1) failures.push(`ontology overflow ${graph.overflow}px`);

  let agentSurface = { checked: false };
  if (viewport.name === "desktop") {
    agentSurface = await cdp.eval(`(async () => {
      const setResponse = await fetch('/api/v2/starter-suggestion-sets', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({page_ref:'/knowledge-graph', work_session_id:''})});
      if (!setResponse.ok) return {checked:true, error:'starter set '+setResponse.status};
      const suggestionSet = await setResponse.json();
      const suggestion = (suggestionSet.items || []).find(item => ['table','timeline','mermaid','explorer'].includes(item.result_kind)) || (suggestionSet.items || [])[0];
      if (!suggestion) return {checked:true, error:'no grounded suggestion'};
      const turnResponse = await fetch('/api/v2/agent/turns', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({question:suggestion.prompt, page_ref:'/knowledge-graph', suggestion_set_id:suggestionSet.set_id, suggestion_id:suggestion.suggestion_id})});
      if (!turnResponse.ok) return {checked:true, error:'turn '+turnResponse.status};
      const turn = await turnResponse.json();
      const surfaceResponse = await fetch('/api/v2/a2ui-surfaces/'+encodeURIComponent(turn.a2ui_surface_ref || ''));
      const surface = surfaceResponse.ok ? await surfaceResponse.json() : null;
      const components = (surface?.components || []).map(item => item.component);
      const invalid = surface ? structuredClone(surface) : null;
      if (invalid) invalid.components.push({id:'untrusted',component:'RawHtml',props:{html:'<script>x</script>'}});
      return {checked:true, surfaceRef:turn.a2ui_surface_ref || '', artifactRef:turn.artifact_refs?.[0]?.artifact_id || '', components, invalidRejected: invalid ? window.BoiA2UI?.validate(invalid) === null : false, error:''};
    })()`);
    if (agentSurface.error) failures.push(`Agent A2UI: ${agentSurface.error}`);
    if (!agentSurface.surfaceRef || !agentSurface.components?.includes("Answer")) failures.push("Agent A2UI surface was not restored");
    if (!agentSurface.invalidRejected) failures.push("invalid A2UI surface was not rejected");
  }

  const inbox = await fetchJson(`${baseUrl}/api/inbox?employee_id=100001&limit=5`);
  const task = (inbox.items || []).find((item) => item.task_ref);
  if (!task) failures.push("fixture task is missing");
  else {
    await navigate(cdp, `${baseUrl}/tasks/console?employee_id=100001&task_id=${encodeURIComponent(task.task_ref)}`, ".task-console-page");
    const taskState = await cdp.eval(`(() => ({ form: !!document.querySelector('[data-a2ui-component="WorkRecordForm"]'), evidence: !!document.querySelector('[data-a2ui-component="EvidencePicker"]'), pickers: document.querySelectorAll('[data-directory-picker]').length, raw: document.body.innerText.includes('흐름 원본 보기'), overflow: Math.max(0, document.documentElement.scrollWidth-innerWidth), fields: ['observation','action_taken','decision','result','blocker','next_work'].every(name => !!document.querySelector('[name="'+name+'"]')) }))()`);
    if (!taskState.form || !taskState.evidence || !taskState.fields) failures.push("Task dynamic work form is incomplete");
    if (taskState.pickers < 3) failures.push("Task assignment pickers are incomplete");
    if (taskState.raw) failures.push("raw Mermaid source is visible");
    if (taskState.overflow > 1) failures.push(`task overflow ${taskState.overflow}px`);
  }
  if (screenshotDir) {
    await navigate(cdp, `${baseUrl}/knowledge-graph?employee_id=100001`, ".knowledge-graph-canvas");
    await wait(cdp, `document.querySelector('.knowledge-graph-canvas canvas')?.width > 20`);
    await cdp.screenshot(join(screenshotDir, `ontology-${viewport.width}x${viewport.height}.png`));
  }
  return { viewport, passed: failures.length === 0, failures, graph, agentSurface };
}

async function main() {
  if (screenshotDir) mkdirSync(screenshotDir, { recursive: true });
  const port = 9300 + Math.floor(Math.random() * 400);
  const profile = mkdtempSync(join(tmpdir(), "boi-a2ui-browser-"));
  const child = spawn(chromePath(), ["--headless=new", "--no-sandbox", "--disable-gpu", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "about:blank"], { stdio: "ignore" });
  let cdp;
  const consoleErrors = [];
  try {
    const targets = await waitForJson(`http://127.0.0.1:${port}/json`);
    cdp = new Cdp(targets.find((item) => item.type === "page").webSocketDebuggerUrl);
    await cdp.connect();
    await cdp.send("Page.enable"); await cdp.send("Runtime.enable"); await cdp.send("Log.enable");
    cdp.on("Runtime.exceptionThrown", (item) => consoleErrors.push(item.exceptionDetails?.exception?.description || item.exceptionDetails?.text || "exception"));
    cdp.on("Log.entryAdded", (item) => { if (item.entry?.level === "error") consoleErrors.push(item.entry.text); });
    const results = [];
    for (const viewport of viewports) results.push(await runViewport(cdp, viewport));
    const report = { ok: results.every((item) => item.passed) && consoleErrors.length === 0, browser: "Chrome DevTools Protocol", results, consoleErrors };
    const rendered = JSON.stringify(report, null, 2);
    if (outputPath) writeFileSync(outputPath, rendered + "\n");
    console.log(rendered);
    process.exitCode = report.ok ? 0 : 1;
  } finally {
    cdp?.close(); child.kill("SIGTERM"); await sleep(300); rmSync(profile, { recursive: true, force: true });
  }
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
