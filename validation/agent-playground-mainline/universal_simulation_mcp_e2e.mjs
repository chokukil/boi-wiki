import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { chromium } from "playwright";

const baseUrl = process.env.BOI_BASE_URL || "http://localhost:28005";
const langflowUrl = process.env.LANGFLOW_URL || "http://localhost:7867";
const identityFile =
  process.env.AGENT_HUB_IDENTITY_FILE
  || "/tmp/boi-ap-agent-hub-sso-users.json";
const outputDir =
  process.env.UNIVERSAL_MCP_EVIDENCE_DIR
  || path.resolve(
    "artifacts/agent-playground-handoff",
    `universal-simulation-mcp-${new Date().toISOString().replaceAll(/[:.]/g, "-")}`,
    "browser",
  );
const employeeId = "100002";
const identities = JSON.parse(fs.readFileSync(identityFile, "utf8"));
const loginUsername = String(process.env.BOI_DEMO_USERNAME || employeeId);
const password = String(
  process.env.BOI_DEMO_PASSWORD || identities[employeeId] || "",
);
if (!password) throw new Error("100002 validation or demo password is unavailable");
fs.mkdirSync(outputDir, { recursive: true });
const storageStatePath = path.join(
  os.tmpdir(),
  `boi-universal-simulation-mcp-${process.pid}-${Date.now()}-storage.json`,
);

const unexpected = [];
const ignored = [];
const evidence = {
  ok: false,
  employee_id: employeeId,
  playground_url: `${baseUrl}/playground`,
  representative_flow: {},
  mcp: {},
  docs: [],
  screenshots: [],
  ignored,
  unexpected,
};
const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};

function decodeJsonStrings(value, depth = 0) {
  if (depth > 12) return value;
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (
      (trimmed.startsWith("{") && trimmed.endsWith("}"))
      || (trimmed.startsWith("[") && trimmed.endsWith("]"))
    ) {
      try {
        return decodeJsonStrings(JSON.parse(trimmed), depth + 1);
      } catch {
        return value;
      }
    }
    return value;
  }
  if (Array.isArray(value)) return value.map((item) => decodeJsonStrings(item, depth + 1));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, decodeJsonStrings(item, depth + 1)]),
    );
  }
  return value;
}

function deepValues(value, key, found = []) {
  if (Array.isArray(value)) {
    value.forEach((item) => deepValues(item, key, found));
  } else if (value && typeof value === "object") {
    for (const [candidate, item] of Object.entries(value)) {
      if (candidate === key) found.push(item);
      deepValues(item, key, found);
    }
  }
  return found;
}

function monitor(page, label) {
  page.on("pageerror", (error) => {
    unexpected.push({ label, kind: "pageerror", message: error.message });
  });
  page.on("console", (message) => {
    if (message.type() === "error") {
      if (
        label === "langflow-canvas"
        && message.text().startsWith("Duplicate request:")
      ) {
        ignored.push({
          label,
          kind: "console",
          reason: "unmodified Langflow duplicate-request guard",
          message: message.text(),
        });
        return;
      }
      if (
        label === "langflow-canvas"
        && message.text().includes("403 (Forbidden)")
      ) return;
      unexpected.push({ label, kind: "console", message: message.text() });
    }
  });
  page.on("response", (response) => {
    if (response.status() >= 400 && !response.url().includes("/favicon")) {
      if (
        label === "langflow-canvas"
        && response.status() === 403
        && response.url().includes("/api/v1/auto_login")
      ) return;
      unexpected.push({
        label,
        kind: "http",
        status: response.status(),
        url: response.url().replace(/[?&](?:code|state|session_state)=[^&]+/g, ""),
      });
    }
  });
}

async function login(page) {
  await page.goto(`${baseUrl}/playground`, { waitUntil: "domcontentloaded" });
  const username = page.locator("#username");
  await Promise.race([
    username.waitFor({ state: "visible", timeout: 30_000 }).catch(() => null),
    page.locator("[data-agent-playground]").waitFor({
      state: "visible",
      timeout: 30_000,
    }).catch(() => null),
  ]);
  if (await username.isVisible().catch(() => false)) {
    await username.fill(loginUsername);
    await page.locator("#password").fill(password);
    await page.locator("#kc-login").click();
  }
  await page.waitForURL((url) => url.origin === baseUrl, { timeout: 30_000 });
  await page.locator("[data-agent-playground]").waitFor({
    state: "visible",
    timeout: 30_000,
  });
  const identity = await page.evaluate(async () => {
    const response = await fetch("/api/auth/me");
    return response.json();
  });
  assert(identity.employee_id === employeeId, "OIDC empno did not resolve to 100002");
}

async function state(page) {
  return page.evaluate(async () => {
    const response = await fetch("/api/agent-playground");
    if (!response.ok) throw new Error(`state HTTP ${response.status}`);
    return response.json();
  });
}

async function bootstrapIfNeeded(page) {
  let current = await state(page);
  if (current.onboarding.required) {
    const bootstrap = page.locator("[data-onboarding-bootstrap]");
    await bootstrap.waitFor({ state: "visible", timeout: 30_000 });
    const bootstrapResponse = page.waitForResponse(
      (response) => (
        response.request().method() === "POST"
        && new URL(response.url()).pathname === "/api/agent-playground/bootstrap"
      ),
      { timeout: 360_000 },
    );
    await bootstrap.click();
    const response = await bootstrapResponse;
    assert(response.ok(), `onboarding bootstrap HTTP ${response.status()}`);
    current = await state(page);
  }
  await page.evaluate(async (endpointId) => {
    const response = await fetch("/api/agent-playground/bootstrap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint_id: endpointId }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(`idempotent bootstrap HTTP ${response.status}: ${JSON.stringify(body)}`);
    return body;
  }, current.default_endpoint_id);
  current = await state(page);
  assert(current.onboarding.status === "ready", "Playground onboarding is not ready");
  assert(
    current.recommended_asset.name === "BoI Universal Simulation MCP",
    "representative asset is not the onboarding recommendation",
  );
  const setup = current.endpoint_setups[current.default_endpoint_id];
  assert(setup.recommended_flow.id, "recommended Flow ID is missing");
  assert(
    setup.recommended_smoke.status === "passed",
    "recommended Flow preview smoke did not pass",
  );
  evidence.representative_flow = {
    id: setup.recommended_flow.id,
    name: setup.recommended_flow.name,
    endpoint_name: setup.recommended_flow.endpoint_name,
    version: setup.recommended_flow.version,
    project_id: setup.recommended_flow.project_id,
  };
  return current;
}

async function reopenGuide(page) {
  const reopen = page.locator("[data-reopen-onboarding]");
  if (await reopen.isVisible().catch(() => false)) await reopen.click();
  await page.locator('[data-onboarding-stage="flow"]').waitFor({
    state: "visible",
    timeout: 30_000,
  });
}

async function verifyFirstRun(page) {
  await page.locator("[data-onboarding-sample-run]").click();
  await page.locator("[data-onboarding-first-run-output]").filter({
    hasText: "SIMULATED",
  }).waitFor({ state: "visible", timeout: 360_000 });
  const rawResult = await page.locator("[data-test-output]").innerText();
  const decodedResult = decodeJsonStrings(JSON.parse(rawResult));
  const traces = deepValues(decodedResult, "model_trace").filter(
    (item) => item && typeof item === "object",
  );
  const trace = traces.find((item) => item.real_inference === true);
  assert(trace, "sample result does not contain a real Gemma model trace");
  assert(String(trace.model || "").includes("gemma"), "sample result was not produced by Gemma");
  assert(trace.response_id, "Gemma trace does not contain a response ID");
  assert(Number(trace.latency_ms) > 0, "Gemma trace does not contain latency");
  assert(Number((trace.usage || {}).total_tokens) > 0, "Gemma trace does not contain token usage");
  const sources = deepValues(decodedResult, "source_references").find(Array.isArray) || [];
  const ontology = deepValues(decodedResult, "ontology_relationships").find(Array.isArray) || [];
  const coverage = deepValues(decodedResult, "coverage_report").find(
    (item) => item && typeof item === "object" && !Array.isArray(item),
  );
  assert(sources.length > 0, "sample result does not preserve Wiki source references");
  assert(coverage, "sample result does not contain a coverage report");
  assert(
    ontology.every((item) => !item || typeof item !== "object" || item.provenance),
    "sample result contains an Ontology relationship without provenance",
  );
  evidence.representative_flow.runtime = {
    model: trace.model,
    response_id: trace.response_id,
    latency_ms: trace.latency_ms,
    usage: trace.usage,
    source_reference_count: sources.length,
    ontology_relationship_count: ontology.length,
    coverage_profile: coverage.profile || "",
  };
  await page.evaluate(() => window.scrollTo(0, 0));
  const onboardingShot = path.join(outputDir, "01-onboarding-first-run.png");
  await page.screenshot({ path: onboardingShot, fullPage: true });
  evidence.screenshots.push(onboardingShot);

  await page.locator("[data-onboarding-enable-mcp]").click();
  await page.locator("[data-onboarding-first-run-output]").filter({
    hasText: "MCP 도구 호출 성공",
  }).waitFor({ state: "visible", timeout: 360_000 });
  await page.evaluate(() => window.scrollTo(0, 0));
  const mcpShot = path.join(outputDir, "02-onboarding-mcp-ready.png");
  await page.screenshot({ path: mcpShot, fullPage: true });
  evidence.screenshots.push(mcpShot);
}

async function verifyMcpApi(page, current) {
  const setup = current.endpoint_setups[current.default_endpoint_id];
  const endpointId = current.default_endpoint_id;
  const projectId = setup.project.id;
  const flowId = setup.recommended_flow.id;
  const payload = await page.evaluate(
    async ({ endpointId: endpoint, projectId: project, flowId: flow }) => {
      const response = await fetch(
        `/api/agent-playground/endpoints/${encodeURIComponent(endpoint)}`
        + `/projects/${encodeURIComponent(project)}/mcp`
        + `?flow_id=${encodeURIComponent(flow)}`,
      );
      if (!response.ok) throw new Error(`MCP state HTTP ${response.status}`);
      return response.json();
    },
    { endpointId, projectId, flowId },
  );
  assert(payload.status === "available", "MCP state is not available");
  assert(payload.auth.type === "apikey", "MCP auth is not apikey");
  assert(payload.auth.credential === "${LANGFLOW_API_KEY}", "MCP response leaked or changed credential placeholder");
  assert(
    payload.streamable_url.startsWith("http://localhost:7867/"),
    "browser-facing MCP URL is not the configured external Langflow URL",
  );
  assert(
    !payload.streamable_url.includes("host.docker.internal"),
    "browser-facing MCP URL exposes a container-only hostname",
  );
  assert(payload.tools.length === 1, "representative MCP tool is not exposed exactly once");
  assert(payload.tools[0].tool_name === "boi_universal_simulate", "unexpected MCP tool name");
  assert(!JSON.stringify(payload).includes("boi_pat_"), "MCP response contains a PAT");
  assert(!JSON.stringify(payload).includes("boi_run_"), "MCP response contains a run token");
  const blocked = await page.evaluate(
    async ({ endpointId: endpoint, projectId: project, flowId: flow }) => {
      const response = await fetch(
        `/api/agent-playground/endpoints/${encodeURIComponent(endpoint)}`
        + `/projects/${encodeURIComponent(project)}`
        + `/flows/${encodeURIComponent(flow)}/mcp/test`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question: "결과를 개인 Wiki 초안으로 바로 저장해줘.",
            save_mode: "private_draft",
          }),
        },
      );
      const body = await response.json();
      if (!response.ok) throw new Error(`MCP private-draft policy HTTP ${response.status}: ${JSON.stringify(body)}`);
      return body;
    },
    { endpointId, projectId, flowId },
  );
  assert(blocked.write_allowed === false, "external MCP unexpectedly allowed a Wiki write");
  assert(blocked.write_blocked === true, "external MCP private draft was not blocked by the Flow policy");
  const exactTools = ((blocked.result || {}).tools || []).filter(
    (item) => item.name === "boi_universal_simulate",
  );
  assert(exactTools.length === 1, "MCP list_tools did not return exactly one representative tool");
  assert(
    /Wiki|Ontology|시뮬레이션/i.test(String(exactTools[0].description || "")),
    "MCP tool description does not explain the representative simulation",
  );
  const inputSchema = exactTools[0].input_schema || {};
  assert(inputSchema.type === "object", "MCP tool input schema is not an object");
  assert(
    Object.prototype.hasOwnProperty.call(inputSchema.properties || {}, "input_value"),
    "MCP tool schema does not expose the natural-language input_value",
  );
  const resultText = JSON.stringify(blocked.result || {});
  const contractMatch = resultText.match(
    /BOI_RESULT_JSON_B64(?::|\s)+([A-Za-z0-9+/=]+)/,
  );
  assert(contractMatch, "MCP transport dropped the structured result contract");
  const resultContract = JSON.parse(
    Buffer.from(contractMatch[1], "base64").toString("utf8"),
  );
  assert(
    resultContract.schema_version === "boi.universal-simulation.result.v1",
    "MCP structured result schema changed",
  );
  assert(resultContract.simulation_label === "SIMULATED", "MCP result is not simulated");
  assert(resultContract.real_system_called === false, "MCP result claimed a real system call");
  assert(
    resultContract.model_trace?.real_inference === true
      && /gemma/i.test(String(resultContract.model_trace?.model || "")),
    "MCP result has no actual Gemma trace",
  );
  evidence.mcp = {
    status: payload.status,
    auth_type: payload.auth.type,
    tool_name: payload.tools[0].tool_name,
    transport: payload.client_example.transport,
    streamable_url: payload.streamable_url,
    schema_input: "input_value",
    result_schema_version: resultContract.schema_version,
    model: resultContract.model_trace.model,
    model_response_id: resultContract.model_trace.response_id,
    forced_private_draft: "blocked",
  };
}

async function verifyDocs(page) {
  const refs = [
    "universal-simulation-mcp-quickstart",
    "universal-simulation-mcp-canvas",
    "universal-simulation-mcp-connect",
    "universal-simulation-mcp-agent-hub",
    "universal-simulation-mcp-component",
    "universal-simulation-mcp-permissions",
    "universal-simulation-mcp-troubleshooting",
  ];
  for (const slug of refs) {
    const url = `${baseUrl}/docs/boi:public:boi-wiki-manual:langflow:${slug}`;
    const response = await page.goto(url, { waitUntil: "domcontentloaded" });
    assert(response && response.status() === 200, `${slug} did not return HTTP 200`);
    await page.locator("main").waitFor({ state: "visible", timeout: 20_000 });
    const body = await page.locator("body").innerText();
    assert(!body.includes("host.docker.internal"), `${slug} exposes a container-only hostname`);
    evidence.docs.push({ slug, status: response.status() });
  }
}

async function verifyCanvas(browser, flowId, projectId) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  monitor(page, "langflow-canvas");
  await page.goto(
    `${langflowUrl}/flow/${encodeURIComponent(flowId)}/folder/${encodeURIComponent(projectId)}`,
    { waitUntil: "domcontentloaded" },
  );
  const loginPassword = page.locator('input[type="password"]');
  await Promise.race([
    loginPassword.waitFor({ state: "visible", timeout: 30_000 }).catch(() => null),
    page.getByText("BoI Universal Simulation MCP", { exact: true }).first()
      .waitFor({ state: "visible", timeout: 30_000 }).catch(() => null),
  ]);
  if (await loginPassword.isVisible().catch(() => false)) {
    const username = page.locator('input[name="username"], input[type="text"]').first();
    await username.fill(employeeId);
    await loginPassword.fill("BoiPlayground-100002!ChangeMe");
    await page.locator('button[type="submit"]').click();
    await loginPassword.waitFor({ state: "hidden", timeout: 60_000 });
  }
  await page.getByText("BoI Universal Simulation MCP", { exact: true }).first().waitFor({
    state: "visible",
    timeout: 60_000,
  });
  await page.waitForTimeout(3_000);
  const canvasText = await page.locator("body").innerText();
  assert(!canvasText.includes("Flow needs review"), "Langflow Canvas reports that the Flow needs review");
  assert(
    !canvasText.includes("components need updates"),
    "Langflow Canvas reports outdated components",
  );
  const shot = path.join(outputDir, "03-langflow-canvas.png");
  await page.screenshot({ path: shot, fullPage: true });
  evidence.screenshots.push(shot);
  await page.close();
}

async function verifyMobile(browser) {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    storageState: storageStatePath,
  });
  const page = await context.newPage();
  monitor(page, "mobile");
  await page.goto(`${baseUrl}/playground`, { waitUntil: "domcontentloaded" });
  await page.locator("[data-agent-playground]").waitFor({
    state: "visible",
    timeout: 30_000,
  });
  await page.locator("[data-reopen-onboarding]").waitFor({
    state: "visible",
    timeout: 30_000,
  });
  await page.locator("[data-selected-flow-name]").filter({
    hasText: "BoI Universal Simulation MCP",
  }).waitFor({ state: "visible", timeout: 30_000 });
  await page.evaluate(() => window.scrollTo(0, 0));
  const shot = path.join(outputDir, "04-playground-mobile.png");
  await page.screenshot({ path: shot, fullPage: true });
  evidence.screenshots.push(shot);
  await context.close();
}

const browser = await chromium.launch({ headless: true });
let failure = null;
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  monitor(page, "desktop");
  await login(page);
  const ready = await bootstrapIfNeeded(page);
  await reopenGuide(page);
  await verifyFirstRun(page);
  const refreshed = await state(page);
  await verifyMcpApi(page, refreshed);
  await page.locator("[data-onboarding-finish]").click();
  await page.locator("[data-agent-replace-status]").filter({
    hasText: "Agent 교체 가능",
  }).waitFor({ state: "visible", timeout: 30_000 });
  const html = await page.locator("body").innerText();
  assert(!html.includes("host.docker.internal"), "Playground exposes a container-only hostname");
  assert(html.includes("Agent 교체 가능"), "representative Flow does not expose the Agent replacement state");
  assert(html.includes("Agent Hub 배포 전") || html.includes("배포 Flow 검증 완료"), "deployment readiness state is missing");
  await context.storageState({ path: storageStatePath });
  const setup = refreshed.endpoint_setups[refreshed.default_endpoint_id];
  await verifyCanvas(browser, setup.recommended_flow.id, setup.project.id);
  await verifyDocs(page);
  await verifyMobile(browser);
  assert(unexpected.length === 0, `unexpected browser errors: ${JSON.stringify(unexpected)}`);
  evidence.ok = true;
} catch (error) {
  failure = error;
  evidence.error = error.message;
} finally {
  await browser.close();
  fs.rmSync(storageStatePath, { force: true });
}

fs.writeFileSync(
  path.join(outputDir, "result.json"),
  `${JSON.stringify(evidence, null, 2)}\n`,
);
console.log(JSON.stringify({ ok: evidence.ok, output_dir: outputDir, evidence }, null, 2));
if (failure) throw failure;
