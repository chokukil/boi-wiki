#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";

const required = (name, fallback = "") => {
  const value = String(process.env[name] || fallback);
  if (!value) throw new Error(`${name} is required`);
  return value;
};
const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};
const safeUrl = (raw) => {
  const url = new URL(raw);
  return `${url.origin}${url.pathname}`;
};
const now = new Date().toISOString();
const runId = now.replace(/[-:TZ.]/g, "").slice(0, 14);
const config = {
  username: required("BOI_DEMO_USERNAME", "boi-dev"),
  password: required("BOI_DEMO_PASSWORD"),
  employeeId: required("BOI_DEMO_EMPLOYEE_ID", "100002"),
  displayName: required("BOI_DEMO_DISPLAY_NAME", "BoI Demo"),
  boiUrl: required("BOI_BASE_URL", "http://localhost:28005"),
  langflowUrl: required("LANGFLOW_BROWSER_URL", "http://localhost:17867"),
  agentHubUrl: required(
    "AGENT_HUB_URL",
    "http://localhost:18080/AgentHub.html",
  ),
  timeoutMs: Number(process.env.BOI_DEMO_E2E_TIMEOUT_MS || 360_000),
  evidenceDir: path.resolve(
    process.env.BOI_DEMO_E2E_EVIDENCE_DIR
      || `artifacts/agent-playground-demo/${runId}`,
  ),
};

const evidence = {
  schema: "boi.agent-playground.demo-account-e2e.v1",
  generated_at: now,
  username: config.username,
  employee_id: config.employeeId,
  display_name: config.displayName,
  boi: {},
  playground: {},
  langflow: {},
  agent_hub: {},
  action: {},
  logout: {},
  screenshots: [],
  unexpected_http_errors: [],
  ignored_browser_warnings: [],
  console_errors: [],
  page_errors: [],
  secret_scan: {},
  ok: false,
};

await fs.mkdir(config.evidenceDir, { recursive: true });

function monitor(page, scope) {
  page.on("pageerror", (error) => {
    evidence.page_errors.push({
      scope,
      message: String(error.message || error).slice(0, 500),
    });
  });
  page.on("console", (message) => {
    const text = message.text();
    const agentHubBootstrap = (
      page.url().startsWith(new URL(config.agentHubUrl).origin)
      && text.startsWith("Failed to load components: TypeError: Failed to fetch")
    );
    if (
      message.type() === "error"
      && !text.startsWith("Failed to load resource:")
      && !text.startsWith("Duplicate request:")
      && !text.includes("api.github.com/repos/langflow-ai/langflow")
      && !text.includes("Error fetching repository data")
    ) {
      if (agentHubBootstrap) {
        evidence.ignored_browser_warnings.push({
          scope: "agent-hub",
          reason: "immutable Agent Hub optional component lookup during auth bootstrap",
        });
      } else {
        evidence.console_errors.push({ scope, message: text.slice(0, 500) });
      }
    }
  });
  page.on("response", (response) => {
    if (response.status() < 400) return;
    const url = new URL(response.url());
    if (url.pathname.endsWith("/favicon.ico")) return;
    if (
      url.origin === new URL(config.agentHubUrl).origin
      && response.status() === 403
      && ["/api/v1/admin/settings", "/api/v1/users/me"].includes(url.pathname)
    ) {
      evidence.ignored_browser_warnings.push({
        scope: "agent-hub",
        reason: "immutable Agent Hub authorization bootstrap before SSO token storage",
        status: response.status(),
        url: `${url.origin}${url.pathname}`,
      });
      return;
    }
    evidence.unexpected_http_errors.push({
      scope,
      status: response.status(),
      method: response.request().method(),
      url: `${url.origin}${url.pathname}`,
    });
  });
}

async function screenshot(page, filename) {
  const target = path.join(config.evidenceDir, filename);
  await page.screenshot({ path: target, fullPage: true });
  evidence.screenshots.push(filename);
}

async function loginBoi(page) {
  await page.goto(`${config.boiUrl}/playground`, {
    waitUntil: "domcontentloaded",
    timeout: config.timeoutMs,
  });
  assert(
    page.url().includes("/protocol/openid-connect/"),
    "BoI did not redirect to the local OIDC provider",
  );
  const authorization = new URL(page.url());
  assert(
    authorization.searchParams.get("code_challenge_method") === "S256",
    "BoI OIDC login did not use PKCE S256",
  );
  await page.locator("#username").fill(config.username);
  await page.locator("#password").fill(config.password);
  await Promise.all([
    page.waitForURL(
      (url) => url.origin === new URL(config.boiUrl).origin,
      { timeout: config.timeoutMs },
    ),
    page.locator("#kc-login").click(),
  ]);
  await page.locator("[data-agent-playground]").waitFor({
    state: "visible",
    timeout: config.timeoutMs,
  });
  const identity = await page.evaluate(async () => {
    const response = await fetch("/api/auth/me");
    return { status: response.status, body: await response.json() };
  });
  assert(identity.status === 200, `BoI identity returned ${identity.status}`);
  assert(
    identity.body.employee_id === config.employeeId,
    "boi-dev did not resolve to employee 100002",
  );
  assert(
    identity.body.display_name === config.displayName,
    `BoI display name is ${identity.body.display_name}`,
  );
  assert(identity.body.auth_source === "oidc", "BoI did not use OIDC");
  assert(
    (identity.body.roles || []).includes("boi.editor")
      && (identity.body.roles || []).includes("boi.action_invoker"),
    "boi-dev did not receive the existing 100002 developer permissions",
  );
  evidence.boi = {
    employee_id: identity.body.employee_id,
    display_name: identity.body.display_name,
    auth_source: identity.body.auth_source,
    teams: identity.body.teams,
    roles: identity.body.roles,
    pkce_s256: true,
  };
  const guide = await page.evaluate(async () => {
    const response = await fetch(
      "/docs/boi:public:boi-wiki-manual:langflow:agent-playground-onboarding",
    );
    return { status: response.status, html: await response.text() };
  });
  assert(guide.status === 200, `Agent Playground guide returned ${guide.status}`);
  assert(
    guide.html.includes("boi-dev")
      && guide.html.includes("로컬 시연")
      && guide.html.includes("사내·운영 환경에는 배포하지 않는다"),
    "live Wiki guide does not explain the local-only demo login",
  );
  evidence.boi.demo_guide = {
    status: guide.status,
    local_only_notice: true,
  };
  await page.waitForFunction(
    () => {
      const onboarding = document.querySelector("[data-onboarding]");
      const flowRows = document.querySelectorAll("[data-flow-list] button");
      return Boolean(onboarding?.hidden && flowRows.length > 0);
    },
    undefined,
    { timeout: config.timeoutMs },
  );
}

async function discoverPlayground(page) {
  const discovery = await page.evaluate(async () => {
    const stateResponse = await fetch("/api/agent-playground");
    const state = await stateResponse.json();
    const endpointId = String(state.default_endpoint_id || "");
    const setup = state.endpoint_setups?.[endpointId] || {};
    const projectId = String(
      setup.project?.id || state.project?.id || "",
    );
    const flowsResponse = await fetch(
      `/api/agent-playground/endpoints/${encodeURIComponent(endpointId)}`
      + `/projects/${encodeURIComponent(projectId)}/flows`,
    );
    const flows = await flowsResponse.json();
    const actionsPageResponse = await fetch("/actions?connector_kind=langflow");
    const actionsPage = await actionsPageResponse.text();
    const actionsDocument = new DOMParser().parseFromString(actionsPage, "text/html");
    const actionKeys = [
      ...new Set(
        [...actionsDocument.querySelectorAll("[data-action-open]")]
          .map((element) => String(element.getAttribute("data-action-open") || ""))
          .filter(Boolean),
      ),
    ];
    const actionCatalog = [];
    for (const actionKey of actionKeys) {
      const detailResponse = await fetch(
        `/api/actions/catalog/${encodeURIComponent(actionKey)}`,
      );
      if (!detailResponse.ok) continue;
      const detail = await detailResponse.json();
      const action = detail.action || {};
      if (String(action.connector_kind || "") !== "langflow") continue;
      const binding = action.connector_binding || action.connector_config || {};
      const flowIdFromActionKey = (
        actionKey.match(
          /[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/i,
        ) || []
      )[0] || "";
      actionCatalog.push({
        action_key: actionKey,
        name: action.title || action.name_ko || action.name || actionKey,
        flow_id: String(binding.flow_id || action.flow_id || flowIdFromActionKey),
        project_id: String(binding.project_id || ""),
        deployment_id: String(binding.deployment_id || ""),
      });
    }
    return {
      state_status: stateResponse.status,
      flows_status: flowsResponse.status,
      actions_page_status: actionsPageResponse.status,
      state,
      endpoint_id: endpointId,
      project_id: projectId,
      flows: flows.flows || [],
      action_catalog: actionCatalog,
    };
  });
  assert(discovery.state_status === 200, "Playground state lookup failed");
  assert(discovery.flows_status === 200, "Playground Flow lookup failed");
  assert(discovery.endpoint_id, "existing 100002 endpoint is missing");
  assert(discovery.project_id, "existing boi-100002 project is missing");
  assert(
    String(discovery.state.identity?.employee_id || "") === config.employeeId,
    "Playground state does not use employee 100002",
  );
  const prdFlows = discovery.flows.filter(
    (flow) => flow.environment === "prd" && flow.origin_label === "Agent Hub",
  );
  assert(prdFlows.length > 0, "existing Agent Hub PRD Flow is missing");
  const universal = prdFlows.find(
    (flow) => String(flow.name || "").includes("Universal Simulation MCP"),
  ) || discovery.flows.find(
    (flow) => String(flow.name || "") === "BoI Universal Simulation MCP",
  );
  assert(universal, "Universal Simulation MCP Flow is missing");
  let actionFlow = prdFlows.find(
    (flow) => (flow.linked_actions || []).length > 0,
  );
  if (!actionFlow) {
    const action = discovery.action_catalog.find((item) => item.flow_id);
    if (action) {
      actionFlow = {
        flow_id: action.flow_id,
        name: action.name,
        environment: "prd",
        origin_label: "Agent Hub",
        linked_actions: [{ action_key: action.action_key }],
      };
    }
  }
  assert(actionFlow, "no existing PRD Flow has a connected Action");
  evidence.playground = {
    endpoint_id: discovery.endpoint_id,
    project_id: discovery.project_id,
    project_name: (
      discovery.state.endpoint_setups?.[discovery.endpoint_id]?.project?.name
      || discovery.state.project?.name
      || ""
    ),
    flow_count: discovery.flows.length,
    prd_flow_count: prdFlows.length,
    universal_flow: {
      flow_id: universal.flow_id,
      name: universal.name,
      environment: universal.environment,
      checksum_state: universal.checksum_state,
    },
    action_flow: {
      flow_id: actionFlow.flow_id,
      name: actionFlow.name,
      action_key: actionFlow.linked_actions[0].action_key,
    },
  };
  return { ...discovery, universal, actionFlow };
}

async function verifyLangflowCanvas(context, discovery) {
  const page = await context.newPage();
  monitor(page, "langflow");
  const canvasUrl = String(
    discovery.universal.canvas_url || discovery.universal.flow_url || "",
  );
  assert(canvasUrl, "Universal Simulation MCP Canvas URL is missing");
  const parsed = new URL(canvasUrl);
  assert(
    parsed.origin === new URL(config.langflowUrl).origin,
    "Canvas URL does not use the browser SSO origin",
  );
  assert(!parsed.search && !parsed.username && !parsed.password, "Canvas URL contains credentials");
  assert(!canvasUrl.includes("host.docker.internal"), "Canvas URL exposes a container host");
  await page.goto(canvasUrl, {
    waitUntil: "domcontentloaded",
    timeout: config.timeoutMs,
  });
  assert(
    (await page.locator('input[type="password"]').count()) === 0,
    "Langflow asked for a second password",
  );
  await page.waitForFunction(
    () => document.querySelectorAll(".react-flow__node").length > 0,
    undefined,
    { timeout: config.timeoutMs },
  );
  const whoamiResponse = await context.request.get(
    `${config.langflowUrl}/api/v1/users/whoami`,
  );
  const whoami = {
    status: whoamiResponse.status(),
    body: await whoamiResponse.json().catch(() => ({})),
  };
  assert(whoami.status === 200, `Langflow whoami returned ${whoami.status}`);
  assert(
    String(whoami.body.username || "") === config.employeeId,
    "Langflow browser user does not match employee 100002",
  );
  evidence.langflow = {
    canvas_url: safeUrl(page.url()),
    flow_id: discovery.universal.flow_id,
    node_count: await page.locator(".react-flow__node").count(),
    username: String(whoami.body.username || ""),
    second_password_form: false,
  };
  await screenshot(page, "02-langflow-exact-canvas.png");
  await page.close();
}

async function runUniversalPreview(page, discovery) {
  const response = await page.evaluate(
    async ({ endpointId, projectId, flowId }) => {
      const result = await fetch(
        `/api/agent-playground/flows/${encodeURIComponent(flowId)}/test`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            endpoint_id: endpointId,
            project_id: projectId,
            question: "데모 요청의 업무 맥락과 근거, 예상 처리 결과를 시뮬레이션해줘.",
            save_mode: "preview",
            title: "boi-dev 공용 데모 preview",
          }),
        },
      );
      return {
        status: result.status,
        body: await result.json().catch(() => ({})),
      };
    },
    {
      endpointId: discovery.endpoint_id,
      projectId: discovery.project_id,
      flowId: discovery.universal.flow_id,
    },
  );
  assert(response.status === 200, `Universal preview returned ${response.status}`);
  const serialized = JSON.stringify(response.body);
  assert(serialized.includes("SIMULATED"), "Universal preview is not marked SIMULATED");
  assert(
    serialized.includes("source_references"),
    "Universal preview does not preserve Wiki sources",
  );
  assert(
    serialized.includes("ontology_relationships"),
    "Universal preview does not include the Ontology contract",
  );
  assert(
    !serialized.includes("private_draft"),
    "preview evidence unexpectedly reports a private draft",
  );
  evidence.playground.universal_preview = {
    status: response.status,
    simulated: true,
    source_references_present: true,
    ontology_contract_present: true,
    save_mode: "preview",
  };
}

async function loginAgentHub(page) {
  await page.goto(config.agentHubUrl, {
    waitUntil: "domcontentloaded",
    timeout: config.timeoutMs,
  });
  if (page.url().includes("/protocol/openid-connect/")) {
    const passwordField = page.locator("#password");
    assert(
      (await passwordField.count()) === 0,
      "Agent Hub requested another password despite the active company SSO session",
    );
  }
  await page.waitForURL(
    (url) => url.origin === new URL(config.agentHubUrl).origin,
    { timeout: config.timeoutMs },
  );
  await page.locator("button.topbar-submit").waitFor({
    state: "visible",
    timeout: config.timeoutMs,
  });
  await page.waitForFunction(
    () => Boolean(localStorage.getItem("agenthub_token")),
    undefined,
    { timeout: config.timeoutMs },
  );
  let agentHub;
  for (let attempt = 0; attempt < 3 && !agentHub; attempt += 1) {
    try {
      agentHub = await page.evaluate(async () => {
        const token = localStorage.getItem("agenthub_token");
        if (!token) return { status: 0, body: {}, endpoints_status: 0, endpoints: [] };
        const [me, endpoints] = await Promise.all([
          fetch("/api/v1/users/me", {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch("/api/v1/deploy/endpoints", {
            headers: { Authorization: `Bearer ${token}` },
          }),
        ]);
        return {
          status: me.status,
          body: await me.json().catch(() => ({})),
          endpoints_status: endpoints.status,
          endpoints: await endpoints.json().catch(() => ([])),
        };
      });
    } catch (error) {
      if (!String(error).includes("Execution context was destroyed") || attempt === 2) {
        throw error;
      }
      await page.waitForLoadState("domcontentloaded");
      await page.waitForFunction(
        () => Boolean(localStorage.getItem("agenthub_token")),
        undefined,
        { timeout: config.timeoutMs },
      );
    }
  }
  assert(agentHub.status === 200, `Agent Hub users/me returned ${agentHub.status}`);
  assert(
    String(agentHub.body.employee_id || "") === config.employeeId,
    "Agent Hub did not resolve boi-dev to employee 100002",
  );
  assert(
    String(agentHub.body.name || "") === config.displayName,
    "Agent Hub did not use the demo display name",
  );
  assert(agentHub.endpoints_status === 200, "Agent Hub endpoint lookup failed");
  const endpoints = Array.isArray(agentHub.endpoints)
    ? agentHub.endpoints
    : agentHub.endpoints.items || agentHub.endpoints.endpoints || [];
  assert(endpoints.length > 0, "existing Agent Hub endpoint settings are missing");
  evidence.agent_hub = {
    employee_id: String(agentHub.body.employee_id || ""),
    display_name: String(agentHub.body.name || ""),
    role: String(agentHub.body.role || ""),
    endpoint_count: endpoints.length,
    second_password_form: false,
  };
  await screenshot(page, "03-agent-hub-existing-assets.png");
}

async function previewAction(page, discovery) {
  const actionKey = discovery.actionFlow.linked_actions[0].action_key;
  await page.goto(
    `${config.boiUrl}/actions?connector_kind=langflow`
      + `&action_key=${encodeURIComponent(actionKey)}`,
    { waitUntil: "domcontentloaded", timeout: config.timeoutMs },
  );
  await page.locator("[data-action-catalog]").waitFor({
    state: "visible",
    timeout: config.timeoutMs,
  });
  const preview = await page.evaluate(async (key) => {
    const detailResponse = await fetch(
      `/api/actions/catalog/${encodeURIComponent(key)}`,
    );
    const detail = await detailResponse.json();
    const payload = Object.fromEntries(
      (detail.action?.input_fields || []).map((field) => [
        field.name,
        field.type === "array" ? ["boi-dev demo"] : "boi-dev demo",
      ]),
    );
    const previewResponse = await fetch(
      `/api/actions/catalog/${encodeURIComponent(key)}/preview`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload }),
      },
    );
    return {
      detail_status: detailResponse.status,
      preview_status: previewResponse.status,
      preview: await previewResponse.json().catch(() => ({})),
      connector_kind: detail.action?.connector_kind || "",
      execution_mode: detail.action?.execution_mode || "",
    };
  }, actionKey);
  assert(preview.detail_status === 200, "connected Action detail lookup failed");
  assert(preview.preview_status === 200, "connected Action preview failed");
  assert(preview.preview.state === "ready", "connected Action preview is not ready");
  evidence.action = {
    action_key: actionKey,
    connector_kind: preview.connector_kind,
    execution_mode: preview.execution_mode,
    preview_state: preview.preview.state,
    dry_run: preview.preview.dry_run,
  };
  await screenshot(page, "04-connected-action-preview.png");
}

async function verifyLogout(context, page) {
  await page.goto(`${config.boiUrl}/auth/logout?next=/`, {
    waitUntil: "domcontentloaded",
    timeout: config.timeoutMs,
  });
  const browserSsoLogout = await context.request.get(
    `${config.langflowUrl}/oauth2/sign_out`,
    { maxRedirects: 0 },
  );
  const boi = await context.request.get(`${config.boiUrl}/api/auth/me`, {
    maxRedirects: 0,
  });
  const langflow = await context.request.get(
    `${config.langflowUrl}/api/v1/users/whoami`,
    { maxRedirects: 0 },
  );
  evidence.logout = {
    boi_status: boi.status(),
    langflow_status: langflow.status(),
    boi_session_invalidated: [401, 403].includes(boi.status()),
    langflow_session_invalidated: [302, 401, 403].includes(langflow.status()),
    browser_sso_logout_status: browserSsoLogout.status(),
    browser_sso_cookie_cleared: [200, 202, 302].includes(
      browserSsoLogout.status(),
    ),
  };
  assert(evidence.logout.boi_session_invalidated, "BoI session survived logout");
  assert(
    evidence.logout.langflow_session_invalidated,
    "Langflow browser session survived coordinated logout",
  );
}

const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox"],
});
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
page.setDefaultTimeout(config.timeoutMs);

try {
  await loginBoi(page);
  monitor(page, "boi");
  await screenshot(page, "01-playground-demo-ready.png");
  const discovery = await discoverPlayground(page);
  await verifyLangflowCanvas(context, discovery);
  await runUniversalPreview(page, discovery);
  await loginAgentHub(page);
  await previewAction(page, discovery);
  await verifyLogout(context, page);
  assert(
    evidence.unexpected_http_errors.length === 0,
    "unexpected browser HTTP errors were recorded",
  );
  assert(evidence.console_errors.length === 0, "browser console errors were recorded");
  assert(evidence.page_errors.length === 0, "browser page errors were recorded");
  evidence.ok = true;
} catch (error) {
  evidence.error = String(error?.stack || error);
} finally {
  const serialized = JSON.stringify(evidence, null, 2);
  evidence.secret_scan = {
    api_key: /(?:api[_-]?key)["']?\s*[:=]\s*["'][A-Za-z0-9._-]{16,}/i.test(serialized),
    boi_pat: /boi_pat_[A-Za-z0-9_-]{8,}/.test(serialized),
    run_token: /boi_run_[A-Za-z0-9_-]{8,}/.test(serialized),
    password_field: /"password"\s*:/i.test(serialized),
  };
  if (Object.values(evidence.secret_scan).some(Boolean)) {
    evidence.ok = false;
    evidence.error = "demo evidence contains a secret-like value";
  }
  await fs.writeFile(
    path.join(config.evidenceDir, "demo-account-e2e.json"),
    `${JSON.stringify(evidence, null, 2)}\n`,
  );
  await context.close();
  await browser.close();
}

if (!evidence.ok) {
  throw new Error(
    `demo account E2E failed: ${evidence.error || "unknown error"}; `
    + `see ${path.join(config.evidenceDir, "demo-account-e2e.json")}`,
  );
}
console.log(JSON.stringify({
  ok: true,
  employee_id: evidence.employee_id,
  evidence: path.join(config.evidenceDir, "demo-account-e2e.json"),
}));
