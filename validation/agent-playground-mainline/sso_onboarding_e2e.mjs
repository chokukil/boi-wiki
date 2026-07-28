#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";

const boiUrl = process.env.BOI_BASE_URL || "http://localhost:28005";
const langflowBrowserUrl =
  process.env.LANGFLOW_BROWSER_URL || "http://localhost:17867";
const langflowDeployUrl =
  process.env.LANGFLOW_DEPLOY_URL || "http://host.docker.internal:7867";
const employeeId = process.env.BOI_EMPLOYEE_ID || "100002";
const identityFile =
  process.env.AGENT_HUB_IDENTITY_FILE
  || "/tmp/boi-ap-agent-hub-sso-users.json";
const evidenceDir =
  process.env.PLAYWRIGHT_EVIDENCE_DIR
  || "artifacts/agent-playground-sso-onboarding";

const identities = JSON.parse(await fs.readFile(identityFile, "utf8"));
const password = String(process.env.BOI_SSO_PASSWORD || identities[employeeId] || "");
if (!password) throw new Error(`${employeeId} validation password is unavailable`);
await fs.mkdir(evidenceDir, { recursive: true });

const result = {
  ok: false,
  employee_id: employeeId,
  api_key_created_in_langflow_ui: false,
  api_key_response_redacted: false,
  endpoint_owner: "",
  browser_owner: "",
  project_name: "",
  recommended_flow: "",
  preview_smoke: "",
  recommended_smoke: "",
  redundant_api_keys_removed: 0,
  screenshots: [],
  unexpected_http_errors: [],
  known_benign_console_messages: [],
  console_errors: [],
  page_errors: [],
};

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function monitor(page, scope) {
  page.on("console", (message) => {
    if (message.type() !== "error" || message.text().includes("favicon")) return;
    const text = message.text().slice(0, 500);
    if (/^Duplicate request: \/api\/v1\/projects\/?$/.test(text)) {
      result.known_benign_console_messages.push(`${scope}: ${text}`);
      return;
    }
    result.console_errors.push(`${scope}: ${text}`);
  });
  page.on("pageerror", (error) => {
    result.page_errors.push(`${scope}: ${String(error).slice(0, 500)}`);
  });
  page.on("response", (response) => {
    if (response.status() < 400 || response.url().includes("/favicon")) return;
    result.unexpected_http_errors.push({
      scope,
      status: response.status(),
      method: response.request().method(),
      url: response.url().replace(/[?#].*$/, ""),
    });
  });
}

async function capture(page, name) {
  const target = path.resolve(evidenceDir, `${name}.png`);
  await page.screenshot({ path: target, fullPage: true });
  result.screenshots.push(target);
}

async function completeKeycloakLogin(page, expectedOrigin) {
  if (!page.url().includes("/protocol/openid-connect/")) return;
  const authorization = new URL(page.url());
  assert(
    authorization.searchParams.get("code_challenge_method") === "S256",
    "OIDC PKCE S256 is missing",
  );
  await page.locator("#username").fill(employeeId);
  await page.locator("#password").fill(password);
  await Promise.all([
    page.waitForURL((url) => url.origin === expectedOrigin, { timeout: 30_000 }),
    page.locator("#kc-login").click(),
  ]);
}

async function waitForLangflow(page) {
  await page.waitForFunction(
    () => {
      const text = document.body?.innerText || "";
      return !text.includes("Loading...") && text.trim().length > 50;
    },
    undefined,
    { timeout: 60_000 },
  );
}

const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const boiPage = await context.newPage();
const langflowPage = await context.newPage();
monitor(boiPage, "boi");
monitor(langflowPage, "langflow");

let apiKey = "";
let apiKeyId = "";
const apiKeyName = `BoI Agent Playground SSO ${new Date().toISOString()}`;
try {
  // Establish the BoI SSO session before loading the Playground workbench.
  // Opening /playground first would start background Flow/MCP requests with
  // the previous endpoint credential while this scenario rotates that key.
  // The real onboarding order is identity -> key -> endpoint -> bootstrap ->
  // workbench, so keep the browser verification aligned with that order.
  await boiPage.goto(`${boiUrl}/auth/login?next=/`, { waitUntil: "domcontentloaded" });
  await completeKeycloakLogin(boiPage, new URL(boiUrl).origin);
  assert(
    new URL(boiPage.url()).origin === new URL(boiUrl).origin,
    "BoI SSO did not return to the application origin",
  );

  await langflowPage.goto(`${langflowBrowserUrl}/settings/api-keys`, {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  await completeKeycloakLogin(langflowPage, new URL(langflowBrowserUrl).origin);
  if (!langflowPage.url().includes("/settings/api-keys")) {
    await langflowPage.goto(`${langflowBrowserUrl}/settings/api-keys`, {
      waitUntil: "domcontentloaded",
    });
  }
  await waitForLangflow(langflowPage);
  const passwordInputs = await langflowPage.locator('input[type="password"]').count();
  assert(passwordInputs === 0, "Langflow displayed a second password form");

  await langflowPage.getByText("Add New", { exact: true }).click();
  await langflowPage.locator("input[name=apikey]").fill(apiKeyName);
  await langflowPage.getByText("Generate API Key", { exact: true }).click();
  await langflowPage.getByText(
    "Please save this secret key somewhere safe and accessible.",
    { exact: false },
  ).waitFor({ state: "visible", timeout: 15_000 });
  const secretDialog = langflowPage.getByRole("dialog");
  await langflowPage.waitForFunction(
    () => Array.from(document.querySelectorAll('input'))
      .some((input) => String(input.value || "").startsWith("sk-")),
    undefined,
    { timeout: 15_000 },
  );
  apiKey = String(
    await secretDialog.locator("input").evaluateAll((inputs) => (
      inputs
        .map((input) => String(input.value || ""))
        .find((value) => value.startsWith("sk-")) || ""
    )),
  );
  assert(apiKey.startsWith("sk-"), "Langflow did not display the one-time API key");
  result.api_key_created_in_langflow_ui = true;
  await langflowPage.getByText("Done", { exact: true }).click();
  await langflowPage.getByText(
    "Please save this secret key somewhere safe and accessible.",
    { exact: false },
  ).waitFor({ state: "hidden", timeout: 15_000 });

  const apiKeyListResponse = await context.request.get(
    `${langflowBrowserUrl}/api/v1/api_key/`,
  );
  assert(apiKeyListResponse.status() === 200, "Langflow API-key list failed");
  const apiKeyList = await apiKeyListResponse.json();
  const currentApiKey = (apiKeyList.api_keys || []).find(
    (candidate) => String(candidate.name || "") === apiKeyName,
  );
  apiKeyId = String(currentApiKey?.id || "");
  assert(apiKeyId, "Generated Langflow API key was not found by its exact name");
  for (const candidate of apiKeyList.api_keys || []) {
    const candidateName = String(candidate.name || "");
    const isPlaygroundValidationKey =
      candidateName.startsWith("BoI Agent Playground SSO ")
      || candidateName.startsWith("BoI Agent Playground SSO debug");
    if (!isPlaygroundValidationKey || String(candidate.id || "") === apiKeyId) continue;
    const deleted = await context.request.delete(
      `${langflowBrowserUrl}/api/v1/api_key/${encodeURIComponent(candidate.id)}`,
    );
    assert(
      deleted.status() === 200,
      `Redundant Langflow API key cleanup failed for ${candidate.id}`,
    );
    result.redundant_api_keys_removed += 1;
  }
  await langflowPage.reload({ waitUntil: "domcontentloaded" });
  await waitForLangflow(langflowPage);
  await langflowPage.getByText(apiKeyName, { exact: true }).waitFor({
    state: "visible",
    timeout: 15_000,
  });
  await capture(langflowPage, "langflow-standard-api-key-created");
  // Stop background settings/catalog polling before the SQLite validation
  // fallback performs the bootstrap transaction sequence.
  await langflowPage.close();

  const connect = await boiPage.evaluate(
    async ({ key, baseUrl }) => {
      const before = await (await fetch("/api/agent-playground")).json();
      const endpointId =
        before.default_endpoint_id || before.endpoints?.[0]?.endpoint_id || "";
      const method = endpointId ? "PATCH" : "POST";
      const url = endpointId
        ? `/api/agent-playground/endpoints/${encodeURIComponent(endpointId)}`
        : "/api/agent-playground/endpoints";
      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "Langflow 1.11 · Company SSO",
          base_url: baseUrl,
          api_key: key,
          make_default: true,
        }),
      });
      return {
        status: response.status,
        body: await response.json(),
        submitted_key: key,
      };
    },
    { key: apiKey, baseUrl: langflowDeployUrl },
  );
  assert(connect.status === 200, `Playground connect failed: ${JSON.stringify(connect.body)}`);
  const publicConnect = JSON.stringify(connect.body);
  assert(!publicConnect.includes(apiKey), "Playground response exposed the API key");
  assert(connect.body.endpoint?.has_api_key === true, "Playground did not retain the API key");
  result.api_key_response_redacted = true;
  result.endpoint_owner = String(connect.body.endpoint?.langflow_username || "");
  assert(result.endpoint_owner === employeeId, "API-key owner does not match SSO principal");

  const browserWhoami = await context.request.get(
    `${langflowBrowserUrl}/api/v1/users/whoami`,
  );
  const browserUser = await browserWhoami.json();
  assert(browserWhoami.status() === 200, "Langflow browser whoami failed");
  result.browser_owner = String(browserUser.username || "");
  assert(result.browser_owner === employeeId, "Browser Langflow owner mismatch");

  const verify = await boiPage.evaluate(
    async ({ endpointId, username, userId }) => {
      const response = await fetch("/api/agent-playground/browser-sso/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          endpoint_id: endpointId,
          langflow_username: username,
          langflow_user_id: userId,
        }),
      });
      return { status: response.status, body: await response.json() };
    },
    {
      endpointId: String(connect.body.endpoint?.endpoint_id || ""),
      username: result.browser_owner,
      userId: String(browserUser.id || ""),
    },
  );
  assert(verify.status === 200, `Browser SSO verification failed: ${JSON.stringify(verify.body)}`);
  assert(verify.body.browser_sso?.status === "ready", "Browser SSO is not ready");

  const bootstrap = await boiPage.evaluate(async (endpointId) => {
    const response = await fetch("/api/agent-playground/bootstrap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint_id: endpointId }),
    });
    return { status: response.status, body: await response.json() };
  }, String(connect.body.endpoint?.endpoint_id || ""));
  assert(bootstrap.status === 200, `Bootstrap failed: ${JSON.stringify(bootstrap.body)}`);

  const state = await boiPage.evaluate(async () => {
    return (await fetch("/api/agent-playground")).json();
  });
  const endpointId = String(connect.body.endpoint?.endpoint_id || "");
  const setup = state.endpoint_setups?.[endpointId] || state.onboarding || {};
  const project = setup.project || state.project || {};
  const flow = setup.recommended_flow || setup.canonical_flow || {};
  result.project_name = String(project.name || setup.project_name || "");
  result.recommended_flow = String(flow.name || "");
  const readinessChecks = setup.readiness?.checks || {};
  result.preview_smoke = readinessChecks.preview_smoke ? "passed" : "failed";
  result.recommended_smoke = readinessChecks.recommended_smoke ? "passed" : "failed";
  assert(result.project_name === `boi-${employeeId}`, "Personal project was not bootstrapped");
  assert(
    result.recommended_flow === "BoI Universal Simulation MCP",
    "Recommended Universal Simulation Flow was not bootstrapped",
  );
  assert(result.preview_smoke === "passed", "Canonical preview smoke did not pass");
  assert(result.recommended_smoke === "passed", "Recommended Flow preview smoke did not pass");
  assert(
    state.browser_sso?.status === "ready",
    "Playground state lost browser SSO readiness",
  );

  await boiPage.goto(`${boiUrl}/playground`, { waitUntil: "domcontentloaded" });
  await boiPage.locator("[data-agent-playground]").waitFor({ state: "visible" });
  await boiPage.waitForFunction(
    () => (
      document.querySelector("[data-browser-sso-status]")?.textContent || ""
    ).includes("회사 SSO 준비됨"),
    undefined,
    { timeout: 30_000 },
  );
  await capture(boiPage, "playground-onboarding-complete");

  const secretNeedles = ["api_key", "access_token", "refresh_token"];
  const stateText = JSON.stringify(state).toLowerCase();
  for (const needle of secretNeedles) {
    assert(
      !stateText.includes(`${needle}\":\"sk-`),
      `Playground state contains a secret-looking ${needle}`,
    );
  }
  assert(result.unexpected_http_errors.length === 0, "Unexpected HTTP errors were detected");
  assert(result.console_errors.length === 0, "Unexpected console errors were detected");
  assert(result.page_errors.length === 0, "Unexpected page errors were detected");
  result.ok = true;
} catch (error) {
  result.error = String(error && error.stack ? error.stack : error);
  await capture(boiPage, "failure").catch(() => null);
  if (!langflowPage.isClosed()) {
    const visibleText = await langflowPage.locator("body").innerText().catch(() => "");
    if (!/\bsk-[A-Za-z0-9_-]+\b/.test(visibleText)) {
      await capture(langflowPage, "langflow-failure").catch(() => null);
    }
  }
  throw error;
} finally {
  apiKey = "";
  await fs.writeFile(
    path.resolve(evidenceDir, "result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
  );
  await context.close();
  await browser.close();
}

console.log(JSON.stringify(result, null, 2));
