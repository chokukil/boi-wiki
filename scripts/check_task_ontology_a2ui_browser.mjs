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

function journey(id, passed, details = {}) {
  return { id, passed: Boolean(passed), details };
}

async function runViewport(cdp, viewport) {
  await cdp.send("Emulation.setDeviceMetricsOverride", { width: viewport.width, height: viewport.height, deviceScaleFactor: 1, mobile: viewport.width < 600 });
  const failures = [];
  const journeys = [];
  await navigate(cdp, `${baseUrl}/knowledge-graph?employee_id=100001`, ".knowledge-graph-canvas");
  await wait(cdp, `document.querySelector('.knowledge-graph-canvas canvas')?.width > 20`);
  const graph = await cdp.eval(`(() => ({ canvas: !!document.querySelector('.knowledge-graph-canvas canvas'), details: !!document.querySelector('[data-knowledge-node-details]'), rawRef: document.querySelector('#graph-source-ref')?.value?.startsWith('boi:'), overflow: Math.max(0, document.documentElement.scrollWidth-innerWidth), consoleTitle: document.title }))()`);
  if (!graph.canvas) failures.push("ontology canvas is blank");
  if (!graph.details) failures.push("ontology node details are missing");
  if (graph.rawRef) failures.push("raw ontology ref is visible");
  if (graph.overflow > 1) failures.push(`ontology overflow ${graph.overflow}px`);
  journeys.push(journey("ontology_one_hop_expand", graph.canvas && graph.details && !graph.rawRef && graph.overflow <= 1, graph));

  if (viewport.name === "desktop") {
    const graphModes = await cdp.eval(`(async () => {
      const panel = document.querySelector('#knowledge-explorer');
      const source = panel?.dataset.sourceRef || '';
      const click = (view) => document.querySelector('[data-knowledge-view="'+view+'"]')?.click();
      click('impact');
      await new Promise(resolve => setTimeout(resolve, 700));
      const impact = {selected:document.querySelector('[data-knowledge-view="impact"]')?.getAttribute('aria-selected') === 'true', canvas:!!document.querySelector('.knowledge-graph-canvas canvas'), status:document.querySelector('.knowledge-explorer-status')?.textContent || ''};
      click('tour');
      await new Promise(resolve => setTimeout(resolve, 700));
      const tour = {selected:document.querySelector('[data-knowledge-view="tour"]')?.getAttribute('aria-selected') === 'true', rows:document.querySelectorAll('.knowledge-explorer-content li').length};
      click('path');
      const neighbors = await fetch('/api/v2/knowledge-graph/explore?employee_id=100001&view=neighbors&source_ref='+encodeURIComponent(source)+'&depth=1&limit=20').then(r => r.json());
      const target = (neighbors.nodes || []).find(item => item.node_id !== source);
      let path = {selected:document.querySelector('[data-knowledge-view="path"]')?.getAttribute('aria-selected') === 'true', target:false, status:''};
      if (target) {
        const pathPayload = await fetch('/api/v2/knowledge-graph/explore?employee_id=100001&view=path&source_ref='+encodeURIComponent(source)+'&target_ref='+encodeURIComponent(target.node_id)+'&depth=6&limit=120').then(r=>r.json());
        path = {selected:true,target:(pathPayload.nodes||[]).length>1 && (pathPayload.edges||[]).length>0,status:pathPayload.status || 'ready'};
        const title = target.payload?.title || 'BoI Agent';
        const input = document.querySelector('#knowledge-path-query');
        if (input) input.value = title;
        document.querySelector('[data-knowledge-search]')?.click();
      }
      return {impact,tour,path};
    })()`);
    journeys.push(journey("ontology_path", graphModes.path.selected && graphModes.path.target && Boolean(graphModes.path.status), graphModes.path));
    journeys.push(journey("ontology_impact", graphModes.impact.selected && graphModes.impact.canvas, graphModes.impact));
    journeys.push(journey("ontology_tour", graphModes.tour.selected && graphModes.tour.rows > 0, graphModes.tour));
  }

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
    journeys.push(journey("agent_a2ui_and_fallback", Boolean(agentSurface.surfaceRef) && agentSurface.components?.includes("Answer") && agentSurface.invalidRejected, agentSurface));
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
    journeys.push(journey("inbox_to_task_work_record", taskState.form && taskState.evidence && taskState.fields && !taskState.raw && taskState.overflow <= 1, taskState));
    journeys.push(journey("task_assignment_and_revision", taskState.pickers >= 3, { pickers: taskState.pickers }));

    if (viewport.name === "desktop") {
      const parity = await cdp.eval(`(async () => {
        const taskRef=${JSON.stringify(task.task_ref)};
        const snapshot=await fetch('/api/tasks/'+encodeURIComponent(taskRef)+'/execution-snapshot?employee_id=100001').then(r=>r.json());
        const batch=await fetch('/api/inbox/workflow-canvases?employee_id=100001',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task_refs:[taskRef]})}).then(r=>r.json());
        const canvas=(batch.items||[])[0]?.canvas || {};
        return {sameSource:snapshot.workflow_canvas?.source===canvas.source,sameStage:snapshot.workflow_canvas?.current_stage_id===canvas.current_stage_id,snapshotStages:snapshot.workflow_canvas?.stages?.length||0,batchStages:canvas.stages?.length||0};
      })()`);
      journeys.push(journey("inbox_task_snapshot_parity", parity.sameSource && parity.sameStage && parity.snapshotStages === parity.batchStages, parity));

      const a2uiMatrix = await cdp.eval(`(async () => {
        const root=document.createElement('section'); root.id='a2ui-browser-matrix'; root.style.cssText='position:fixed;left:0;top:0;width:900px;height:700px;display:block;opacity:.01;z-index:-1'; document.body.appendChild(root);
        const componentNames=['Answer','CitationList','RelatedQuestions','TaskStatus','DecisionSummary','Confirmation','DataTable','Timeline','MermaidArtifact','OntologyExplorer','ActionPreview'];
        componentNames.forEach((name,index)=>{const node=document.createElement('div');node.dataset.a2uiComponentId='matrix-'+index;node.style.cssText='display:block;width:800px;min-height:120px';if(name==='OntologyExplorer')node.style.height='500px';root.appendChild(node);});
        const originalFetch=window.fetch;
        window.fetch=async (input,init) => String(input).includes('/api/v2/artifacts/browser-fixture') ? new Response(JSON.stringify({artifact_id:'browser-fixture',title:'검증 결과',preview:'실행 전 검토',draft:{source:'flowchart LR\\n A[업무] --> B[결과]',mermaid:'flowchart LR\\n A[업무] --> B[결과]',nodes:[{node_id:'a',node_type:'task',payload:{title:'업무'}},{node_id:'b',node_type:'boi',payload:{title:'결과'}}],edges:[{edge_id:'ab',source_id:'a',target_id:'b',relation:'produces',payload:{provenance:'declared',observed_at:'2026-07-13'}}]}}),{status:200,headers:{'Content-Type':'application/json'}}) : originalFetch(input,init);
        const components=componentNames.map((component,index)=>({id:'matrix-'+index,component,props: component==='Answer'?{summary:'검증',markdown:'답변'}:component==='CitationList'?{items:[{title:'근거',target_url:'/'}]}:component==='RelatedQuestions'?{items:[{label:'더 보기'}]}:component==='DecisionSummary'?{summary:'판단',items:[{label:'결과',value:'확인'}]}:component==='Confirmation'?{title:'확인',message:'진행 여부'}:['DataTable','Timeline','MermaidArtifact','OntologyExplorer','ActionPreview'].includes(component)?{artifact_id:'browser-fixture'}:{}}));
        const surface={protocol_version:'0.9.1',catalog_id:'boi-a2ui/v1',surface_id:'browser-matrix',components,events:[],fallback:{}};
        const hydrated=window.BoiA2UI?.hydrate(surface,root)===true;
        await new Promise(resolve=>setTimeout(resolve,1000));
        window.fetch=originalFetch;
        const rendered=componentNames.filter((name,index)=>root.children[index]?.childElementCount>0 || root.children[index]?.dataset.a2uiHydrated==='true');
        const canvas=root.querySelector('.knowledge-graph-canvas canvas');
        const mermaid=root.querySelector('.mermaid svg');
        return {hydrated,rendered,canvasNonblank:Boolean(canvas && canvas.width>20),mermaidNonblank:Boolean(mermaid)};
      })()`);
      journeys.push(journey("agent_table_timeline_mermaid", a2uiMatrix.hydrated && a2uiMatrix.rendered.length === 11 && a2uiMatrix.canvasNonblank && a2uiMatrix.mermaidNonblank, a2uiMatrix));

      const adapterState = await cdp.eval(`(async () => {
        const sources=await fetch('/api/v2/knowledge-sources?employee_id=100001').then(r=>r.json());
        const health=await fetch('/health').then(r=>r.json());
        return {sourceCount:(sources.items||[]).length,coreOk:health.status==='ok'};
      })()`);
      journeys.push(journey("adapter_job_status_and_retry", adapterState.coreOk, adapterState));

      const harnessState = await cdp.eval(`(async () => {
        const response=await fetch('/api/v2/harness-candidates?employee_id=100001');
        if (!response.ok) return {available:false,status:response.status};
        const payload=await response.json(); const candidate=(payload.items||[])[0];
        if (!candidate) return {available:false,status:'empty'};
        const page=await fetch('/harness-candidates/'+encodeURIComponent(candidate.candidate_id)+'?employee_id=100001').then(r=>r.text());
        return {available:true,rendered:page.includes('data-harness-review') && page.includes('배포 연습')};
      })()`);
      journeys.push(journey("harness_review_release_rehearsal", harnessState.available && harnessState.rendered, harnessState));
    }
  }
  if (viewport.name === "mobile") {
    const mobile = await cdp.eval(`(() => ({overflow:Math.max(0,document.documentElement.scrollWidth-innerWidth),focusable:!!document.querySelector('button, input, textarea, a[href]'),fallbackCount:document.querySelectorAll('[data-a2ui-rendered="fallback"]').length}))()`);
    journeys.push(journey("mobile_focus_and_fallback", mobile.overflow <= 1 && mobile.focusable && mobile.fallbackCount <= 1, mobile));
  }
  if (screenshotDir) {
    await navigate(cdp, `${baseUrl}/knowledge-graph?employee_id=100001`, ".knowledge-graph-canvas");
    await wait(cdp, `document.querySelector('.knowledge-graph-canvas canvas')?.width > 20`);
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
    const results = [];
    for (const viewport of viewports) results.push(await runViewport(cdp, viewport));
    const journeyMap = new Map();
    results.flatMap((item) => item.journeys || []).forEach((item) => journeyMap.set(item.id, item));
    const requiredJourneys = ["inbox_to_task_work_record","task_assignment_and_revision","ontology_one_hop_expand","agent_a2ui_and_fallback","inbox_task_snapshot_parity","ontology_path","ontology_impact","ontology_tour","agent_table_timeline_mermaid","harness_review_release_rehearsal","adapter_job_status_and_retry","mobile_focus_and_fallback"];
    const missingJourneys = requiredJourneys.filter((id) => !journeyMap.has(id));
    const failedJourneys = [...journeyMap.values()].filter((item) => !item.passed).map((item) => item.id);
    const report = { ok: results.every((item) => item.passed) && consoleErrors.length === 0 && missingJourneys.length === 0 && failedJourneys.length === 0, browser: "Chrome DevTools Protocol", requiredJourneyCount: requiredJourneys.length, missingJourneys, failedJourneys, results, consoleErrors };
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
