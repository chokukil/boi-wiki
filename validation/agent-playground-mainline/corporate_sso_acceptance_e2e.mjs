#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";

const required = (name, fallback = "") => {
  const value = String(process.env[name] || fallback).trim();
  if (!value) throw new Error(`${name} is required`);
  return value;
};
const booleanEnv = (name, fallback = false) => {
  const value = String(process.env[name] || "").trim().toLowerCase();
  if (!value) return fallback;
  return ["1", "true", "yes", "on"].includes(value);
};
const origin = (value) => new URL(value).origin;
const sanitizedUrl = (value) => {
  const url = new URL(value);
  return `${url.origin}${url.pathname}`;
};
const nested = (value, ...keys) => {
  let current = value;
  for (const key of keys) {
    if (!current || typeof current !== "object") return undefined;
    current = current[key];
  }
  return current;
};
const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};

const config = {
  environment: required("CORPORATE_ACCEPTANCE_ENVIRONMENT", "validation"),
  authMode: required("CORPORATE_AUTH_MODE", "embedded_sso"),
  boiUrl: required("BOI_CORPORATE_URL", process.env.BOI_BASE_URL),
  langflowUrl: required(
    "LANGFLOW_EXTERNAL_URL",
    process.env.LANGFLOW_BROWSER_URL,
  ),
  employeeId: required(
    "CORPORATE_EXPECTED_EMPLOYEE_ID",
    process.env.BOI_EMPLOYEE_ID,
  ),
  flowId: required("CORPORATE_EXPECTED_FLOW_ID"),
  projectId: String(process.env.CORPORATE_EXPECTED_PROJECT_ID || "").trim(),
  hcpEvidenceFile: required("CORPORATE_HCP_EVIDENCE_FILE"),
  evidenceDir: required(
    "CORPORATE_EVIDENCE_DIR",
    "artifacts/agent-playground-corporate-sso-acceptance",
  ),
  storageState: String(process.env.CORPORATE_STORAGE_STATE || "").trim(),
  storageStateOutput: String(
    process.env.CORPORATE_STORAGE_STATE_OUTPUT || "",
  ).trim(),
  interactive: booleanEnv("CORPORATE_SSO_INTERACTIVE"),
  timeoutMs: Number(process.env.CORPORATE_SSO_TIMEOUT_MS || 300_000),
  logoutConfirmSelector: String(
    process.env.CORPORATE_LOGOUT_CONFIRM_SELECTOR || "",
  ).trim(),
  validationUsername: String(
    process.env.VALIDATION_SSO_USERNAME || "",
  ).trim(),
  validationPassword: String(
    process.env.VALIDATION_SSO_PASSWORD || "",
  ),
  validationIdentityFile: String(
    process.env.VALIDATION_SSO_IDENTITY_FILE || "",
  ).trim(),
};
if (
  config.environment === "validation"
  && config.validationIdentityFile
  && !config.validationPassword
) {
  const validationIdentities = JSON.parse(
    await fs.readFile(config.validationIdentityFile, "utf8"),
  );
  config.validationUsername ||= config.employeeId;
  config.validationPassword = String(
    validationIdentities[config.validationUsername] || "",
  );
}

assert(
  ["external_jwt", "trusted_header_bridge", "embedded_sso"].includes(
    config.authMode,
  ),
  "CORPORATE_AUTH_MODE must be external_jwt, trusted_header_bridge, or embedded_sso",
);
assert(
  ["corporate", "validation"].includes(config.environment),
  "CORPORATE_ACCEPTANCE_ENVIRONMENT must be corporate or validation",
);
if (config.environment === "corporate") {
  assert(
    !config.validationUsername && !config.validationPassword,
    "provider credentials must not be passed to the corporate acceptance runner",
  );
  assert(
    config.storageState || config.interactive,
    "corporate acceptance requires an approved storage state or interactive SSO",
  );
}
const hcpEvidence = JSON.parse(
  await fs.readFile(config.hcpEvidenceFile, "utf8"),
);
const hcpStatus = (name) => Number(
  nested(hcpEvidence, "hcp", name, "response", "status")
  ?? nested(hcpEvidence, name, "status")
  ?? 0,
);
const hcpEnvironment = String(
  hcpEvidence.environment || (
    config.environment === "validation" ? "validation" : ""
  ),
);
const hcpFailClosed = {
  environment: hcpEnvironment,
  role_reduction_status: hcpStatus("role_reduction"),
  account_disabled_status: hcpStatus("account_disabled"),
  outage_status: hcpStatus("outage"),
  recovered_status: hcpStatus("recovered"),
};
hcpFailClosed.ok = (
  hcpFailClosed.role_reduction_status === 403
  && hcpFailClosed.account_disabled_status === 403
  && hcpFailClosed.outage_status === 503
  && hcpFailClosed.recovered_status === 200
  && hcpFailClosed.environment === config.environment
);

await fs.mkdir(config.evidenceDir, { recursive: true });
const result = {
  schema: "boi.agent-playground.corporate-sso-acceptance.v1",
  ok: false,
  final_acceptance: false,
  environment: config.environment,
  auth_mode: config.authMode,
  generated_at: new Date().toISOString(),
  employee_id: config.employeeId,
  boi_auth_source: "",
  langflow_user: "",
  principal_match: false,
  second_password_form: null,
  exact_canvas_loaded: false,
  canvas_state: {},
  exact_reference: {
    flow_id: config.flowId,
    project_id: config.projectId,
    environment: "",
    origin_label: "",
  },
  browser_sso: {},
  spoof_status: 0,
  logout: {},
  hcp_fail_closed: hcpFailClosed,
  screenshots: [],
  redirect_path: [],
  unexpected_http_errors: [],
  ignored_console_warnings: [],
  console_errors: [],
  page_errors: [],
  secret_exposure: {
    query_credentials: false,
    container_address: false,
    response_tokens: false,
  },
};

const browser = await chromium.launch({
  headless: !config.interactive,
  args: ["--no-sandbox"],
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  ...(config.storageState ? { storageState: config.storageState } : {}),
});
const page = await context.newPage();
page.setDefaultTimeout(config.timeoutMs);
let monitorRuntime = false;

const monitor = (targetPage) => {
  targetPage.on("console", (message) => {
    const text = message.text();
    const ignoredReason = (
      text === "Duplicate request: /api/v1/projects/"
        ? "langflow_duplicate_projects_request"
        : (
          text.includes("https://api.github.com/repos/langflow-ai/langflow")
          || text.startsWith(
            "Error fetching repository data: AxiosError: Network Error",
          )
        )
          ? "langflow_optional_github_metadata_unavailable"
          : ""
    );
    if (
      monitorRuntime
      && message.type() === "error"
      && !text.includes("favicon")
      && !text.startsWith("Failed to load resource:")
    ) {
      if (ignoredReason) {
        result.ignored_console_warnings.push({
          reason: ignoredReason,
          message: text.slice(0, 500),
        });
      } else {
        result.console_errors.push(text.slice(0, 500));
      }
    }
  });
  targetPage.on("pageerror", (error) => {
    if (monitorRuntime) result.page_errors.push(String(error).slice(0, 500));
  });
  targetPage.on("response", (response) => {
    const url = new URL(response.url());
    const safe = `${url.origin}${url.pathname}`;
    if (!result.redirect_path.includes(safe) && result.redirect_path.length < 30) {
      result.redirect_path.push(safe);
    }
    if (
      monitorRuntime
      && response.status() >= 400
      && !url.pathname.endsWith("/favicon.ico")
    ) {
      result.unexpected_http_errors.push({
        status: response.status(),
        method: response.request().method(),
        url: safe,
      });
    }
  });
};
monitor(page);

const screenshot = async (name, targetPage = page) => {
  const filename = `${name}.png`;
  await targetPage.screenshot({
    path: path.join(config.evidenceDir, filename),
    fullPage: true,
  });
  result.screenshots.push(filename);
};

const waitForPlayground = async () => {
  await page.goto(`${config.boiUrl.replace(/\/+$/, "")}/playground`, {
    waitUntil: "domcontentloaded",
    timeout: config.timeoutMs,
  });
  if (
    config.environment === "validation"
    && config.validationUsername
    && config.validationPassword
    && page.url().includes("/protocol/openid-connect/")
  ) {
    await page.locator("#username").fill(config.validationUsername);
    await page.locator("#password").fill(config.validationPassword);
    await page.locator("#kc-login").click();
  }
  await page.locator("[data-agent-playground]").waitFor({
    state: "visible",
    timeout: config.timeoutMs,
  });
};

try {
  await waitForPlayground();
  const identity = await page.evaluate(async () => {
    const response = await fetch("/api/auth/me");
    return { status: response.status, body: await response.json() };
  });
  assert(identity.status === 200, `BoI identity returned HTTP ${identity.status}`);
  result.boi_auth_source = String(identity.body.auth_source || "");
  assert(
    String(identity.body.employee_id || "") === config.employeeId,
    "BoI Principal does not match the expected employee",
  );
  assert(
    result.boi_auth_source !== "dev",
    "corporate acceptance cannot use the dev identity provider",
  );

  const spoofEmployee = config.employeeId === "100001" ? "100002" : "100001";
  result.spoof_status = await page.evaluate(async (employee) => {
    const response = await fetch(
      `/api/agent-playground?employee_id=${encodeURIComponent(employee)}`,
    );
    return response.status;
  }, spoofEmployee);
  assert(result.spoof_status === 403, "employee query spoof was not rejected");
  monitorRuntime = true;

  const discovery = await page.evaluate(
    async ({ expectedFlowId, expectedProjectId }) => {
      const stateResponse = await fetch("/api/agent-playground");
      const state = await stateResponse.json();
      const endpointId = String(state.default_endpoint_id || "");
      const setup = state.endpoint_setups?.[endpointId] || {};
      const projectId = String(
        expectedProjectId
        || setup.project?.id
        || state.project?.id
        || "",
      );
      const flowsResponse = await fetch(
        `/api/agent-playground/endpoints/${encodeURIComponent(endpointId)}`
        + `/projects/${encodeURIComponent(projectId)}/flows`,
      );
      const flows = await flowsResponse.json();
      return {
        state_status: stateResponse.status,
        flows_status: flowsResponse.status,
        endpoint_id: endpointId,
        project_id: projectId,
        browser_sso: state.browser_sso || {},
        flow: (flows.flows || []).find(
          (item) => String(item.flow_id || item.id || "") === expectedFlowId,
        ) || null,
      };
    },
    {
      expectedFlowId: config.flowId,
      expectedProjectId: config.projectId,
    },
  );
  assert(discovery.state_status === 200, "Playground state lookup failed");
  assert(discovery.flows_status === 200, "Flow discovery failed");
  assert(discovery.flow, "the exact deployed Flow was not rediscovered");
  assert(
    discovery.flow.environment === "prd"
    && discovery.flow.origin_label === "Agent Hub",
    "the exact Flow is not a confirmed Agent Hub PRD deployment",
  );
  result.exact_reference.project_id = discovery.project_id;
  result.exact_reference.environment = discovery.flow.environment;
  result.exact_reference.origin_label = discovery.flow.origin_label;
  result.browser_sso = {
    mode: String(discovery.browser_sso.mode || ""),
    status: String(discovery.browser_sso.status || ""),
    principal_match: Boolean(discovery.browser_sso.principal_match),
  };

  const canvasUrl = String(
    discovery.flow.canvas_url || discovery.flow.flow_url || "",
  );
  assert(canvasUrl, "server did not provide an exact Canvas URL");
  assert(
    origin(canvasUrl) === origin(config.langflowUrl),
    "Canvas URL does not use LANGFLOW_EXTERNAL_URL",
  );
  assert(
    canvasUrl.includes(config.flowId)
    && canvasUrl.includes(discovery.project_id),
    "Canvas URL does not contain the exact Flow and project",
  );
  result.secret_exposure.query_credentials = Boolean(
    new URL(canvasUrl).username
    || new URL(canvasUrl).password
    || new URL(canvasUrl).search,
  );
  result.secret_exposure.container_address = canvasUrl.includes(
    "host.docker.internal",
  );
  assert(
    !result.secret_exposure.query_credentials
    && !result.secret_exposure.container_address,
    "Canvas URL exposes credentials or a container-only address",
  );

  const exactPlaygroundUrl = new URL(
    `${config.boiUrl.replace(/\/+$/, "")}/playground`,
  );
  exactPlaygroundUrl.searchParams.set("stage", "action");
  exactPlaygroundUrl.searchParams.set("endpoint_id", discovery.endpoint_id);
  exactPlaygroundUrl.searchParams.set("project_id", discovery.project_id);
  exactPlaygroundUrl.searchParams.set("flow_id", config.flowId);
  await page.goto(exactPlaygroundUrl.toString(), {
    waitUntil: "domcontentloaded",
    timeout: config.timeoutMs,
  });
  await page.waitForFunction(
    (flowId) => (
      document.querySelector("[data-selected-flow-id]")?.textContent?.trim()
      === flowId
    ),
    config.flowId,
    { timeout: config.timeoutMs },
  );
  const selectedEnvironment = (
    await page.locator("[data-selected-flow-environment]").textContent()
  ).trim();
  assert(
    selectedEnvironment === "PRD · Agent Hub",
    `Playground selected Flow origin is ${selectedEnvironment}`,
  );

  const langflowPage = await context.newPage();
  monitor(langflowPage);
  await langflowPage.goto(canvasUrl, {
    waitUntil: "domcontentloaded",
    timeout: config.timeoutMs,
  });
  await langflowPage.waitForURL(
    (url) => url.origin === origin(config.langflowUrl),
    { timeout: config.timeoutMs },
  );
  result.second_password_form = (
    await langflowPage.locator('input[type="password"]').count()
  ) > 0;
  assert(
    result.second_password_form === false,
    "Langflow displayed a second password form",
  );
  await langflowPage.waitForFunction(
    () => {
      const text = document.body?.innerText || "";
      const nodeCount = document.querySelectorAll(".react-flow__node").length;
      return (
        nodeCount > 0
        && text.trim().length > 50
        && !text.includes("Loading...")
        && !text.includes("Untitled Flow")
      );
    },
    undefined,
    { timeout: config.timeoutMs },
  );
  result.canvas_state = await langflowPage.evaluate(() => ({
    node_count: document.querySelectorAll(".react-flow__node").length,
    untitled_visible: (document.body?.innerText || "").includes("Untitled Flow"),
    pathname: window.location.pathname,
  }));
  assert(
    Number(result.canvas_state.node_count || 0) > 0
    && result.canvas_state.untitled_visible === false,
    "exact Langflow Canvas graph did not finish loading",
  );
  const whoami = await context.request.get(
    `${config.langflowUrl.replace(/\/+$/, "")}/api/v1/users/whoami`,
  );
  const whoamiBody = await whoami.json().catch(() => ({}));
  assert(
    whoami.status() === 200,
    `Langflow whoami returned HTTP ${whoami.status()}`,
  );
  result.langflow_user = String(
    whoamiBody.username || whoamiBody.employee_id || "",
  );
  result.principal_match = (
    result.langflow_user === config.employeeId
    && String(identity.body.employee_id || "") === config.employeeId
  );
  assert(result.principal_match, "BoI and Langflow Principals do not match");
  const browserVerification = await page.evaluate(
    async ({ endpointId, employeeId, userId }) => {
      const response = await fetch("/api/agent-playground/browser-sso/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          endpoint_id: endpointId,
          langflow_username: employeeId,
          langflow_user_id: userId,
        }),
      });
      return {
        status: response.status,
        body: await response.json().catch(() => ({})),
      };
    },
    {
      endpointId: discovery.endpoint_id,
      employeeId: config.employeeId,
      userId: String(whoamiBody.id || ""),
    },
  );
  assert(
    browserVerification.status === 200,
    `browser SSO verification returned HTTP ${browserVerification.status}`,
  );
  result.browser_sso = {
    mode: String(browserVerification.body.browser_sso?.mode || ""),
    status: String(browserVerification.body.browser_sso?.status || ""),
    principal_match: Boolean(
      browserVerification.body.browser_sso?.principal_match,
    ),
  };
  assert(
    result.browser_sso.status === "ready"
    && result.browser_sso.principal_match,
    "Playground browser SSO readiness did not confirm the same Principal",
  );
  assert(
    result.browser_sso.mode === config.authMode,
    `Playground browser SSO mode ${result.browser_sso.mode} does not match ${config.authMode}`,
  );
  result.exact_canvas_loaded = true;
  await screenshot("01-corporate-exact-canvas", langflowPage);
  await screenshot("02-corporate-playground-ready");

  if (config.storageStateOutput) {
    await context.storageState({ path: config.storageStateOutput });
    await fs.chmod(config.storageStateOutput, 0o600);
  }

  monitorRuntime = false;
  await page.goto(
    `${config.boiUrl.replace(/\/+$/, "")}/auth/logout?next=/`,
    { waitUntil: "domcontentloaded", timeout: config.timeoutMs },
  );
  if (config.logoutConfirmSelector) {
    const confirmation = page.locator(config.logoutConfirmSelector).first();
    if (await confirmation.isVisible().catch(() => false)) {
      await confirmation.click();
    }
  }
  const boiProbe = await context.request.get(
    `${config.boiUrl.replace(/\/+$/, "")}/api/auth/me`,
    { maxRedirects: 0 },
  );
  const langflowProbe = await context.request.get(
    `${config.langflowUrl.replace(/\/+$/, "")}/api/v1/users/whoami`,
    { maxRedirects: 0 },
  );
  result.logout = {
    boi_status: boiProbe.status(),
    langflow_status: langflowProbe.status(),
    boi_session_cleared: [401, 403].includes(boiProbe.status()),
    langflow_session_cleared: [302, 401, 403].includes(
      langflowProbe.status(),
    ),
    canvas_requires_reauthentication: [302, 401, 403].includes(
      langflowProbe.status(),
    ),
  };

  assert(
    result.logout.boi_session_cleared,
    "BoI session survived coordinated logout",
  );
  assert(
    result.logout.langflow_session_cleared
    && result.logout.canvas_requires_reauthentication,
    "Langflow Canvas remained authenticated after coordinated logout",
  );
  assert(result.hcp_fail_closed.ok, "corporate HCP fail-closed evidence is incomplete");
  assert(result.unexpected_http_errors.length === 0, "unexpected HTTP errors");
  assert(result.console_errors.length === 0, "unexpected console errors");
  assert(result.page_errors.length === 0, "unexpected page errors");
  result.ok = true;
  result.final_acceptance = config.environment === "corporate";
} catch (error) {
  result.error = String(error?.stack || error);
  throw error;
} finally {
  const serialized = `${JSON.stringify(result, null, 2)}\n`;
  result.secret_exposure.response_tokens = (
    /(?:access|refresh|id|run|api)[_-]?token["']?\s*[:=]\s*["'][A-Za-z0-9._-]{16,}/i
      .test(serialized)
    || /boi_(?:pat|run)_[A-Za-z0-9_-]{8,}/.test(serialized)
  );
  if (result.secret_exposure.response_tokens) {
    result.ok = false;
    result.final_acceptance = false;
    result.error = "acceptance evidence contains a token-like value";
  }
  await fs.writeFile(
    path.join(config.evidenceDir, "corporate-sso-acceptance.json"),
    `${JSON.stringify(result, null, 2)}\n`,
  );
  await context.close();
  await browser.close();
}

console.log(JSON.stringify({
  ok: result.ok,
  final_acceptance: result.final_acceptance,
  environment: result.environment,
  evidence: path.join(config.evidenceDir, "corporate-sso-acceptance.json"),
}));
