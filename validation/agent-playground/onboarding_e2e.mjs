#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const playwrightPath = process.env.PLAYWRIGHT_MODULE_PATH || "playwright";
const { chromium } = require(playwrightPath);

const config = {
  boiUrl: process.env.BOI_URL || "http://localhost:28005",
  langflowUrl: process.env.LANGFLOW_URL || "http://localhost:7867",
  langflowEndpoint:
    process.env.LANGFLOW_ENDPOINT_URL || "http://localhost:7867",
  employeeId: process.env.BOI_EMPLOYEE_ID || "100002",
  ssoPassword: process.env.BOI_SSO_PASSWORD || "",
  langflowPassword: process.env.LANGFLOW_PASSWORD || "",
  agentHubIdentityFile:
    process.env.AGENT_HUB_IDENTITY_FILE
    || "/tmp/boi-ap-agent-hub-sso-users.json",
  langflowIdentityFile:
    process.env.LANGFLOW_IDENTITY_FILE
    || "/tmp/boi-ap-ux-final-langflow-users-20260727.json",
  endpointName: process.env.BOI_ENDPOINT_NAME || "내 Langflow 1.11",
  evidenceDir:
    process.env.PLAYWRIGHT_EVIDENCE_DIR ||
    "artifacts/agent-playground-onboarding-browser",
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || "",
};

const [agentHubIdentities, langflowIdentities] = await Promise.all([
  fs.readFile(config.agentHubIdentityFile, "utf8")
    .then((value) => JSON.parse(value))
    .catch(() => ({})),
  fs.readFile(config.langflowIdentityFile, "utf8")
    .then((value) => JSON.parse(value))
    .catch(() => ({})),
]);
config.ssoPassword ||= String(agentHubIdentities[config.employeeId] || "");
config.langflowPassword ||= String(
  langflowIdentities.users?.[config.employeeId]?.password || "",
);

for (const name of ["ssoPassword", "langflowPassword"]) {
  if (!config[name]) throw new Error(`${name} is required`);
}

const result = {
  ok: false,
  identity: {},
  initial: {},
  langflow: {},
  ready: {},
  idempotency: {},
  console_errors: [],
  page_errors: [],
  http_errors: [],
};

await fs.mkdir(config.evidenceDir, { recursive: true });

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function screenshot(page, name) {
  await page.screenshot({
    path: path.join(config.evidenceDir, `${name}.png`),
    fullPage: true,
  });
}

function diagnostics(page, scope) {
  page.on("console", (message) => {
    const text = message.text();
    if (
      message.type() === "error" &&
      !text.includes("favicon") &&
      !text.startsWith("Failed to load resource:")
    ) {
      result.console_errors.push({ scope, text: text.slice(0, 500) });
    }
  });
  page.on("pageerror", (error) => {
    result.page_errors.push({ scope, text: String(error.message || error).slice(0, 500) });
  });
  page.on("response", (response) => {
    if (response.status() >= 400) {
      const url = new URL(response.url());
      if (
        scope === "langflow-key" &&
        response.status() === 403 &&
        url.pathname === "/api/v1/auto_login"
      ) {
        return;
      }
      result.http_errors.push({
        scope,
        status: response.status(),
        method: response.request().method(),
        url: `${url.origin}${url.pathname}`,
      });
    }
  });
}

async function loginBoi(page) {
  await page.goto(`${config.boiUrl}/playground`, { waitUntil: "domcontentloaded" });
  if (page.url().includes("/protocol/openid-connect/")) {
    const authorization = new URL(page.url());
    assert(authorization.searchParams.get("state"), "OIDC state is missing");
    assert(authorization.searchParams.get("nonce"), "OIDC nonce is missing");
    assert(authorization.searchParams.get("code_challenge_method") === "S256", "PKCE S256 is missing");
    await page.locator("#username").fill(config.employeeId);
    await page.locator("#password").fill(config.ssoPassword);
    await Promise.all([
      page.waitForURL((url) => url.origin === new URL(config.boiUrl).origin),
      page.locator("#kc-login").click(),
    ]);
  }
  const state = await page.evaluate(async () => {
    const response = await fetch("/api/agent-playground");
    return { status: response.status, body: await response.json() };
  });
  assert(state.status === 200, `Playground state returned HTTP ${state.status}`);
  assert(state.body.identity?.employee_id === config.employeeId, "SSO employee does not match");
  assert(state.body.identity?.auth_source === "keycloak", "Playground is not using Keycloak");
  result.identity = {
    employee_id: state.body.identity.employee_id,
    auth_source: state.body.identity.auth_source,
  };
  result.initial = {
    required: state.body.onboarding?.required,
    current_step: state.body.onboarding?.current_step,
    endpoint_count: (state.body.endpoints || []).length,
  };
  assert(result.initial.required === true, "clean onboarding was not required");
  assert(result.initial.endpoint_count === 0, "clean onboarding already has endpoints");
  return state.body;
}

async function createLangflowKey(context) {
  const page = await context.newPage();
  diagnostics(page, "langflow-key");
  await page.goto(`${config.langflowUrl}/settings/api-keys`, { waitUntil: "domcontentloaded" });
  const password = page.locator('input[type="password"]');
  const loginVisible = await password
    .waitFor({ state: "visible", timeout: 15_000 })
    .then(() => true)
    .catch(() => false);
  if (loginVisible) {
    await page.locator('input[name="username"], input[type="text"]').first().fill(config.employeeId);
    await password.fill(config.langflowPassword);
    await Promise.all([
      page.waitForURL((url) => !url.pathname.endsWith("/login")),
      page.getByRole("button", { name: "Sign In", exact: true }).click(),
    ]);
    await page.goto(`${config.langflowUrl}/settings/api-keys`, {
      waitUntil: "domcontentloaded",
    });
  }
  await page.getByRole("button", { name: /Add New/i }).click();
  const dialog = page.getByRole("dialog");
  await dialog.waitFor();
  const nameInput = dialog.locator("input").first();
  await nameInput.fill("BoI Agent Playground");
  const responsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "POST" &&
      /api[_/-]?keys?/i.test(url.pathname)
    );
  });
  await dialog.getByRole("button", { name: /Generate|Create/i }).click();
  const response = await responsePromise;
  assert(response.ok(), `Langflow API Key creation returned HTTP ${response.status()}`);
  const payload = await response.json();
  const apiKey = String(payload.api_key || payload.key || payload.token || "");
  assert(apiKey.length >= 16, "Langflow did not return a one-time API Key");
  const done = dialog.getByRole("button", { name: "Done", exact: true });
  const close = dialog.getByRole("button", { name: "Close", exact: true });
  if (await done.count()) await done.click();
  else if (await close.count()) await close.click();
  else await page.keyboard.press("Escape");
  await page.getByText("BoI Agent Playground", { exact: true }).first().waitFor();
  await screenshot(page, "02-langflow-key-list-masked");
  const visible = await page.locator("body").innerText();
  assert(!visible.includes(apiKey), "raw Langflow API Key remained visible after closing");
  result.langflow.key_hidden_after_creation = true;
  await page.close();
  return apiKey;
}

async function completeOnboarding(page, apiKey) {
  const root = page.locator("[data-agent-playground]");
  const form = root.locator("[data-onboarding-connection-form]");
  await form.locator('[name="name"]').fill(config.endpointName);
  await form.locator('[name="base_url"]').fill(config.langflowEndpoint);
  await form.locator('[name="api_key"]').fill(apiKey);
  await screenshot(page, "01-boi-onboarding-connection");
  await root.locator("[data-onboarding-test-connection]").click();
  await page.waitForFunction(
    () =>
      document
        .querySelector("[data-onboarding-connection-output]")
        ?.textContent?.trim()
        .startsWith("연결 성공"),
    null,
    { timeout: 30_000 },
  );
  await form.getByRole("button", { name: "확인하고 저장" }).click();
  await root
    .locator('[data-onboarding-stage="knowledge"]')
    .waitFor({ state: "visible", timeout: 30_000 });
  await screenshot(page, "03-boi-knowledge-auto-setup");
  await root.locator("[data-onboarding-bootstrap]").click();
  await root
    .locator('[data-onboarding-stage="flow"]')
    .waitFor({ state: "visible", timeout: 120_000 });
  await screenshot(page, "04-boi-first-flow-ready");

  const ready = await page.evaluate(async () => (await fetch("/api/agent-playground")).json());
  const endpointId = ready.default_endpoint_id;
  const setup = ready.endpoint_setups?.[endpointId] || {};
  assert(ready.onboarding?.status === "ready", "onboarding did not reach ready");
  assert(setup.smoke?.status === "passed", "canonical preview smoke did not pass");
  result.ready = {
    status: ready.onboarding.status,
    endpoint_id: endpointId,
    project_id: setup.project?.id || setup.project_id,
    flow_id: setup.canonical_flow?.id || setup.flow_id,
    flow_checksum: setup.canonical_flow?.checksum || setup.flow_checksum,
    checks: ready.onboarding.checks,
  };

  const before = {
    project_id: result.ready.project_id,
    flow_id: result.ready.flow_id,
  };
  const rerun = await page.evaluate(async (id) => {
    const response = await fetch("/api/agent-playground/bootstrap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint_id: id }),
    });
    return { status: response.status, body: await response.json() };
  }, endpointId);
  assert(rerun.status === 200, `idempotent bootstrap returned HTTP ${rerun.status}`);
  const after = await page.evaluate(async () => (await fetch("/api/agent-playground")).json());
  const afterSetup = after.endpoint_setups?.[endpointId] || {};
  result.idempotency = {
    bootstrap_status: rerun.status,
    same_project:
      before.project_id === (afterSetup.project?.id || afterSetup.project_id),
    same_flow:
      before.flow_id === (afterSetup.canonical_flow?.id || afterSetup.flow_id),
  };
  assert(result.idempotency.same_project, "bootstrap duplicated the project");
  assert(result.idempotency.same_flow, "bootstrap duplicated the canonical Flow");

  await root.locator("[data-onboarding-finish]").click();
  await root.locator("[data-workbench-only]").first().waitFor({ state: "visible" });
  await screenshot(page, "05-boi-workbench-ready");
}

const browser = await chromium.launch({
  headless: process.env.PLAYWRIGHT_HEADFUL !== "1",
  ...(config.executablePath ? { executablePath: config.executablePath } : {}),
});
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  diagnostics(page, "boi-onboarding");
  await loginBoi(page);
  const apiKey = await createLangflowKey(context);
  await completeOnboarding(page, apiKey);
  assert(result.console_errors.length === 0, "unexpected browser console errors");
  assert(result.page_errors.length === 0, "unexpected browser page errors");
  assert(result.http_errors.length === 0, "unexpected browser HTTP errors");
  result.ok = true;
  await context.close();
} finally {
  await browser.close();
  await fs.writeFile(
    path.join(config.evidenceDir, "fresh-onboarding-result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
    { mode: 0o600 },
  );
}

console.log(JSON.stringify({ ok: result.ok, evidence_dir: config.evidenceDir }));
