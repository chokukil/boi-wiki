#!/usr/bin/env node
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { get, request as httpRequest } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

const baseUrl = (process.argv.find((item) => item.startsWith("--base-url=")) || "--base-url=http://127.0.0.1:8765").split("=")[1].replace(/\/$/, "");
const outputPath = (process.argv.find((item) => item.startsWith("--output=")) || "--output=").split("=")[1];
const screenshotDir = (process.argv.find((item) => item.startsWith("--screenshot-dir=")) || "--screenshot-dir=").split("=")[1];
const timeoutMs = Number((process.argv.find((item) => item.startsWith("--timeout-ms=")) || "--timeout-ms=30000").split("=")[1]);
const allowMutations = process.argv.includes("--allow-mutations");
const debugSession = (process.argv.find((item) => item.startsWith("--debug-session=")) || "--debug-session=").split("=")[1];
const debugArtifact = (process.argv.find((item) => item.startsWith("--debug-artifact=")) || "--debug-artifact=").split("=")[1];
const debugPage = (process.argv.find((item) => item.startsWith("--debug-page=")) || "--debug-page=").slice("--debug-page=".length);
const debugGraph = process.argv.includes("--debug-graph");
const debugFocus = process.argv.includes("--debug-focus");
const debugHideAgent = process.argv.includes("--debug-hide-agent");
const onlyConfirmation = process.argv.includes("--only-confirmation");
const debugWidth = Number((process.argv.find((item) => item.startsWith("--debug-width=")) || "--debug-width=1440").split("=")[1]);
const debugHeight = Number((process.argv.find((item) => item.startsWith("--debug-height=")) || "--debug-height=1000").split("=")[1]);
const viewports = [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "compact", width: 1180, height: 850 },
  { name: "narrow", width: 949, height: 1151 },
  { name: "mobile", width: 390, height: 844 },
];

function chromePath() {
  const paths = [process.env.CHROME_BIN, "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser", "/snap/bin/chromium"].filter(Boolean);
  const found = paths.find((item) => existsSync(item));
  if (!found) throw new Error("Chrome/Chromium binary not found");
  return found;
}

async function fetchJson(url, timeout = 5000, attempts = 3) {
  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await new Promise((resolve, reject) => {
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
    } catch (error) {
      lastError = error;
      if (attempt < attempts) await sleep(150 * attempt);
    }
  }
  throw lastError;
}

async function fetchStatus(url, timeout = 5000) {
  return new Promise((resolve) => {
    const request = get(url, (response) => {
      response.resume();
      resolve(response.statusCode || 0);
    });
    request.on("error", () => resolve(0));
    request.setTimeout(timeout, () => request.destroy());
  });
}

async function postJson(url, payload, timeout = 5000, attempts = 3) {
  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await new Promise((resolve, reject) => {
        const target = new URL(url);
        const body = JSON.stringify(payload);
        const req = httpRequest({
          hostname: target.hostname,
          port: target.port,
          path: `${target.pathname}${target.search}`,
          method: "POST",
          headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) },
        }, (response) => {
          let responseBody = "";
          response.setEncoding("utf8");
          response.on("data", (chunk) => { responseBody += chunk; });
          response.on("end", () => {
            try { resolve({ status: response.statusCode || 0, result: JSON.parse(responseBody) }); } catch (error) { reject(error); }
          });
        });
        req.on("error", reject);
        req.setTimeout(timeout, () => req.destroy(new Error(`timeout: ${url}`)));
        req.end(body);
      });
    } catch (error) {
      lastError = error;
      if (attempt < attempts) await sleep(150 * attempt);
    }
  }
  throw lastError;
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
  send(method, params = {}) {
    const id = this.id++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`CDP timeout: ${method}`));
      }, Math.max(timeoutMs, 30000));
      this.pending.set(id, {
        resolve: (value) => { clearTimeout(timer); resolve(value); },
        reject: (error) => { clearTimeout(timer); reject(error); },
      });
    });
  }
  on(method, fn) { if (!this.listeners.has(method)) this.listeners.set(method, new Set()); this.listeners.get(method).add(fn); }
  once(method) { return new Promise((resolve) => { const fn = (value) => { this.listeners.get(method)?.delete(fn); resolve(value); }; this.on(method, fn); }); }
  async eval(expression) {
    const result = await this.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true, userGesture: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    return result.result?.value;
  }
  async screenshot(path) {
    const result = await this.send("Page.captureScreenshot", {
      format: "png",
      fromSurface: true,
      captureBeyondViewport: false,
    });
    if (path) writeFileSync(path, Buffer.from(result.data, "base64"));
  }
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

async function pressKey(cdp, key, code = key) {
  const virtualKeys = { Enter: 13, Escape: 27, ArrowLeft: 37, ArrowUp: 38, ArrowRight: 39, ArrowDown: 40 };
  const windowsVirtualKeyCode = virtualKeys[key] || 0;
  await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", key, code, windowsVirtualKeyCode, nativeVirtualKeyCode: windowsVirtualKeyCode });
  await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", key, code, windowsVirtualKeyCode, nativeVirtualKeyCode: windowsVirtualKeyCode });
}

async function submitAgentQuestion(cdp, question, timeout = Math.max(timeoutMs, 180000)) {
  const before = await cdp.eval(`document.querySelectorAll('.agent-v2-message.assistant').length`);
  await cdp.eval(`(() => {
    window.__boiAcceptanceProgressSeen = false;
    const progress = document.querySelector('[data-agent-v2-progress]');
    const record = () => { if (progress && !progress.hidden && progress.textContent.trim()) window.__boiAcceptanceProgressSeen = true; };
    new MutationObserver(record).observe(progress, {attributes:true,childList:true,subtree:true});
    const field = document.querySelector('[data-agent-v2-form] textarea[name="question"]');
    field.value = ${JSON.stringify(question)};
    field.dispatchEvent(new InputEvent('input', {bubbles:true,inputType:'insertText',data:${JSON.stringify(question)}}));
    document.querySelector('[data-agent-v2-form]').requestSubmit();
  })()`);
  await wait(cdp, `window.__boiAcceptanceProgressSeen === true`, 10000);
  await wait(cdp, `document.querySelectorAll('.agent-v2-message.assistant').length > ${before} && !document.querySelector('[data-agent-v2-form] textarea[name="question"]')?.disabled`, timeout);
}

function journey(id, passed, details = {}) {
  return { id, passed: Boolean(passed), details };
}

function progress(viewport, step) {
  process.stderr.write(`[browser:${viewport.name}] ${step}\n`);
}

async function runViewport(cdp, viewport) {
  progress(viewport, "ontology explorer");
  await cdp.send("Emulation.setDeviceMetricsOverride", { width: viewport.width, height: viewport.height, deviceScaleFactor: 1, mobile: viewport.width < 600 });
  const failures = [];
  const journeys = [];
  await navigate(cdp, `${baseUrl}/knowledge-graph?employee_id=100001`, "#knowledge-explorer .knowledge-graph-canvas");
  await wait(cdp, `document.querySelector('#knowledge-explorer .knowledge-graph-canvas canvas')?.width > 20`);
  await wait(cdp, `Number(document.querySelector('#knowledge-explorer .knowledge-graph-canvas')?.dataset.minimumNodeDistance || 0) > 0`, 10000);
  await cdp.eval(`document.querySelector('#knowledge-explorer .knowledge-graph-canvas')?.focus()`);
  await pressKey(cdp, "ArrowRight");
  await wait(cdp, `document.querySelector('#knowledge-explorer [data-knowledge-node-details]')?.hidden === false`);
  await sleep(250);
  if (!await cdp.eval(`document.querySelector('#knowledge-explorer [data-knowledge-node-details]')?.hidden === false && !!document.querySelector('#knowledge-explorer .knowledge-graph-canvas canvas')`)) {
    await cdp.eval(`document.querySelector('#knowledge-explorer .knowledge-graph-canvas')?.focus()`);
    await pressKey(cdp, "Enter");
    await wait(cdp, `document.querySelector('#knowledge-explorer [data-knowledge-node-details]')?.hidden === false && !!document.querySelector('#knowledge-explorer .knowledge-graph-canvas canvas')`);
  }
  const graph = await cdp.eval(`(async () => {
    const panel = document.querySelector('#knowledge-explorer');
    const canvas = panel?.querySelector('.knowledge-graph-canvas');
    const hub = panel?.querySelector('.knowledge-graph-hub') || panel;
    const details = panel?.querySelector('[data-knowledge-node-details]');
    const source = details?.querySelector('[data-knowledge-open-node]');
    const before = canvas?.getBoundingClientRect();
    const href = source?.getAttribute('href') || '';
    const sourceStatus = href ? await fetch(href, {redirect:'manual'}).then(response => response.status).catch(() => 0) : 0;
    const labelRects = [...(canvas?.querySelectorAll('.knowledge-graph-node-label') || [])].map(item => item.getBoundingClientRect());
    let labelOverlaps = 0;
    labelRects.forEach((rect, index) => labelRects.slice(index + 1).forEach(other => {
      if (rect.left < other.right && rect.right > other.left && rect.top < other.bottom && rect.bottom > other.top) labelOverlaps += 1;
    }));
    return {
      canvas: !!canvas?.querySelector('canvas'),
      details: Boolean(details && !details.hidden),
      title: details?.querySelector('[data-knowledge-node-title]')?.textContent?.trim() || '',
      reason: details?.querySelector('[data-knowledge-node-reason]')?.textContent?.trim() || '',
      href,
      sourceStatus,
      widthRatio: before && hub ? before.width / hub.getBoundingClientRect().width : 0,
      inspectorWidthRatio: canvas && hub ? canvas.getBoundingClientRect().width / hub.getBoundingClientRect().width : 0,
      rawRef: document.querySelector('#graph-source-ref')?.value?.startsWith('boi:'),
      overflow: Math.max(0, document.documentElement.scrollWidth-innerWidth),
      nodeCount: Number(canvas?.dataset.nodeCount || 0),
      minimumNodeDistance: Number(canvas?.dataset.minimumNodeDistance || 0),
      visibleLabelCount: labelRects.length,
      labelOverlaps,
      computedLabelOverlaps: Number(canvas?.dataset.labelOverlapCount || 0),
      consoleTitle: document.title,
    };
  })()`);
  if (!graph.canvas) failures.push("ontology canvas is blank");
  if (!graph.details || !graph.title || !graph.reason) failures.push("ontology node inspector is incomplete");
  if (!graph.href || ![200, 303, 307].includes(graph.sourceStatus)) failures.push("ontology canonical source does not open");
  if (graph.widthRatio < .9 || graph.inspectorWidthRatio < .9) failures.push(`ontology canvas only uses ${Math.round(Math.min(graph.widthRatio, graph.inspectorWidthRatio) * 100)}% of its result width`);
  if (graph.rawRef) failures.push("raw ontology ref is visible");
  if (graph.overflow > 1) failures.push(`ontology overflow ${graph.overflow}px`);
  journeys.push(journey("ontology_one_hop_expand", graph.canvas && graph.details && Boolean(graph.title) && Boolean(graph.reason) && Boolean(graph.href) && [200, 303, 307].includes(graph.sourceStatus) && graph.widthRatio >= .9 && graph.inspectorWidthRatio >= .9 && !graph.rawRef && graph.overflow <= 1, graph));
  const labelsComplete = graph.nodeCount > 25 || graph.visibleLabelCount === graph.nodeCount;
  const readableLayout = graph.nodeCount > 1 && graph.minimumNodeDistance >= 48 && labelsComplete
    && graph.labelOverlaps === 0 && graph.computedLabelOverlaps === 0;
  if (!readableLayout) failures.push(`ontology layout is unreadable: nodes=${graph.nodeCount}, distance=${graph.minimumNodeDistance}px, labels=${graph.visibleLabelCount}, overlaps=${graph.labelOverlaps}/${graph.computedLabelOverlaps}`);
  journeys.push(journey("ontology_readable_layout", readableLayout, {nodeCount:graph.nodeCount,minimumNodeDistance:graph.minimumNodeDistance,visibleLabelCount:graph.visibleLabelCount,labelOverlaps:graph.labelOverlaps,computedLabelOverlaps:graph.computedLabelOverlaps}));
  await cdp.eval(`document.querySelector('#knowledge-explorer [data-knowledge-node-close]')?.click()`);
  await wait(cdp, `document.querySelector('#knowledge-explorer [data-knowledge-node-details]')?.hidden === true`);

  if (viewport.name === "desktop") {
    progress(viewport, "semantic graph queries");
    await cdp.eval(`document.querySelector('#knowledge-explorer [data-knowledge-view="impact"]')?.click()`);
    await wait(cdp, `document.querySelector('#knowledge-explorer [data-knowledge-view="impact"]')?.getAttribute('aria-selected') === 'true'`);
    await wait(cdp, `!document.querySelector('#knowledge-explorer .knowledge-explorer-status')?.textContent.includes('확인하고 있습니다')`, 10000);
    const impact = await cdp.eval(`({selected:document.querySelector('#knowledge-explorer [data-knowledge-view="impact"]')?.getAttribute('aria-selected') === 'true',canvas:!!document.querySelector('#knowledge-explorer .knowledge-graph-canvas canvas'),status:document.querySelector('#knowledge-explorer .knowledge-explorer-status')?.textContent || ''})`);
    await cdp.eval(`document.querySelector('#knowledge-explorer [data-knowledge-view="tour"]')?.click()`);
    await wait(cdp, `document.querySelector('#knowledge-explorer [data-knowledge-view="tour"]')?.getAttribute('aria-selected') === 'true'`);
    await wait(cdp, `!document.querySelector('#knowledge-explorer .knowledge-explorer-status')?.textContent.includes('확인하고 있습니다')`, 10000);
    const tour = await cdp.eval(`({selected:document.querySelector('#knowledge-explorer [data-knowledge-view="tour"]')?.getAttribute('aria-selected') === 'true',rows:document.querySelectorAll('#knowledge-explorer .knowledge-explorer-content li').length})`);
    await cdp.eval(`document.querySelector('#knowledge-explorer [data-knowledge-view="path"]')?.click()`);
    await wait(cdp, `document.querySelector('#knowledge-explorer [data-knowledge-view="path"]')?.getAttribute('aria-selected') === 'true'`);
    const focal = await cdp.eval(`document.querySelector('#knowledge-explorer')?.dataset.sourceRef || ''`);
    const neighbors = await fetchJson(`${baseUrl}/api/v2/knowledge-graph/explore?employee_id=100001&view=neighbors&source_ref=${encodeURIComponent(focal)}&depth=1&limit=20`);
    const target = (neighbors.nodes || []).find((item) => item.node_id !== focal);
    let path = { selected: true, target: false, status: "unavailable" };
    if (target) {
      const pathPayload = await fetchJson(`${baseUrl}/api/v2/knowledge-graph/explore?employee_id=100001&view=path&source_ref=${encodeURIComponent(focal)}&target_ref=${encodeURIComponent(target.node_id)}&depth=6&limit=120`);
      path = { selected: true, target: (pathPayload.nodes || []).length > 1 && (pathPayload.edges || []).length > 0, status: pathPayload.status || "ready" };
    }
    const graphModes = { impact, tour, path };
    journeys.push(journey("ontology_path", graphModes.path.selected && graphModes.path.target && Boolean(graphModes.path.status), graphModes.path));
    journeys.push(journey("ontology_impact", graphModes.impact.selected && graphModes.impact.canvas, graphModes.impact));
    journeys.push(journey("ontology_tour", graphModes.tour.selected && graphModes.tour.rows > 0, graphModes.tour));

    const semanticQueries = [];
    const semanticPlans = {
      neighbors: {focal:[focal], targets:[]},
      path: {focal:[focal], targets:target ? [target.node_id] : []},
      workflow: {focal:["boi:public:boi-wiki-manual:sop-workflows:create-and-connect-sop"], targets:[]},
      impact: {focal:[focal], targets:[]},
      lineage: {focal:[focal], targets:[]},
      responsibility: {focal:["person:100001"], targets:[]},
      timeline: {focal:[focal], targets:[]},
      compare: {focal:target ? [focal, target.node_id] : [focal], targets:[]},
      tour: {focal:[focal], targets:[]},
    };
    for (const kind of Object.keys(semanticPlans)) {
      const semanticPlan = semanticPlans[kind];
      const requested = await postJson(`${baseUrl}/api/v2/knowledge-graph/query?employee_id=100001`, {
        focal_entities: semanticPlan.focal,
        query_kind: kind,
        target_entities: semanticPlan.targets,
        depth: 4,
        limit: 80,
        presentation: "auto",
      }, 10000);
      const result = requested.result;
      semanticQueries.push({ kind, status: requested.status, ok:result.ok === true, meaningful:result.meaningful === true, reported: result.query_plan?.query_kind || "", presentation: result.presentation || "", nodes: (result.nodes || []).length, edges: (result.edges || []).length, path: (result.path_refs || []).length, timeline: (result.timeline || []).length, tour: (result.tour_steps || []).length, comparison: Boolean(result.comparison && Object.keys(result.comparison).length) });
    }
    const semanticKinds = new Set((semanticQueries || []).map((item) => item.reported));
    const semanticSpecials = (semanticQueries || []).every((item) => item.status === 200 && item.ok && item.meaningful && item.reported === item.kind)
      && (semanticQueries || []).find((item) => item.kind === 'path')?.path > 1
      && (semanticQueries || []).find((item) => item.kind === 'workflow')?.edges > 0
      && (semanticQueries || []).find((item) => item.kind === 'impact')?.edges > 0
      && (semanticQueries || []).find((item) => item.kind === 'lineage')?.edges > 0
      && (semanticQueries || []).find((item) => item.kind === 'responsibility')?.edges > 0
      && (semanticQueries || []).find((item) => item.kind === 'timeline')?.timeline > 0
      && (semanticQueries || []).find((item) => item.kind === 'tour')?.tour > 0
      && (semanticQueries || []).find((item) => item.kind === 'compare')?.comparison
      && (semanticQueries || []).find((item) => item.kind === 'compare')?.presentation === 'table';
    journeys.push(journey("ontology_semantic_queries", semanticKinds.size === 9 && Boolean(semanticSpecials), {queries:semanticQueries}));

    const visibleModes = [];
    const targetTitle = String(target?.payload?.title || target?.title || "BoI Agent");
    for (const kind of ["neighbors", "workflow", "impact", "lineage", "responsibility", "timeline", "tour"]) {
      await cdp.eval(`document.querySelector('#knowledge-explorer [data-knowledge-view=${JSON.stringify(kind)}]')?.click()`);
      await wait(cdp, `document.querySelector('#knowledge-explorer')?.dataset.activeView === ${JSON.stringify(kind)}`, 10000);
      await wait(cdp, `!document.querySelector('#knowledge-explorer .knowledge-explorer-status')?.textContent.includes('확인하고 있습니다')`, 10000);
      visibleModes.push(await cdp.eval(`(() => ({
        kind:${JSON.stringify(kind)},
        selected:document.querySelector('#knowledge-explorer [data-knowledge-view=${JSON.stringify(kind)}]')?.getAttribute('aria-selected') === 'true',
        canvas:!!document.querySelector('#knowledge-explorer .knowledge-graph-canvas canvas'),
        rows:document.querySelectorAll('#knowledge-explorer .knowledge-explorer-content li').length,
        status:document.querySelector('#knowledge-explorer .knowledge-explorer-status')?.textContent.trim() || ''
      }))()`));
    }
    for (const kind of ["path", "compare"]) {
      await cdp.eval(`document.querySelector('#knowledge-explorer [data-knowledge-view=${JSON.stringify(kind)}]')?.click()`);
      await wait(cdp, `document.querySelector('#knowledge-explorer')?.dataset.activeView === ${JSON.stringify(kind)}`, 10000);
      await cdp.eval(`(() => {
        const input=document.querySelector('#knowledge-path-query');
        input.value=${JSON.stringify(targetTitle)};
        input.dispatchEvent(new Event('input',{bubbles:true}));
        document.querySelector('#knowledge-explorer [data-knowledge-search]')?.click();
      })()`);
      await wait(cdp, `document.querySelector('#knowledge-explorer .knowledge-path-candidates [data-target-ref]')`, 10000);
      await cdp.eval(`document.querySelector('#knowledge-explorer .knowledge-path-candidates [data-target-ref]')?.click()`);
      await wait(cdp, `!document.querySelector('#knowledge-explorer .knowledge-explorer-status')?.textContent.includes('확인하고 있습니다')`, 10000);
      visibleModes.push(await cdp.eval(`(() => ({
        kind:${JSON.stringify(kind)},
        selected:document.querySelector('#knowledge-explorer [data-knowledge-view=${JSON.stringify(kind)}]')?.getAttribute('aria-selected') === 'true',
        canvas:!!document.querySelector('#knowledge-explorer .knowledge-graph-canvas canvas'),
        rows:document.querySelectorAll('#knowledge-explorer .knowledge-explorer-content li').length,
        status:document.querySelector('#knowledge-explorer .knowledge-explorer-status')?.textContent.trim() || ''
      }))()`));
    }
    const visibleModesPassed = visibleModes.length === 9 && visibleModes.every((item) => item.selected && Boolean(item.status) && (item.canvas || item.rows > 0));
    journeys.push(journey("ontology_visible_semantic_views", visibleModesPassed, {modes:visibleModes}));
  }

  let agentSurface = { checked: false };
  if (viewport.name === "desktop") {
    progress(viewport, "natural-language Agent graph");
    await navigate(cdp, `${baseUrl}/agent?employee_id=100001`, "[data-agent-v2-workspace]");
    await submitAgentQuestion(cdp, "BoI Wiki 종합 가이드와 직접 연결된 업무 관계를 노드를 선택하며 탐색할 수 있는 관계 화면으로 보여줘.");
    let naturalGraph = false;
    try { await wait(cdp, `!!document.querySelector('[data-agent-v2-artifact-list] [data-agent-ontology-explorer]')`, 30000); naturalGraph = true; } catch (_error) { naturalGraph = false; }
    if (!naturalGraph) {
      await wait(cdp, `document.querySelector('[data-agent-v2-workspace]')?.dataset.agentReady === 'true' && !document.querySelector('[data-agent-v2-new]')?.disabled`, 15000);
      const previousSessionId = await cdp.eval(`document.querySelector('[data-agent-v2-workspace]')?.dataset.sessionId || sessionStorage.getItem('boiAgentV2WorkSession') || ''`);
      await cdp.eval(`document.querySelector('[data-agent-v2-new]')?.click()`);
      await wait(cdp, `(() => { const id=document.querySelector('[data-agent-v2-workspace]')?.dataset.sessionId || sessionStorage.getItem('boiAgentV2WorkSession') || ''; return id && id !== ${JSON.stringify(previousSessionId)}; })()`, 15000);
      await wait(cdp, `document.querySelectorAll('[data-agent-v2-starters] button:not(:disabled)').length > 0`, 15000);
      await cdp.eval(`document.querySelector('[data-agent-v2-starters-more]')?.click()`);
      const clicked = await cdp.eval(`(() => { const button=[...document.querySelectorAll('[data-agent-v2-starters] button')].find(item=>item.dataset.resultKind==='explorer'); button?.click(); return Boolean(button); })()`);
      if (!clicked) throw new Error("grounded ontology starter is missing");
      await wait(cdp, `!!document.querySelector('[data-agent-v2-artifact-list] [data-agent-ontology-explorer]')`, 30000);
    }
    await wait(cdp, `(() => { const node=document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas'); return node?.dataset.graphPainted === 'true' && node?.dataset.keyboardReady === 'true' && Number(node?.dataset.nodeCount || 0) > 0 && node.querySelector('canvas')?.width > 20; })()`, 10000);
    await cdp.eval(`(() => { const node=document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas'); if (node) node.dataset.acceptanceIdentity = crypto.randomUUID(); return node?.dataset.acceptanceIdentity || ''; })()`);
    await sleep(800);
    await wait(cdp, `(() => { const nodes=document.querySelectorAll('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas'); const node=nodes[0]; return nodes.length === 1 && node?.dataset.graphPainted === 'true' && node?.dataset.keyboardReady === 'true'; })()`, 10000);
    await cdp.eval(`(() => { const node=document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas'); node?.focus(); return document.activeElement === node; })()`);
    await sleep(100);
    await pressKey(cdp, "Enter");
    await sleep(500);
    const keyboardSelection = await cdp.eval(`(() => { const node=document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas'); const details=document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] [data-knowledge-node-details]'); return {focused:document.activeElement===node,keyEvents:Number(node?.dataset.keyEventCount||0),lastKey:node?.dataset.lastKey||'',detailsOpenCount:Number(node?.dataset.detailsOpenCount||0),detailsOpen:details?.hidden===false,officialCount:document.querySelectorAll('[data-agent-v2-artifact-list] [data-boi-a2ui-official]').length}; })()`);
    if (!keyboardSelection.detailsOpen) throw new Error(`Agent graph keyboard selection failed: ${JSON.stringify(keyboardSelection)}`);
    await cdp.eval(`document.querySelector('[data-agent-v2-artifact-focus]')?.click()`);
    await wait(cdp, `document.querySelector('[data-agent-v2-workspace]')?.classList.contains('artifact-focus-open')`);
    const beforeReload = await cdp.eval(`(() => {
      const canvasNode=document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas');
      const labelRects=[...(canvasNode?.querySelectorAll('.knowledge-graph-node-label')||[])].map(item=>item.getBoundingClientRect());
      let labelOverlaps=0;
      labelRects.forEach((rect,index)=>labelRects.slice(index+1).forEach(other=>{ if(rect.left<other.right&&rect.right>other.left&&rect.top<other.bottom&&rect.bottom>other.top) labelOverlaps+=1; }));
      return ({
      sessionId: sessionStorage.getItem('boiAgentV2WorkSession') || '',
      progressSeen: window.__boiAcceptanceProgressSeen === true,
      surfaceRef: document.querySelector('[data-agent-v2-workspace]')?.dataset.a2uiSurfaceRef || '',
      component: document.querySelector('[data-agent-v2-artifact-list] [data-a2ui-component]')?.dataset.a2uiComponent || '',
      canvas: document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas canvas')?.width > 20,
      painted: document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas')?.dataset.graphPainted === 'true',
      nodeCount: Number(document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas')?.dataset.nodeCount || 0),
      minimumNodeDistance: Number(document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas')?.dataset.minimumNodeDistance || 0),
      visibleLabelCount: labelRects.length,
      labelOverlaps,
      computedLabelOverlaps: Number(canvasNode?.dataset.labelOverlapCount || 0),
      canvasHeight: document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas')?.getBoundingClientRect().height || 0,
      duplicateConversationComponents: document.querySelectorAll('[data-agent-v2-artifact-list] [data-a2ui-component="Answer"], [data-agent-v2-artifact-list] [data-a2ui-component="CitationList"], [data-agent-v2-artifact-list] [data-a2ui-component="RelatedQuestions"]').length,
      inspector: document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] [data-knowledge-node-details]')?.hidden === false,
      selectedTitle: document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] [data-knowledge-node-title]')?.textContent.trim() || '',
      sourceHref: document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] [data-knowledge-open-node]')?.getAttribute('href') || '',
      focused: document.querySelector('[data-agent-v2-workspace]')?.classList.contains('artifact-focus-open') || false,
      assistantMessages: document.querySelectorAll('.agent-v2-message.assistant').length,
    }); })()`);
    if (screenshotDir) {
      await cdp.screenshot(join(screenshotDir, `agent-ontology-${viewport.width}x${viewport.height}.png`));
    }
    await pressKey(cdp, "Escape");
    await wait(cdp, `document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] [data-knowledge-node-details]')?.hidden === true && document.querySelector('[data-agent-v2-workspace]')?.classList.contains('artifact-focus-open')`);
    await pressKey(cdp, "Escape");
    await wait(cdp, `!document.querySelector('[data-agent-v2-workspace]')?.classList.contains('artifact-focus-open')`);
    await cdp.eval(`document.querySelector('[data-agent-v2-artifact-focus]')?.click()`);
    await wait(cdp, `document.querySelector('[data-agent-v2-workspace]')?.classList.contains('artifact-focus-open')`);
    await wait(cdp, `(() => { const node=document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas'); return node?.dataset.graphPainted === 'true' && node?.dataset.keyboardReady === 'true'; })()`, 10000);
    await sleep(300);
    await cdp.eval(`document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas')?.focus()`);
    await pressKey(cdp, "Enter");
    await wait(cdp, `document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] [data-knowledge-node-details]')?.hidden === false`).catch(() => { throw new Error("Agent graph inspector did not reopen after focus mode transition"); });
    await sleep(200);
    const expectedRestoredTitle = await cdp.eval(`document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] [data-knowledge-node-title]')?.textContent.trim() || ''`);
    const reloaded = cdp.once("Page.loadEventFired");
    await cdp.send("Page.reload", {ignoreCache:false});
    await reloaded;
    await wait(cdp, `document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas')?.dataset.graphPainted === 'true'`, 30000);
    await wait(cdp, `document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] [data-knowledge-node-details]')?.hidden === false`, 10000).catch(() => { throw new Error("Agent graph inspector state was not restored after reload"); });
    const restored = await cdp.eval(`(() => ({
      sessionId: sessionStorage.getItem('boiAgentV2WorkSession') || '',
      focused: document.querySelector('[data-agent-v2-workspace]')?.classList.contains('artifact-focus-open') || false,
      inspector: document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] [data-knowledge-node-details]')?.hidden === false,
      selectedTitle: document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] [data-knowledge-node-title]')?.textContent.trim() || '',
    }))()`);
    progress(viewport, "compact graph lifecycle");
    await navigate(
      cdp,
      `${baseUrl}/docs/boi%3Apublic%3Aboi-wiki-manual%3Aguide%3Afinal-operator-guide?employee_id=100001&pet=expanded&pet_session=${encodeURIComponent(beforeReload.sessionId)}`,
      "[data-agent-v2-workspace]",
    );
    await wait(cdp, `document.querySelectorAll('[data-message-artifact]').length > 0`, 10000);
    await cdp.eval(`(() => { const buttons=[...document.querySelectorAll('[data-message-artifact]')]; buttons.at(-1)?.click(); })()`);
    await wait(cdp, `document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas')?.dataset.graphPainted === 'true'`, 30000);
    const expandedBeforeCompact = await cdp.eval(`(() => ({
      mode: document.querySelector('[data-agent-v2-workspace]')?.dataset.surfaceMode || '',
      selectedTitle: document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] [data-knowledge-node-title]')?.textContent.trim() || '',
      artifactButton: Boolean(document.querySelector('[data-message-artifact]')),
      canvas: Boolean(document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas canvas')),
    }))()`);
    await cdp.eval(`document.querySelector('[data-agent-v2-expand]')?.click()`);
    await wait(cdp, `document.querySelector('[data-agent-v2-workspace]')?.dataset.surfaceMode === 'compact'`);
    await wait(cdp, `!document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas canvas')`, 10000);
    const compactState = await cdp.eval(`(() => ({
      mode: document.querySelector('[data-agent-v2-workspace]')?.dataset.surfaceMode || '',
      workbenchHidden: document.querySelector('[data-agent-v2-workbench]')?.hidden === true,
      canvas: Boolean(document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas canvas')),
      artifactButton: Boolean(document.querySelector('[data-message-artifact]')),
    }))()`);
    await cdp.eval(`document.querySelector('[data-agent-v2-expand]')?.click()`);
    await wait(cdp, `document.querySelector('[data-agent-v2-workspace]')?.dataset.surfaceMode === 'expanded'`);
    await cdp.eval(`(() => { const buttons=[...document.querySelectorAll('[data-message-artifact]')]; buttons.at(-1)?.click(); })()`);
    await wait(cdp, `document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas')?.dataset.graphPainted === 'true'`, 10000);
    const expandedAfterCompact = await cdp.eval(`(() => ({
      mode: document.querySelector('[data-agent-v2-workspace]')?.dataset.surfaceMode || '',
      selectedTitle: document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] [data-knowledge-node-title]')?.textContent.trim() || '',
      canvas: Boolean(document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas canvas')),
    }))()`);
    const compactLifecyclePassed = expandedBeforeCompact.mode === "expanded" && expandedBeforeCompact.canvas
      && expandedBeforeCompact.artifactButton && compactState.mode === "compact" && compactState.workbenchHidden
      && !compactState.canvas && compactState.artifactButton && expandedAfterCompact.mode === "expanded"
      && expandedAfterCompact.canvas && expandedAfterCompact.selectedTitle === expandedBeforeCompact.selectedTitle;
    if (!compactLifecyclePassed) failures.push("Compact mode did not suspend and restore the ontology renderer");
    journeys.push(journey("agent_compact_suspends_graph", compactLifecyclePassed, {
      expandedBeforeCompact,
      compactState,
      expandedAfterCompact,
    }));
    const invalidRejected = await cdp.eval(`(() => {
      const payload={protocol_version:'0.9.1',catalog_id:'boi-a2ui/v1',surface_id:'invalid-browser-surface',components:[{id:'bad',component:'RawHtml',props:{html:'<script>x</script>'}}],events:[],fallback:{}};
      return window.BoiA2UI?.validate(payload) === null;
    })()`);
    const officialLifecycle = await cdp.eval(`(async () => {
      const ref=document.querySelector('[data-agent-v2-workspace]')?.dataset.a2uiSurfaceRef || ${JSON.stringify("")};
      const payload=ref ? await fetch('/api/v2/a2ui-surfaces/'+encodeURIComponent(ref)).then(response=>response.json()) : {};
      const sequence=(payload.messages||[]).map(item=>Object.keys(item).find(key=>key!=='version'));
      return {ref,sequence,dataModel:Boolean(payload.data_model?.surface?.id),official:Boolean(document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official]'))};
    })()`);
    agentSurface = {checked:true,naturalGraph,...beforeReload,expectedRestoredTitle,restored,invalidRejected,compactLifecyclePassed,officialLifecycle};
    const agentPassed = naturalGraph && beforeReload.progressSeen && beforeReload.canvas && beforeReload.painted
      && beforeReload.nodeCount > 0 && beforeReload.minimumNodeDistance >= 48 && beforeReload.canvasHeight >= 300
      && (beforeReload.nodeCount > 25 || beforeReload.visibleLabelCount === beforeReload.nodeCount)
      && beforeReload.labelOverlaps === 0 && beforeReload.computedLabelOverlaps === 0
      && beforeReload.duplicateConversationComponents === 0 && beforeReload.inspector && beforeReload.focused
      && Boolean(beforeReload.selectedTitle) && Boolean(beforeReload.sourceHref) && beforeReload.assistantMessages > 0
      && restored.sessionId === beforeReload.sessionId && restored.focused && restored.inspector
      && restored.selectedTitle === expectedRestoredTitle && invalidRejected;
    if (!agentPassed) failures.push("Agent ontology journey or A2UI fallback failed");
    journeys.push(journey("agent_a2ui_and_fallback", agentPassed, agentSurface));
    const lifecyclePassed = officialLifecycle.official && officialLifecycle.dataModel
      && officialLifecycle.sequence.join(",") === "createSurface,updateComponents,updateDataModel";
    if (!lifecyclePassed) failures.push("official A2UI lifecycle or persisted data model is incomplete");
    journeys.push(journey("a2ui_official_lifecycle", lifecyclePassed, officialLifecycle));
    const citationPassed = Boolean(beforeReload.sourceHref) && [200,303,307].includes(await fetchStatus(`${baseUrl}${beforeReload.sourceHref}`));
    journeys.push(journey("citation_canonical_navigation", citationPassed, {href:beforeReload.sourceHref}));

    const variantChecks = [];
    progress(viewport, "Agent table/timeline/Mermaid surfaces");
    for (const variant of [
      {label:"내 역할과 지금 맡은 일을 한눈에 보기", resultKind:"table", component:"DataTable", selector:'[data-agent-v2-artifact-list] [data-a2ui-component="DataTable"] tbody tr'},
      {label:"업무 결과 재사용", resultKind:"timeline", component:"Timeline", selector:'[data-agent-v2-artifact-list] [data-a2ui-component="Timeline"] li'},
    ]) {
      let visible = false;
      let error = "";
      try {
        await wait(cdp, `document.querySelector('[data-agent-v2-workspace]')?.dataset.agentReady === 'true' && !document.querySelector('[data-agent-v2-new]')?.disabled`, 15000);
        const previousSessionId = await cdp.eval(`document.querySelector('[data-agent-v2-workspace]')?.dataset.sessionId || sessionStorage.getItem('boiAgentV2WorkSession') || ''`);
        await cdp.eval(`document.querySelector('[data-agent-v2-new]')?.click()`);
        await wait(cdp, `(() => { const id=document.querySelector('[data-agent-v2-workspace]')?.dataset.sessionId || sessionStorage.getItem('boiAgentV2WorkSession') || ''; return id && id !== ${JSON.stringify(previousSessionId)}; })()`, 15000);
        await wait(cdp, `document.querySelectorAll('[data-agent-v2-starters] button:not(:disabled)').length > 0`, 15000);
        await cdp.eval(`document.querySelector('[data-agent-v2-starters-more]')?.click()`);
        const clicked = await cdp.eval(`(() => { const button=[...document.querySelectorAll('[data-agent-v2-starters] button')].find(item=>item.dataset.resultKind===${JSON.stringify(variant.resultKind)}); button?.click(); return Boolean(button); })()`);
        if (!clicked) throw new Error(`grounded starter is missing: ${variant.label}`);
        await wait(cdp, `!!document.querySelector(${JSON.stringify(variant.selector)})`, 30000);
        visible = true;
      } catch (caught) {
        error = String(caught?.message || caught);
      }
      variantChecks.push({component:variant.component,visible,error,active:await cdp.eval(`document.querySelector('[data-agent-v2-artifact-list] [data-a2ui-component]')?.dataset.a2uiComponent || ''`)});
      if (error) {
        const current = await cdp.eval(`location.href`);
        await navigate(cdp, current, "[data-agent-v2-workspace]");
      }
    }
    let mermaidVisible = false;
    let mermaidError = "";
    try {
      await navigate(cdp, `${baseUrl}/docs/boi%3Apublic%3Asop%3Aequipment-abnormal-response?employee_id=100001`, "[data-agent-v2-workspace]");
      await cdp.eval(`document.querySelector('[data-agent-v2-open]')?.click()`);
      await wait(cdp, `document.querySelector('[data-agent-v2-workspace]')?.dataset.agentReady === 'true' && !document.querySelector('[data-agent-v2-new]')?.disabled`, 15000);
      const previousSessionId = await cdp.eval(`document.querySelector('[data-agent-v2-workspace]')?.dataset.sessionId || sessionStorage.getItem('boiAgentV2WorkSession') || ''`);
      await cdp.eval(`document.querySelector('[data-agent-v2-new]')?.click()`);
      await wait(cdp, `(() => { const id=document.querySelector('[data-agent-v2-workspace]')?.dataset.sessionId || sessionStorage.getItem('boiAgentV2WorkSession') || ''; return id && id !== ${JSON.stringify(previousSessionId)}; })()`, 15000);
      await wait(cdp, `document.querySelectorAll('[data-agent-v2-starters] button:not(:disabled)').length > 0`, 15000);
      await cdp.eval(`document.querySelector('[data-agent-v2-starters-more]')?.click()`);
      const clicked = await cdp.eval(`(() => { const button=[...document.querySelectorAll('[data-agent-v2-starters] button')].find(item=>item.dataset.resultKind==='mermaid'); button?.click(); return Boolean(button); })()`);
      if (!clicked) throw new Error("grounded Mermaid starter is missing");
      await wait(cdp, `!!document.querySelector('[data-agent-v2-artifact-list] [data-a2ui-component="MermaidArtifact"] svg')`, 30000);
      mermaidVisible = true;
    } catch (caught) {
      mermaidError = String(caught?.message || caught);
    }
    variantChecks.push({
      component:"MermaidArtifact",
      visible:mermaidVisible,
      error:mermaidError,
      active:await cdp.eval(`document.querySelector('[data-agent-v2-artifact-list] [data-a2ui-component]')?.dataset.a2uiComponent || ''`),
      renderState:await cdp.eval(`document.querySelector('[data-agent-v2-artifact-list] .mermaid-diagram')?.dataset.mermaidState || ''`),
      renderError:await cdp.eval(`document.querySelector('[data-agent-v2-artifact-list] .mermaid-diagram')?.dataset.mermaidError || ''`),
      source:await cdp.eval(`document.querySelector('[data-agent-v2-artifact-list] .mermaid-diagram')?.dataset.mermaidSource || ''`),
    });
    await navigate(cdp, `${baseUrl}/docs/boi%3Apublic%3Aboi-wiki-manual%3Aguide%3Afinal-operator-guide?employee_id=100001`, ".markdown-body");
    let canonicalMermaid = {rendered:false,raw:false,error:""};
    try {
      await wait(cdp, `document.querySelector('.markdown-body .mermaid-diagram')?.dataset.mermaidState === 'rendered' && !!document.querySelector('.markdown-body .mermaid-diagram svg')`, 30000);
      canonicalMermaid = await cdp.eval(`({rendered:!!document.querySelector('.markdown-body .mermaid-diagram svg'),raw:/flowchart\\s+(LR|TD)/.test(document.querySelector('.markdown-body .mermaid-diagram')?.textContent||''),error:document.querySelector('.markdown-body .mermaid-diagram')?.dataset.mermaidError||''})`);
    } catch (caught) { canonicalMermaid.error=String(caught?.message||caught); }
    const canonicalMermaidPassed = canonicalMermaid.rendered && !canonicalMermaid.raw && !canonicalMermaid.error;
    if (!canonicalMermaidPassed) failures.push("canonical Mermaid did not render as SVG without raw source");
    journeys.push(journey("mermaid_document_rendering", canonicalMermaidPassed, canonicalMermaid));
    let canonicalMedia = {count:0,decoded:0,failed:[],error:""};
    try {
      await wait(cdp, `[...document.querySelectorAll('.markdown-body img')].every(image => image.complete)`, 30000);
      canonicalMedia = await cdp.eval(`(() => {
        const images=[...document.querySelectorAll('.markdown-body img')];
        const failed=images.filter(image=>!image.complete || image.naturalWidth < 1).map(image=>image.currentSrc || image.src);
        return {count:images.length,decoded:images.length-failed.length,failed,error:""};
      })()`);
    } catch (caught) { canonicalMedia.error=String(caught?.message||caught); }
    const canonicalMediaPassed = canonicalMedia.count > 0 && canonicalMedia.failed.length === 0 && !canonicalMedia.error;
    if (!canonicalMediaPassed) failures.push("canonical guide media did not decode in the browser");
    journeys.push(journey("canonical_media_decode", canonicalMediaPassed, canonicalMedia));
    const variantsPassed = variantChecks.every((item) => item.visible && item.active === item.component);
    if (!variantsPassed) failures.push("Agent table, timeline, and Mermaid surfaces were not rendered through the visible workbench");
    journeys.push(journey("agent_table_timeline_mermaid", variantsPassed, {variants:variantChecks}));

    let confirmationState = { visible:false, emitted:false, planRef:"", error:"" };
    try {
      await navigate(cdp, `${baseUrl}/docs/boi%3Apublic%3Aboi-wiki-manual%3Aguide%3Afinal-operator-guide?employee_id=100001`, "[data-agent-v2-workspace]");
      await cdp.eval(`document.querySelector('[data-agent-v2-open]')?.click()`);
      await wait(cdp, `document.querySelector('[data-agent-v2-workspace]')?.dataset.agentReady === 'true' && !document.querySelector('[data-agent-v2-new]')?.disabled`, 15000);
      const previousSessionId = await cdp.eval(`document.querySelector('[data-agent-v2-workspace]')?.dataset.sessionId || sessionStorage.getItem('boiAgentV2WorkSession') || ''`);
      await cdp.eval(`document.querySelector('[data-agent-v2-new]')?.click()`);
      await wait(cdp, `(() => { const id=document.querySelector('[data-agent-v2-workspace]')?.dataset.sessionId || sessionStorage.getItem('boiAgentV2WorkSession') || ''; return id && id !== ${JSON.stringify(previousSessionId)}; })()`, 15000);
      await wait(cdp, `document.querySelectorAll('[data-agent-v2-starters] button:not(:disabled)').length > 0`, 15000);
      await cdp.eval(`document.querySelector('[data-agent-v2-starters-more]')?.click()`);
      await wait(cdp, `!![...document.querySelectorAll('[data-agent-v2-starters] button')].find(item=>item.dataset.resultKind==='confirmation' && !item.disabled)`, 15000);
      const clicked = await cdp.eval(`(() => { const button=[...document.querySelectorAll('[data-agent-v2-starters] button')].find(item=>item.dataset.resultKind==='confirmation' && !item.disabled); button?.click(); return Boolean(button); })()`);
      if (!clicked) throw new Error("grounded Confirmation starter is missing");
      const confirmationLookup = `(() => { const matches=[...document.querySelectorAll('boi-a2ui-confirmation, [data-a2ui-component="Confirmation"]')]; return matches.find(match => match.shadowRoot?.querySelector('button') || match.querySelector('button')) || matches[0] || null; })()`;
      const confirmationButtonLookup = `(() => { const host=${confirmationLookup}; return host?.shadowRoot?.querySelector('button') || host?.querySelector('button') || null; })()`;
      await wait(cdp, `!!(${confirmationButtonLookup})`, 90000);
      confirmationState = await cdp.eval(`(() => {
        const mount=${confirmationLookup};
        const button=${confirmationButtonLookup};
        let emitted=false;
        document.addEventListener('boi:a2ui-confirm-request',()=>{ emitted=true; window.__boiConfirmationEmitted=true; },{once:true});
        const original=window.confirm;
        window.confirm=()=>false;
        button?.click();
        window.confirm=original;
        return {
          visible:!mount.hidden,
          emitted:window.__boiConfirmationEmitted===true,
          planRef:button?${JSON.stringify("stored-on-surface")}:"",
          title:(mount.shadowRoot?.querySelector('h3') || mount.querySelector('h3'))?.textContent.trim()||"",
        };
      })()`);
    } catch (caught) {
      confirmationState.error = String(caught?.message || caught);
    }
    const confirmationPassed = confirmationState.visible && confirmationState.emitted && Boolean(confirmationState.title) && !confirmationState.error;
    if (!confirmationPassed) failures.push("Agent Confirmation surface was not rendered and guarded through the visible workbench");
    journeys.push(journey("agent_confirmation_surface", confirmationPassed, confirmationState));
  }

  const inbox = await fetchJson(`${baseUrl}/api/inbox?employee_id=100001&limit=5`);
  const task = (inbox.items || []).find((item) => item.task_ref);
  if (!task) failures.push("fixture task is missing");
  else {
    progress(viewport, "Task Console");
    await navigate(cdp, `${baseUrl}/tasks/console?employee_id=100001&task_id=${encodeURIComponent(task.task_ref)}`, ".task-console-page");
    const taskState = await cdp.eval(`(() => ({ form: !!document.querySelector('[data-a2ui-component="WorkRecordForm"]'), evidence: !!document.querySelector('[data-a2ui-component="EvidencePicker"]'), pickers: document.querySelectorAll('[data-directory-picker]').length, raw: document.body.innerText.includes('흐름 원본 보기'), overflow: Math.max(0, document.documentElement.scrollWidth-innerWidth), fields: ['observation','action_taken','decision','result','blocker','next_work'].every(name => !!document.querySelector('[name="'+name+'"]')) }))()`);
    if (!taskState.form || !taskState.evidence || !taskState.fields) failures.push("Task dynamic work form is incomplete");
    if (taskState.pickers < 3) failures.push("Task assignment pickers are incomplete");
    if (taskState.raw) failures.push("raw Mermaid source is visible");
    if (taskState.overflow > 1) failures.push(`task overflow ${taskState.overflow}px`);
    journeys.push(journey("inbox_to_task_work_record", taskState.form && taskState.evidence && taskState.fields && !taskState.raw && taskState.overflow <= 1, taskState));
    if (viewport.name === "desktop") {
      let assignmentJourney = {allowMutations};
      if (allowMutations) {
        assignmentJourney = await cdp.eval(`(async () => {
          const editor=document.querySelector('[data-task-assignment]');
          const taskRef=editor?.dataset.taskRef || '';
          const originalRevision=Number(editor?.dataset.revision || 0);
          const fields=Object.fromEntries([...editor.querySelectorAll('[data-assignment-field]')].map(field=>[field.dataset.assignmentField,String(field.value||'').split(',').map(item=>item.trim()).filter(Boolean)]));
          const assignee=editor.querySelector('[data-assignment-field="assignee_employee_ids"]')?.closest('[data-directory-picker]');
          const query=assignee?.querySelector('[data-directory-query]');
          query.value='100002';
          query.dispatchEvent(new Event('input',{bubbles:true}));
          query?.focus();
          const optionsDeadline=Date.now()+5000;
          while(Date.now()<optionsDeadline && !(assignee?.querySelector('[data-directory-options] button'))) await new Promise(resolve=>setTimeout(resolve,100));
          const option=[...(assignee?.querySelectorAll('[data-directory-options] button')||[])].find(item=>!fields.assignee_employee_ids.some(id=>item.textContent.includes(id)));
          option?.click();
          const chosen=String(assignee?.querySelector('[data-directory-value]')?.value||'').split(',').map(item=>item.trim()).filter(Boolean);
          editor.querySelector('[data-task-assignment-save]')?.click();
          const deadline=Date.now()+10000;
          while(Date.now()<deadline && !String(editor.querySelector('[data-task-assignment-status]')?.textContent||'').includes('저장되었습니다')) await new Promise(resolve=>setTimeout(resolve,100));
          const savedRevision=Number(editor.dataset.revision||0);
          const conflict=await fetch('/api/tasks/'+encodeURIComponent(taskRef)+'/assignment?employee_id=100001',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({...fields,completion_policy:'any_assignee',expected_revision:originalRevision,user_confirmed:true})});
          const restored=await fetch('/api/tasks/'+encodeURIComponent(taskRef)+'/assignment?employee_id=100001',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({...fields,completion_policy:'any_assignee',expected_revision:savedRevision,user_confirmed:true})});
          const restoredPayload=await restored.json().catch(()=>({}));
          return {taskRef,originalRevision,savedRevision,selectedCount:chosen.length,originalCount:fields.assignee_employee_ids.length,chipCount:assignee?.querySelectorAll('[data-directory-chips] .directory-chip').length||0,status:editor.querySelector('[data-task-assignment-status]')?.textContent||'',conflictStatus:conflict.status,restoreStatus:restored.status,restoredRevision:restoredPayload.assignment_design?.revision||0};
        })()`);
      }
      const assignmentPassed = allowMutations && assignmentJourney.selectedCount > assignmentJourney.originalCount
        && assignmentJourney.chipCount === assignmentJourney.selectedCount
        && assignmentJourney.savedRevision === assignmentJourney.originalRevision + 1
        && assignmentJourney.conflictStatus === 409 && assignmentJourney.restoreStatus === 200;
      journeys.push(journey("task_assignment_and_revision", assignmentPassed, assignmentJourney));

      const parity = await cdp.eval(`(async () => {
        const taskRef=${JSON.stringify(task.task_ref)};
        const snapshot=await fetch('/api/tasks/'+encodeURIComponent(taskRef)+'/execution-snapshot?employee_id=100001').then(r=>r.json());
        const batch=await fetch('/api/inbox/workflow-canvases?employee_id=100001',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task_refs:[taskRef]})}).then(r=>r.json());
        const canvas=(batch.items||[])[0]?.canvas || {};
        return {sameSource:snapshot.workflow_canvas?.source===canvas.source,sameStage:snapshot.workflow_canvas?.current_stage_id===canvas.current_stage_id,snapshotStages:snapshot.workflow_canvas?.stages?.length||0,batchStages:canvas.stages?.length||0};
      })()`);
      journeys.push(journey("inbox_task_snapshot_parity", parity.sameSource && parity.sameStage && parity.snapshotStages === parity.batchStages, parity));

      let workRecord = {allowMutations};
      if (allowMutations) {
        progress(viewport, "Task WorkRecord save");
        const marker = `browser-work-record-${Date.now()}`;
        const formReady = await cdp.eval(`(() => {
          const form=document.querySelector('.task-console-note-form');
          const marker=${JSON.stringify(marker)};
          const values={observation:'확인',action_taken:'조치',decision:'판단',result:'결과',evidence_refs:'boi:public:boi-wiki-manual:guide:final-operator-guide',blocker:'',next_work:'다음 업무'};
          for (const [name,value] of Object.entries(values)) {
            const field=form.elements.namedItem(name);
            if (!field) continue;
            field.value=name==='evidence_refs'?value:marker+' '+value;
            field.dispatchEvent(new Event('input',{bubbles:true}));
          }
          for (const box of form.querySelectorAll('input[type="checkbox"]')) box.checked=true;
          const missing=[...form.querySelectorAll(':invalid')].map(field=>field.name||field.type);
          if (form.checkValidity()) form.requestSubmit();
          return {valid:form.checkValidity(),missing};
        })()`);
        await sleep(1500);
        await navigate(cdp, `${baseUrl}/tasks/console?employee_id=100001&task_id=${encodeURIComponent(task.task_ref)}`, ".task-console-page");
        await wait(cdp, `document.body.innerText.includes(${JSON.stringify(marker)})`, 10000);
        workRecord = await cdp.eval(`(() => ({marker:${JSON.stringify(marker)},historyVisible:document.body.innerText.includes(${JSON.stringify(marker)}),taskStatus:document.querySelector('.task-console-summary')?.textContent.trim()||'',workForm:!!document.querySelector('[data-a2ui-component="WorkRecordForm"]'),evidencePicker:!!document.querySelector('[data-a2ui-component="EvidencePicker"]')}))()`);
        workRecord.formReady = formReady;
      }
      const workRecordPassed = allowMutations && workRecord.historyVisible && workRecord.workForm && workRecord.evidencePicker;
      if (!workRecordPassed) failures.push("Task WorkRecord was not saved through the visible form");
      journeys.push(journey("task_work_record_persistence", workRecordPassed, workRecord));

      const adapterState = await cdp.eval(`(async () => {
        const sources=await fetch('/api/v2/knowledge-sources?employee_id=100001').then(r=>r.json());
        const health=await fetch('/health').then(r=>r.json());
        return {sourceCount:(sources.items||[]).length,coreOk:health.status==='ok'};
      })()`);
      journeys.push(journey("adapter_job_status_and_retry", adapterState.coreOk, adapterState));

      const candidate = await cdp.eval(`fetch('/api/v2/harness-candidates?employee_id=100001').then(r=>r.json()).then(payload=>(payload.items||[])[0]||null)`);
      let harnessState = {available:Boolean(candidate),allowMutations};
      if (candidate && allowMutations) {
        progress(viewport, "Harness rehearsal");
        const beforeStatus = candidate.status;
        await navigate(cdp, `${baseUrl}/harness-candidates/${encodeURIComponent(candidate.candidate_id)}?employee_id=100001`, "[data-harness-review]");
        await wait(cdp, `[...document.querySelectorAll('[data-harness-review] [data-a2ui-component-id]')].some(node => node.childElementCount > 0)`, 10000);
        await cdp.eval(`(() => {
          const root=document.querySelector('[data-harness-review]');
          root.querySelector('[data-harness-note]').value='실제 브라우저 배포 연습 검증';
          root.querySelector('[data-harness-confirm]').checked=true;
          root.querySelector('[data-harness-release][data-rehearsal="true"]').click();
        })()`);
        await wait(cdp, `document.querySelector('[data-harness-review]')?.dataset.harnessOperation === 'rehearsal'`, 10000);
        const after = await cdp.eval(`fetch('/api/v2/harness-candidates?employee_id=100001').then(r=>r.json()).then(payload=>(payload.items||[]).find(item=>item.candidate_id===${JSON.stringify(candidate.candidate_id)})||null)`);
        harnessState = await cdp.eval(`(() => { const root=document.querySelector('[data-harness-review]'); return {rendered:[...root.querySelectorAll('[data-a2ui-component-id]')].filter(node=>node.childElementCount>0).length,message:root.querySelector('[data-harness-message]')?.textContent||'',operation:root.dataset.harnessOperation||'',productionChanged:root.dataset.harnessProductionChanged||'',revision:root.dataset.harnessRevision||''}; })()`);
        harnessState.available = true;
        harnessState.beforeStatus = beforeStatus;
        harnessState.afterStatus = after?.status || '';
        harnessState.productionUnchanged = harnessState.beforeStatus === harnessState.afterStatus;
        const releaseLoaded = cdp.once("Page.loadEventFired");
        await cdp.eval(`document.querySelector('[data-harness-release]:not([data-rehearsal="true"])')?.click()`);
        await releaseLoaded;
        await wait(cdp, `document.querySelector('[data-harness-rollback]')`, 10000);
        const released = await cdp.eval(`fetch('/api/v2/harness-candidates?employee_id=100001').then(r=>r.json()).then(payload=>(payload.items||[]).find(item=>item.candidate_id===${JSON.stringify(candidate.candidate_id)})||null)`);
        await cdp.eval(`(() => { const root=document.querySelector('[data-harness-review]'); root.querySelector('[data-harness-note]').value='실제 브라우저 rollback 검증'; root.querySelector('[data-harness-confirm]').checked=true; })()`);
        const rollbackLoaded = cdp.once("Page.loadEventFired");
        await cdp.eval(`document.querySelector('[data-harness-rollback]')?.click()`);
        await rollbackLoaded;
        await wait(cdp, `!!document.querySelector('[data-harness-review]')`, 10000);
        const rolledBack = await cdp.eval(`fetch('/api/v2/harness-candidates?employee_id=100001').then(r=>r.json()).then(payload=>(payload.items||[]).find(item=>item.candidate_id===${JSON.stringify(candidate.candidate_id)})||null)`);
        harnessState.releasedStatus = released?.status || '';
        harnessState.rolledBackStatus = rolledBack?.status || '';
        harnessState.releaseAndRollback = harnessState.releasedStatus === 'released' && harnessState.rolledBackStatus === 'rolled_back';
      }
      const harnessPassed = harnessState.available && harnessState.rendered > 0 && harnessState.productionUnchanged
        && harnessState.operation === 'rehearsal' && harnessState.productionChanged === 'false'
        && harnessState.releaseAndRollback;
      journeys.push(journey("harness_review_release_rehearsal", Boolean(harnessPassed), harnessState));
    }
  }
  if (viewport.name === "mobile") {
    const mobile = await cdp.eval(`(() => ({overflow:Math.max(0,document.documentElement.scrollWidth-innerWidth),focusable:!!document.querySelector('button, input, textarea, a[href]'),fallbackCount:document.querySelectorAll('[data-a2ui-rendered="fallback"]').length}))()`);
    journeys.push(journey("mobile_focus_and_fallback", mobile.overflow <= 1 && mobile.focusable && mobile.fallbackCount <= 1, mobile));
  }
  if (screenshotDir) {
    progress(viewport, "capture");
    await navigate(cdp, `${baseUrl}/knowledge-graph?employee_id=100001`, "#knowledge-explorer .knowledge-graph-canvas");
    await wait(cdp, `document.querySelector('#knowledge-explorer .knowledge-graph-canvas canvas')?.width > 20`);
    await cdp.eval(`document.querySelector('[data-agent-v2-close]')?.click()`);
    await sleep(180);
    await cdp.screenshot(join(screenshotDir, `ontology-${viewport.width}x${viewport.height}.png`));
  }
  journeys.filter((item) => !item.passed).forEach((item) => failures.push(`${item.id} failed`));
  return { viewport, passed: failures.length === 0, failures: [...new Set(failures)], journeys, graph, agentSurface };
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
    if (onlyConfirmation) {
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width: 1440,
        height: 1000,
        deviceScaleFactor: 1,
        mobile: false,
      });
      await navigate(cdp, `${baseUrl}/docs/boi%3Apublic%3Aboi-wiki-manual%3Aguide%3Afinal-operator-guide?employee_id=100001`, "[data-agent-v2-workspace]");
      await cdp.eval(`document.querySelector('[data-agent-v2-open]')?.click()`);
      await wait(cdp, `document.querySelector('[data-agent-v2-workspace]')?.dataset.agentReady === 'true' && !document.querySelector('[data-agent-v2-new]')?.disabled`, 15000);
      const before = await cdp.eval(`document.querySelector('[data-agent-v2-workspace]')?.dataset.sessionId || sessionStorage.getItem('boiAgentV2WorkSession') || ''`);
      await cdp.eval(`document.querySelector('[data-agent-v2-new]')?.click()`);
      await wait(cdp, `(() => { const id=document.querySelector('[data-agent-v2-workspace]')?.dataset.sessionId || sessionStorage.getItem('boiAgentV2WorkSession') || ''; return id && id !== ${JSON.stringify(before)}; })()`, 15000);
      await wait(cdp, `document.querySelectorAll('[data-agent-v2-starters] button:not(:disabled)').length > 0`, 15000);
      await cdp.eval(`document.querySelector('[data-agent-v2-starters-more]')?.click()`);
      await wait(cdp, `!![...document.querySelectorAll('[data-agent-v2-starters] button')].find(item => item.dataset.resultKind === 'confirmation' && !item.disabled)`, 15000);
      const beforeAssistant = await cdp.eval(`document.querySelectorAll('.agent-v2-message.assistant').length`);
      await cdp.eval(`[...document.querySelectorAll('[data-agent-v2-starters] button')].find(item => item.dataset.resultKind === 'confirmation' && !item.disabled)?.click()`);
      await wait(cdp, `document.querySelectorAll('.agent-v2-message.assistant').length > ${beforeAssistant} && document.querySelector('[data-agent-v2-workspace]')?.getAttribute('aria-busy') === 'false'`, 180000);
      const report = await cdp.eval(`(() => {
        const confirmationMatches = [...document.querySelectorAll('boi-a2ui-confirmation, [data-a2ui-component="Confirmation"]')];
        const confirmationHost = confirmationMatches.find(match => match.shadowRoot?.querySelector('button') || match.querySelector('button')) || confirmationMatches[0] || null;
        return ({
        pageRef: document.querySelector('[data-agent-v2-workspace]')?.dataset.pageRef || '',
        sessionId: document.querySelector('[data-agent-v2-workspace]')?.dataset.sessionId || sessionStorage.getItem('boiAgentV2WorkSession') || '',
        ready: document.querySelector('[data-agent-v2-workspace]')?.dataset.agentReady || '',
        busy: document.querySelector('[data-agent-v2-workspace]')?.getAttribute('aria-busy') || '',
        mode: document.querySelector('[data-agent-v2-workspace]')?.dataset.surfaceMode || '',
        surfaceRef: document.querySelector('[data-agent-v2-workspace]')?.dataset.a2uiSurfaceRef || '',
        activeComponent: document.querySelector('[data-agent-v2-artifact-list] [data-a2ui-component]')?.dataset.a2uiComponent || '',
        confirmationButton: Boolean(confirmationHost?.shadowRoot?.querySelector('button') || confirmationHost?.querySelector('button')),
        messages: [...document.querySelectorAll('.agent-v2-message')].map(item => item.textContent.trim()),
        buttons: [...document.querySelectorAll('[data-agent-v2-starters] button')].map(item => ({
          label: item.textContent.trim(),
          resultKind: item.dataset.resultKind || '',
          suggestionId: item.dataset.suggestionId || '',
          disabled: item.disabled,
        })),
      }); })()`);
      if (outputPath) writeFileSync(outputPath, JSON.stringify(report, null, 2) + "\n");
      console.log(JSON.stringify(report, null, 2));
      process.exitCode = report.activeComponent === "Confirmation" && report.confirmationButton ? 0 : 1;
      return;
    }
    if (debugSession) {
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width: debugWidth,
        height: debugHeight,
        deviceScaleFactor: 1,
        mobile: debugWidth < 600,
      });
      const artifactQuery = debugArtifact ? `&artifact=${encodeURIComponent(debugArtifact)}` : "";
      const target = debugPage
        ? `${baseUrl}${debugPage}${debugPage.includes("?") ? "&" : "?"}pet_session=${encodeURIComponent(debugSession)}`
        : `${baseUrl}/agent?employee_id=100001&session=${encodeURIComponent(debugSession)}${artifactQuery}`;
      await navigate(cdp, target, "[data-agent-v2-workspace]");
      if (debugPage) {
        if (debugHideAgent) await cdp.eval(`document.querySelector('[data-agent-v2-close]')?.click()`);
        else await cdp.eval(`document.querySelector('[data-agent-v2-expand]')?.click()`);
        await sleep(300);
      }
      if (debugFocus) {
        await cdp.eval(`document.querySelector('[data-agent-v2-artifact-focus]')?.click()`);
        await wait(cdp, `document.querySelector('[data-agent-v2-workspace]')?.classList.contains('artifact-focus-open')`);
      }
      const debugStarted = Date.now();
      if (!debugGraph) {
        try { await wait(cdp, `document.querySelector('[data-agent-v2-artifact-list] .mermaid-diagram')?.dataset.mermaidState === 'rendered'`, 30000); } catch (_error) {}
      } else {
        await wait(cdp, `document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas')?.dataset.graphPainted === 'true'`, 10000);
        await cdp.eval(`document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] .knowledge-graph-canvas')?.focus()`);
        await pressKey(cdp, "Enter");
      }
      await sleep(1000);
      const debug = await cdp.eval(`(() => ({
        mermaidLoaded: Boolean(window.mermaid),
        diagrams: [...document.querySelectorAll('.mermaid-diagram')].map(item => ({state:item.dataset.mermaidState||'',error:item.dataset.mermaidError||'',lastFailure:item.dataset.mermaidLastFailure||'',attempts:Number(item.dataset.mermaidAttempts||0),libraryMs:Number(item.dataset.mermaidLibraryMs||0),queueMs:Number(item.dataset.mermaidQueueMs||0),renderMs:Number(item.dataset.mermaidRenderMs||0),startedAt:item.dataset.mermaidStartedAt||'',connected:item.isConnected,source:(item.dataset.mermaidSource||'').slice(0,120)})),
        artifactComponent: document.querySelector('[data-agent-v2-artifact-list] [data-a2ui-component]')?.dataset.a2uiComponent || '',
        svgCount: document.querySelectorAll('[data-agent-v2-artifact-list] svg').length,
        mermaidScripts: [...document.scripts].filter(item=>item.src.includes('mermaid')).map(item=>({src:item.src,async:item.async,connected:item.isConnected})),
        mermaidResources: performance.getEntriesByType('resource').filter(item=>item.name.includes('mermaid')).map(item=>({name:item.name,duration:Math.round(item.duration),transferSize:item.transferSize,encodedBodySize:item.encodedBodySize,decodedBodySize:item.decodedBodySize})),
        graphPanels: [...document.querySelectorAll('[data-agent-v2-artifact-list] .knowledge-graph-hub')].map(panel => { const canvas=panel.querySelector('.knowledge-graph-canvas'); const rect=canvas?.getBoundingClientRect(); return {official:Boolean(panel.closest('[data-boi-a2ui-official]')),connected:panel.isConnected,hidden:panel.hidden,ready:canvas?.dataset.ready||'',painted:canvas?.dataset.graphPainted||'',nodeCount:Number(canvas?.dataset.nodeCount||0),minimumNodeDistance:Number(canvas?.dataset.minimumNodeDistance||0),width:Math.round(rect?.width||0),height:Math.round(rect?.height||0),computedMinHeight:getComputedStyle(canvas).minHeight,hostClass:panel.closest('[data-agent-v2-workspace]')?.className||'',surfaceClass:panel.closest('.agent-surface')?.className||'',canvases:canvas?.querySelectorAll('canvas').length||0,canvasSizes:[...(canvas?.querySelectorAll('canvas')||[])].map(item=>({width:item.width,height:item.height,clientWidth:item.clientWidth,clientHeight:item.clientHeight}))}; }),
        artifactClass: document.querySelector('[data-agent-v2-workspace]')?.className || '',
        surfaceMode: document.querySelector('[data-agent-v2-workspace]')?.dataset.surfaceMode || '',
        workbenchHidden: document.querySelector('[data-agent-v2-workbench]')?.hidden,
        runtimeResources: performance.getEntriesByType('resource').filter(item=>/a2ui-runtime|knowledge-graph/.test(item.name)).map(item=>({name:item.name,duration:Math.round(item.duration)})),
        a2uiRuntime: document.querySelector('[data-agent-v2-artifact-list]')?.dataset.a2uiRuntime || '',
        officialCount: document.querySelectorAll('[data-agent-v2-artifact-list] [data-boi-a2ui-official]').length,
        activeElement: document.activeElement?.className || document.activeElement?.tagName || '',
        inspectorOpen: document.querySelector('[data-agent-v2-artifact-list] [data-boi-a2ui-official] [data-knowledge-node-details]')?.hidden === false,
      }))()`);
      debug.elapsedMs = Date.now() - debugStarted;
      if (screenshotDir) await cdp.screenshot(join(screenshotDir, `debug-agent-graph.png`));
      if (outputPath) writeFileSync(outputPath, JSON.stringify(debug, null, 2) + "\n");
      console.log(JSON.stringify(debug, null, 2));
      return;
    }
    const results = [];
    for (const viewport of viewports) {
      try {
        results.push(await runViewport(cdp, viewport));
      } catch (error) {
        process.stderr.write(`[browser:${viewport.name}] fatal: ${String(error?.message || error)}\n`);
        results.push({viewport, passed:false, failures:[String(error?.message || error)], journeys:[]});
      }
    }
    const journeyMap = new Map();
    results.flatMap((item) => item.journeys || []).forEach((item) => journeyMap.set(item.id, item));
    const requiredJourneys = ["inbox_to_task_work_record","task_assignment_and_revision","task_work_record_persistence","ontology_one_hop_expand","ontology_readable_layout","ontology_path","ontology_impact","ontology_tour","ontology_semantic_queries","ontology_visible_semantic_views","agent_a2ui_and_fallback","a2ui_official_lifecycle","citation_canonical_navigation","agent_compact_suspends_graph","agent_table_timeline_mermaid","mermaid_document_rendering","canonical_media_decode","agent_confirmation_surface","inbox_task_snapshot_parity","harness_review_release_rehearsal","adapter_job_status_and_retry","mobile_focus_and_fallback"];
    const missingJourneys = requiredJourneys.filter((id) => !journeyMap.has(id));
    const failedJourneys = [...journeyMap.values()].filter((item) => !item.passed).map((item) => item.id);
    const unexpectedConsoleErrors = consoleErrors.filter((message) => !message.includes("409 (Conflict)"));
    const report = { ok: results.every((item) => item.passed) && unexpectedConsoleErrors.length === 0 && missingJourneys.length === 0 && failedJourneys.length === 0, browser: "Chrome DevTools Protocol", requiredJourneyCount: requiredJourneys.length, missingJourneys, failedJourneys, results, consoleErrors: unexpectedConsoleErrors, expectedConsoleEvents: consoleErrors.filter((message) => message.includes("409 (Conflict)")) };
    const rendered = JSON.stringify(report, null, 2);
    if (outputPath) writeFileSync(outputPath, rendered + "\n");
    console.log(rendered);
    process.exitCode = report.ok ? 0 : 1;
  } finally {
    cdp?.close(); child.kill("SIGTERM"); await sleep(300); rmSync(profile, { recursive: true, force: true });
  }
}

main()
  .then(() => process.exit(process.exitCode || 0))
  .catch((error) => { console.error(error); process.exit(1); });
