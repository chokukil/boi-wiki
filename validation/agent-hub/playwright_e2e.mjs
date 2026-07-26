#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import crypto from "node:crypto";
import { createRequire } from "node:module";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const require = createRequire(import.meta.url);

function loadPlaywright() {
  try {
    return require("playwright");
  } catch (error) {
    const explicit = process.env.PLAYWRIGHT_MODULE_PATH;
    if (!explicit) {
      throw new Error(
        "playwright is not installed. Run npm install, or set PLAYWRIGHT_MODULE_PATH to an installed playwright package.",
        { cause: error },
      );
    }
    return require(explicit);
  }
}

const { chromium } = loadPlaywright();
const execFileAsync = promisify(execFile);
const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");

const config = {
  agentHubUrl: process.env.AGENT_HUB_URL || "http://localhost:18080/AgentHub.html",
  agentHubUsername: process.env.AGENT_HUB_USERNAME || "100002",
  agentHubPassword: process.env.AGENT_HUB_PASSWORD || "",
  boiViewerPassword:
    process.env.BOI_VIEWER_PASSWORD || process.env.AGENT_HUB_PASSWORD || "",
  langflowApiKey: process.env.LANGFLOW_API_KEY || "",
  langflowPassword: process.env.LANGFLOW_PASSWORD || "",
  langflowEndpointForAgentHub:
    process.env.LANGFLOW_ENDPOINT_FOR_AGENT_HUB || "http://host.docker.internal:7867",
  langflowEndpointForPlayground:
    process.env.LANGFLOW_ENDPOINT_FOR_PLAYGROUND || "http://host.docker.internal:7867",
  langflowBrowserUrl:
    process.env.LANGFLOW_BROWSER_URL
    || process.env.LANGFLOW_ENDPOINT_FOR_PLAYGROUND
    || "http://localhost:7867",
  playgroundUrl:
    process.env.AGENT_PLAYGROUND_URL || "http://localhost:28005/playground",
  boiBaseUrl: process.env.BOI_BASE_URL || "http://localhost:28005",
  boiActionUrl:
    process.env.BOI_ACTION_URL ||
    "http://localhost:28005/actions",
  boiActionKey:
    process.env.BOI_ACTION_KEY || "",
  boiFlowId:
    process.env.BOI_FLOW_ID || "",
  keycloakUrl: process.env.KEYCLOAK_URL || "http://localhost:18082",
  validationRuntimeRoot:
    process.env.BOI_VALIDATION_RUNTIME_ROOT || "/tmp/boi-agent-playground-validation/runtime",
  validationCatalogRoot:
    process.env.BOI_VALIDATION_CATALOG_ROOT || "/tmp/boi-agent-playground-validation/action_catalog",
  validationContainer:
    process.env.BOI_VALIDATION_CONTAINER || "boi-agent-playground-mainline-boi-api-1",
  flowJson:
    process.env.FLOW_JSON_PATH || path.join(repoRoot, "langflow/flows/boi_wiki_agent_loop.json"),
  evidenceDir:
    process.env.PLAYWRIGHT_EVIDENCE_DIR ||
    "/tmp/boi-agent-playground-validation/evidence/browser-playwright",
  playwrightModulePath: process.env.PLAYWRIGHT_MODULE_PATH || "",
  chromiumExecutable: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || "",
};

for (const [name, value] of Object.entries({
  AGENT_HUB_PASSWORD: config.agentHubPassword,
  LANGFLOW_API_KEY: config.langflowApiKey,
  LANGFLOW_PASSWORD: config.langflowPassword,
})) {
  if (!value) throw new Error(`${name} is required`);
}

const runId =
  process.env.PLAYWRIGHT_RUN_ID ||
  new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 14);
const endpointAlias = process.env.PLAYWRIGHT_ENDPOINT_ALIAS || "Playwright Langflow 1.11";
const assetTitle = process.env.PLAYWRIGHT_ASSET_TITLE || `BoI Wiki Agent Loop Browser ${runId}`;
const result = {
  run_id: runId,
  runner: "standalone-playwright",
  playwright_version: require(
    path.join(
      config.playwrightModulePath || path.dirname(require.resolve("playwright")),
      "package.json",
    ),
  ).version,
  started_at: new Date().toISOString(),
  agent_hub: {},
  langflow: {},
  playground: {},
  boi_action: {},
  screenshots: [],
  console_errors: [],
  ignored_console_warnings: [],
  ignored_auth_bootstrap_errors: [],
  page_errors: [],
  http_errors: [],
  passed: false,
};

await fs.mkdir(config.evidenceDir, { recursive: true });

function safeUrl(raw) {
  const url = new URL(raw);
  url.username = "";
  url.password = "";
  url.search = "";
  return url.toString();
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function screenshot(page, name, options = {}) {
  const target = path.join(config.evidenceDir, `${name}.png`);
  await page.screenshot({ path: target, fullPage: true, ...options });
  result.screenshots.push(target);
  return target;
}

async function attachDiagnostics(page, scope) {
  page.on("console", (message) => {
    if (message.type() === "error") {
      const text = message.text();
      // HTTP failures are collected with URL and status by the response
      // listener below. Chromium's generic console duplicate has no target
      // information and would turn expected 401/403 policy checks into noise.
      if (text.startsWith("Duplicate request:")) {
        result.ignored_console_warnings.push({
          scope,
          reason: "unmodified Langflow frontend duplicate-request guard",
          text: text.slice(0, 500),
        });
      } else if (!text.includes("favicon") && !text.startsWith("Failed to load resource:")) {
        result.console_errors.push({ scope, text: text.slice(0, 500) });
      }
    }
  });
  page.on("pageerror", (error) => {
    result.page_errors.push({ scope, text: String(error.message || error).slice(0, 500) });
  });
  page.on("response", (response) => {
    if (response.status() < 400) return;
    const url = new URL(response.url());
    result.http_errors.push({
      scope,
      status: response.status(),
      method: response.request().method(),
      url: `${url.origin}${url.pathname}`,
    });
  });
}

async function loginAgentHub(page) {
  await page.goto(config.agentHubUrl, { waitUntil: "domcontentloaded" });
  const agentHubOrigin = new URL(config.agentHubUrl).origin;
  const hasToken = await page.evaluate(() => Boolean(localStorage.getItem("agenthub_token")));
  if (page.url().startsWith(agentHubOrigin) && !hasToken) {
    await page.waitForURL((url) => url.origin !== agentHubOrigin, { timeout: 20_000 });
  }

  if (page.url().includes("/protocol/openid-connect/")) {
    await page.locator("#username").fill(config.agentHubUsername);
    await page.locator("#password").fill(config.agentHubPassword);
    await Promise.all([
      page.waitForURL((url) => url.origin === new URL(config.agentHubUrl).origin),
      page.locator("#kc-login").click(),
    ]);
  }

  await page.locator("button.topbar-submit").waitFor({ state: "visible", timeout: 30_000 });
  await page.waitForFunction(() => Boolean(localStorage.getItem("agenthub_token")), null, {
    timeout: 30_000,
  });
  const tokenPrincipal = await page.evaluate(() => {
    const token = localStorage.getItem("agenthub_token");
    if (!token) return {};
    const payload = JSON.parse(atob(token.split(".")[1]));
    return {
      employee_id: Array.isArray(payload.empno) ? payload.empno[0] : payload.empno,
      preferred_username: payload.preferred_username,
    };
  });
  const apiPrincipal = await page.evaluate(async () => {
    const token = localStorage.getItem("agenthub_token");
    const response = await fetch("/api/v1/users/me", {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) throw new Error(`users/me returned ${response.status}`);
    return response.json();
  });
  const principal = {
    employee_id:
      apiPrincipal.employee_id ||
      apiPrincipal.employee_number ||
      apiPrincipal.empno ||
      apiPrincipal.username ||
      tokenPrincipal.employee_id ||
      tokenPrincipal.preferred_username,
    display_name: apiPrincipal.name || apiPrincipal.display_name || "",
    role: apiPrincipal.role || "",
  };
  assert(
    String(principal.employee_id || principal.preferred_username) === config.agentHubUsername,
    "Agent Hub SSO principal did not resolve to the expected employee",
  );
  result.agent_hub.sso_principal = principal;
  result.agent_hub.url = safeUrl(page.url());
  await screenshot(page, "01-agent-hub-sso");
}

async function loginBoi(page, targetUrl, username = config.agentHubUsername) {
  const boiOrigin = new URL(config.boiBaseUrl).origin;
  await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
  if (page.url().startsWith(boiOrigin) && page.url().includes("/auth/login")) {
    await page.waitForURL((url) => url.origin !== boiOrigin, { timeout: 20_000 });
  }
  if (page.url().includes("/protocol/openid-connect/")) {
    const authorizationUrl = new URL(page.url());
    const state = authorizationUrl.searchParams.get("state");
    const nonce = authorizationUrl.searchParams.get("nonce");
    const codeChallenge = authorizationUrl.searchParams.get("code_challenge");
    const codeChallengeMethod = authorizationUrl.searchParams.get("code_challenge_method");
    const stateCookies = await page.context().cookies(config.boiBaseUrl);
    const stateCookie = stateCookies.find((cookie) => cookie.name === "boi_oidc_state");
    assert(Boolean(state), "BoI OIDC authorization request did not include state");
    assert(Boolean(nonce), "BoI OIDC authorization request did not include nonce");
    assert(Boolean(codeChallenge), "BoI OIDC authorization request did not include a PKCE code challenge");
    assert(codeChallengeMethod === "S256", `Unexpected BoI PKCE method: ${codeChallengeMethod}`);
    assert(Boolean(stateCookie), "BoI OIDC state cookie was not issued before redirect");
    assert(stateCookie.httpOnly === true, "BoI OIDC state cookie is not HttpOnly");
    if (username === config.agentHubUsername) {
      result.boi_oidc = {
        authorization_endpoint: authorizationUrl.pathname,
        state_present: true,
        nonce_present: true,
        pkce_challenge_present: true,
        pkce_method: codeChallengeMethod,
        state_cookie_issued: true,
        state_cookie_http_only: true,
      };
    }
    await page.locator("#username").fill(username);
    await page
      .locator("#password")
      .fill(
        username === config.agentHubUsername
          ? config.agentHubPassword
          : config.boiViewerPassword,
      );
    await Promise.all([
      page.waitForURL((url) => url.origin === boiOrigin, { timeout: 30_000 }),
      page.locator("#kc-login").click(),
    ]);
  }
  assert(
    new URL(page.url()).origin === boiOrigin,
    `BoI OIDC callback did not return to ${boiOrigin}`,
  );
  if (new URL(page.url()).pathname === "/auth/callback") {
    const callbackDetail = (await page.locator("body").innerText()).slice(0, 1000);
    throw new Error(`BoI OIDC callback failed: ${callbackDetail}`);
  }
  const callbackCookies = await page.context().cookies(config.boiBaseUrl);
  const sessionCookie = callbackCookies.find((cookie) => cookie.name === "boi_session");
  const remainingStateCookie = callbackCookies.find((cookie) => cookie.name === "boi_oidc_state");
  assert(Boolean(sessionCookie), "BoI session cookie was not issued after OIDC callback");
  assert(sessionCookie.httpOnly === true, "BoI session cookie is not HttpOnly");
  assert(!remainingStateCookie, "BoI OIDC state cookie remained after successful callback");
  if (username === config.agentHubUsername && result.boi_oidc) {
    result.boi_oidc.callback_completed = true;
    result.boi_oidc.state_cookie_consumed = true;
    result.boi_oidc.session_cookie_issued = true;
    result.boi_oidc.session_cookie_http_only = true;
  }
  const identity = await page.evaluate(async () => {
    const response = await fetch("/api/agent-playground");
    return { status: response.status, body: await response.json() };
  });
  assert(identity.status === 200, `BoI session identity returned HTTP ${identity.status}`);
  assert(identity.body?.identity?.employee_id === username, "BoI SSO principal did not resolve empno");
  assert(identity.body?.identity?.auth_source === "keycloak", "BoI browser did not use the Keycloak session");
  const spoofEmployee = username === "100003" ? "100002" : "100003";
  const spoof = await page.evaluate(async (employeeId) => {
    const response = await fetch(`/api/agent-playground?employee_id=${encodeURIComponent(employeeId)}`);
    return response.status;
  }, spoofEmployee);
  assert(spoof === 403, `BoI SSO employee spoof returned HTTP ${spoof}`);
  const ssoEvidence = {
    employee_id: identity.body.identity.employee_id,
    auth_source: identity.body.identity.auth_source,
    roles: identity.body.identity.roles,
    teams: identity.body.identity.teams,
    query_spoof_status: spoof,
  };
  if (username === config.agentHubUsername) result.boi_sso = ssoEvidence;
  else result.boi_sso_viewer = ssoEvidence;
}

async function resetViewerPassword() {
  const password = crypto.randomBytes(24).toString("base64url");
  const tokenResponse = await fetch(
    `${config.keycloakUrl}/realms/master/protocol/openid-connect/token`,
    {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "password",
        client_id: "admin-cli",
        username: "validation-admin",
        password: "validation-admin",
      }),
    },
  );
  assert(tokenResponse.ok, `Keycloak admin login returned ${tokenResponse.status}`);
  const adminToken = (await tokenResponse.json()).access_token;
  const usersResponse = await fetch(
    `${config.keycloakUrl}/admin/realms/boi-validation/users?username=100003&exact=true`,
    { headers: { Authorization: `Bearer ${adminToken}` } },
  );
  assert(usersResponse.ok, `Keycloak viewer lookup returned ${usersResponse.status}`);
  const user = (await usersResponse.json())[0];
  assert(user?.id, "Keycloak 100003 fixture is missing");
  const resetResponse = await fetch(
    `${config.keycloakUrl}/admin/realms/boi-validation/users/${user.id}/reset-password`,
    {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${adminToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        type: "password",
        value: password,
        temporary: false,
      }),
    },
  );
  assert(resetResponse.status === 204, `Keycloak viewer reset returned ${resetResponse.status}`);
  return password;
}

async function uploadFlow(page) {
  await page.locator("button.topbar-submit").click();
  const modal = page.locator(".modal").filter({ hasText: "새 Component / Flow 제출" });
  await modal.waitFor();

  const chooserPromise = page.waitForEvent("filechooser");
  await modal.locator(".dropzone").click();
  const chooser = await chooserPromise;
  await chooser.setFiles(config.flowJson);
  await modal.getByText(path.basename(config.flowJson), { exact: true }).waitFor();
  await modal.getByRole("button", { name: /^다음/ }).click();

  const titleInput = modal.locator("input.input").nth(0);
  const descriptionInput = modal.locator("input.input").nth(1);
  await titleInput.fill(assetTitle);
  await descriptionInput.fill("BoI Wiki와 Ontology 근거를 활용하는 Agent Playground 기준 Flow입니다.");
  const readme = modal.locator("textarea.input");
  await readme.fill(
    [
      "## 개요",
      "",
      "BoI Wiki Agent Loop 1.1.0을 Agent Hub에서 개인 Langflow 프로젝트로 배포합니다.",
      "",
      "## 검증",
      "",
      "- Wiki 문서와 Ontology provenance를 함께 확인합니다.",
      "- 기본 저장 모드는 preview이며 private draft는 명시적으로만 사용합니다.",
      "- API Key와 BoI PAT는 Flow JSON에 포함하지 않습니다.",
    ].join("\n"),
  );
  await modal.getByRole("button", { name: /^다음/ }).click();

  const compatibilitySelects = modal.locator("select.select");
  if ((await compatibilitySelects.count()) >= 2) {
    await compatibilitySelects.nth(1).selectOption({ index: 0 });
  }

  const responsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v1\/components\/?$/.test(new URL(response.url()).pathname),
  );
  await modal.getByRole("button", { name: "제출하기" }).click();
  const response = await responsePromise;
  assert(response.ok(), `Agent Hub upload failed with HTTP ${response.status()}`);
  const payload = await response.json();
  const assetId = payload.id || payload.component_id || payload.component?.id;
  assert(assetId, "Agent Hub upload response did not include an asset ID");
  result.agent_hub.asset_id = assetId;
  result.agent_hub.asset_title = assetTitle;

  await page.getByText("제출 완료", { exact: false }).waitFor({ timeout: 15_000 });
  await page.locator(".modal-backdrop").waitFor({ state: "detached", timeout: 15_000 });
  await page.goto(`${config.agentHubUrl}#/flow/${assetId}`, { waitUntil: "domcontentloaded" });
  await page.locator(".detail-title", { hasText: assetTitle }).waitFor({ timeout: 20_000 });
  await screenshot(page, "02-agent-hub-flow-detail");
  return assetId;
}

async function configureAgentHubEndpoint(modal) {
  const loading = modal.getByText("불러오는 중…", { exact: true });
  if (await loading.count()) {
    await loading.waitFor({ state: "detached", timeout: 30_000 });
  }
  const endpointNames = modal.getByText(endpointAlias, { exact: true });
  let duplicateCount = await endpointNames.count();
  let cleanedEndpoints = 0;
  while (duplicateCount > 1) {
    const duplicateCard = endpointNames
      .first()
      .locator('xpath=ancestor::div[.//input[@type="radio"]][1]');
    const deleteResponse = modal.page().waitForResponse(
      (response) =>
        response.request().method() === "DELETE" &&
        /\/api\/v1\/deploy\/endpoints\/[^/]+$/.test(new URL(response.url()).pathname),
    );
    modal.page().once("dialog", (dialog) => dialog.accept());
    await duplicateCard.getByRole("button", { name: "삭제" }).click();
    const deleted = await deleteResponse;
    assert(deleted.ok(), `Agent Hub endpoint cleanup returned HTTP ${deleted.status()}`);
    cleanedEndpoints += 1;
    await modal.page().waitForFunction(
      ({ alias, expected }) =>
        [...document.querySelectorAll(".modal")]
          .flatMap((element) => [...element.querySelectorAll("div")])
          .filter((element) => element.textContent?.trim() === alias).length <= expected,
      { alias: endpointAlias, expected: duplicateCount - 1 },
      { timeout: 15_000 },
    );
    duplicateCount = await endpointNames.count();
  }
  result.agent_hub.cleaned_duplicate_endpoints = cleanedEndpoints;
  const existing = endpointNames
    .last()
    .locator('xpath=ancestor::div[.//input[@type="radio"]][1]');

  if (await endpointNames.count()) {
    await existing.getByRole("button", { name: "수정" }).click();
  } else {
    await modal.getByRole("button", { name: /엔드포인트 추가/ }).click();
  }

  const form = modal.locator(".card.card-pad").filter({ hasText: "API Key" }).last();
  await form.waitFor();
  const textInputs = form.locator('input:not([type="checkbox"]):not([type="password"])');
  assert((await textInputs.count()) >= 2, "Agent Hub endpoint form inputs were not found");
  await textInputs.nth(0).fill(endpointAlias);
  await textInputs.nth(1).fill(config.langflowEndpointForAgentHub);
  const apiKeyInput = form.locator('input[type="password"]');
  await apiKeyInput.fill(`invalid-playwright-${runId}`);
  const rejectedResponsePromise = modal.page().waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname.endsWith("/api/v1/deploy/test"),
  );
  await form.getByRole("button", { name: "연결 테스트" }).click();
  const rejectedResponse = await rejectedResponsePromise;
  assert(rejectedResponse.ok(), `Invalid Agent Hub endpoint test returned HTTP ${rejectedResponse.status()}`);
  const rejectedPayload = await rejectedResponse.json();
  assert(rejectedPayload.ok === false, "Agent Hub accepted a deliberately invalid API key");
  await form.getByText("실패", { exact: true }).waitFor({ timeout: 30_000 });
  result.agent_hub.invalid_endpoint_test = "rejected";

  await apiKeyInput.fill(config.langflowApiKey);
  await form.getByRole("button", { name: "연결 테스트" }).click();
  await form.getByText(/Agent Builder 1\.11\./).waitFor({ timeout: 30_000 });
  result.agent_hub.endpoint_test = "Langflow 1.11 connected";
  await form.getByRole("button", { name: "저장" }).click();
  await form.waitFor({ state: "detached", timeout: 15_000 });

  const saved = modal
    .getByText(endpointAlias, { exact: true })
    .last()
    .locator('xpath=ancestor::div[.//input[@type="radio"]][1]');
  await saved.waitFor();
  assert((await saved.innerText()).includes(endpointAlias), "Saved endpoint was not selected in Agent Hub");
  await saved.click();
  const savedEndpointTest = modal.page().waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v1\/deploy\/endpoints\/[^/]+\/test$/.test(new URL(response.url()).pathname),
  );
  await saved.getByRole("button", { name: "연결 테스트" }).click();
  const savedEndpointResponse = await savedEndpointTest;
  assert(savedEndpointResponse.ok(), `Saved Agent Hub endpoint test returned HTTP ${savedEndpointResponse.status()}`);
  const savedEndpointPayload = await savedEndpointResponse.json();
  assert(savedEndpointPayload.ok === true, "Saved Agent Hub endpoint test did not return ok=true");
  await pageWaitForEndpointState(saved);
  return saved;
}

async function pageWaitForEndpointState(card) {
  await card.getByText(/^(정상|OK)$/).waitFor({ timeout: 10_000 });
}

async function deployFlow(page) {
  await page.locator(".detail-actions").getByRole("button", { name: "배포" }).click();
  const modal = page.locator(".modal").filter({ hasText: "Agent Builder에 배포" });
  await modal.waitFor();
  await configureAgentHubEndpoint(modal);

  const projectSelect = modal.locator("select.select").last();
  await projectSelect.waitFor({ state: "visible", timeout: 30_000 });
  await projectSelect.selectOption({ label: "boi-100002" });
  result.agent_hub.project = "boi-100002";

  await screenshot(page, "03-agent-hub-deploy-modal-connected");
  const responsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v1\/deploy\/components\/[^/]+$/.test(new URL(response.url()).pathname),
  );
  await modal.locator(".modal-footer").getByRole("button", { name: "배포", exact: true }).click();
  const response = await responsePromise;
  assert(response.ok(), `Agent Hub deploy failed with HTTP ${response.status()}`);
  const payload = await response.json();
  await modal.getByText("배포 완료!", { exact: true }).waitFor({ timeout: 60_000 });
  const openLink = modal.getByRole("link", { name: "Agent Builder에서 열기" });
  const flowUrl = (await openLink.getAttribute("href")) || payload.flow_url;
  assert(flowUrl, "Agent Hub deploy result did not include a Flow URL");
  const flowId = String(payload.flow_id || new URL(flowUrl).pathname.split("/").filter(Boolean).at(-1));
  assert(flowId, "Agent Hub deploy result did not include a Flow ID");
  result.agent_hub.deployment = {
    flow_id: flowId,
    flow_url: safeUrl(flowUrl),
    name: payload.name || assetTitle,
  };
  await screenshot(page, "04-agent-hub-deploy-success");
  return { flowId, flowUrl };
}

async function verifyLangflowCanvas(browser, flowId, flowUrl) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  await attachDiagnostics(page, "langflow");
  const consoleErrorStart = result.console_errors.length;
  const httpErrorStart = result.http_errors.length;
  const publicUrl = new URL(flowUrl);
  publicUrl.protocol = new URL(config.langflowBrowserUrl).protocol;
  publicUrl.host = new URL(config.langflowBrowserUrl).host;
  await page.goto(publicUrl.toString(), { waitUntil: "domcontentloaded" });

  const passwordInput = page.locator('input[type="password"]');
  const loginVisible = await passwordInput
    .waitFor({ state: "visible", timeout: 20_000 })
    .then(() => true)
    .catch(() => false);
  if (loginVisible) {
    const userInput = page.locator('input[name="username"], input[type="text"]').first();
    await userInput.fill(config.agentHubUsername);
    await passwordInput.fill(config.langflowPassword);
    const loginResponsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === "POST"
        && /\/api\/v1\/login\/?$/.test(new URL(response.url()).pathname),
      { timeout: 30_000 },
    );
    await page.getByRole("button", { name: "Sign In", exact: true }).click();
    const loginResponse = await loginResponsePromise;
    assert(loginResponse.ok(), `Langflow sign-in returned HTTP ${loginResponse.status()}`);
    await passwordInput.waitFor({ state: "hidden", timeout: 30_000 });
    await page.waitForFunction(async () => {
      try {
        return (await fetch("/api/v1/users/whoami")).ok;
      } catch {
        return false;
      }
    }, null, { timeout: 30_000 });
    await page.goto(publicUrl.toString(), { waitUntil: "domcontentloaded" });
    const preAuthConsoleErrors = result.console_errors
      .slice(consoleErrorStart)
      .filter(
        (entry) =>
          entry.scope === "langflow"
          && entry.text.startsWith("AxiosError: Request failed with status code "),
      );
    const preAuthHttpErrors = result.http_errors
      .slice(httpErrorStart)
      .filter(
        (entry) =>
          entry.scope === "langflow"
          && [401, 403].includes(entry.status)
          && [
            "/api/v1/auto_login",
            "/api/v1/refresh",
            "/api/v1/users/whoami",
            "/api/v1/projects/",
            "/api/v1/variables/",
            "/api/v1/all",
          ].includes(new URL(entry.url).pathname),
      );
    result.ignored_auth_bootstrap_errors.push(
      ...preAuthConsoleErrors.map((entry) => ({ ...entry, kind: "console" })),
      ...preAuthHttpErrors.map((entry) => ({ ...entry, kind: "http" })),
    );
    result.console_errors = result.console_errors.filter(
      (entry, index) =>
        index < consoleErrorStart || !preAuthConsoleErrors.includes(entry),
    );
    result.http_errors = result.http_errors.filter(
      (entry, index) =>
        index < httpErrorStart || !preAuthHttpErrors.includes(entry),
    );
  }

  await page.waitForTimeout(5000);
  const body = (await page.locator("body").innerText()).slice(0, 20_000);
  await screenshot(page, "05-langflow-deployed-flow");
  assert(
    body.includes(assetTitle) || body.includes("BoI Wiki Agent Loop") || page.url().includes(flowId),
    "Langflow browser page did not show the deployed Flow",
  );
  result.langflow = {
    flow_id: flowId,
    url: safeUrl(page.url()),
    visible_name: body.includes(assetTitle) ? assetTitle : "BoI Wiki Agent Loop",
  };
  await context.close();
}

async function ensurePlaygroundEndpoint(root) {
  await root.locator('[data-workbench-step="create"]').click();
  const connectionSettings = root.locator(
    "details.agent-playground-connection-settings[data-workbench-only]",
  );
  if (!(await connectionSettings.evaluate((element) => element.open))) {
    await connectionSettings.locator("summary").click();
  }
  await root.locator("[data-endpoint-list] .agent-playground-limit").waitFor({
    state: "attached",
    timeout: 30_000,
  });
  const endpointItems = root.locator("[data-endpoint-list] [data-endpoint-id]");
  const existingByAlias = endpointItems.filter({ hasText: endpointAlias });
  const existingByUrl = endpointItems.filter({ hasText: config.langflowEndpointForPlayground });
  const existing = (await existingByAlias.count()) ? existingByAlias : existingByUrl;
  if (await existing.count()) {
    if ((await existing.last().getAttribute("data-active")) !== "true") {
      await existing.last().click();
    }
    await root.locator("[data-endpoint-summary]").getByRole("button", { name: "수정" }).click();
  } else {
    await root.locator("[data-new-endpoint]").click();
  }

  const form = root.locator("[data-endpoint-form]");
  await form.waitFor({ state: "visible" });
  await form.locator('[name="name"]').fill(endpointAlias);
  await form.locator('[name="base_url"]').fill(config.langflowEndpointForPlayground);
  await form.locator('[name="api_key"]').fill(config.langflowApiKey);
  await form.locator("[data-test-unsaved]").click();
  await form.locator("[data-endpoint-test-output]").getByText(/1\.11\.0/).waitFor({ timeout: 30_000 });
  const endpointId = await form.locator('[name="endpoint_id"]').inputValue();
  const saveResponse = root.page().waitForResponse(
    (response) => {
      const pathname = new URL(response.url()).pathname;
      return (
        response.request().method() === (endpointId ? "PATCH" : "POST") &&
        (endpointId
          ? pathname.endsWith(`/api/agent-playground/endpoints/${endpointId}`)
          : pathname.endsWith("/api/agent-playground/endpoints"))
      );
    },
  );
  await form.getByRole("button", { name: "저장", exact: true }).click();
  const saved = await saveResponse;
  assert(saved.ok(), `Agent Playground endpoint save returned HTTP ${saved.status()}`);
  await form.waitFor({ state: "hidden", timeout: 20_000 });
  await root.locator("[data-status-card='connection']").getByText(/연결됨|connected/i).waitFor({
    timeout: 20_000,
  });
}

async function verifyPlayground(browser, flowId) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  await attachDiagnostics(page, "playground");
  await loginBoi(page, config.playgroundUrl);
  const root = page.locator("[data-agent-playground]");
  await root.waitFor();
  await root.locator("[data-auth-source]").getByText(/keycloak/i).waitFor({ timeout: 20_000 });
  await root.locator(".agent-playground-identity strong").getByText("100002", { exact: true }).waitFor({
    timeout: 20_000,
  });
  await screenshot(page, "05b-boi-sso-playground");

  // A newer repository artifact can intentionally reopen onboarding for an
  // already connected endpoint. Resume the idempotent setup before entering
  // the workbench instead of treating the hidden endpoint list as a failure.
  const onboarding = root.locator("[data-onboarding]");
  if (await onboarding.isVisible()) {
    const bootstrap = root.locator("[data-onboarding-bootstrap]");
    const finish = root.locator("[data-onboarding-finish]");
    await page.waitForFunction(
      () => {
        const visible = (selector) => {
          const element = document.querySelector(selector);
          return Boolean(element && !element.hidden && element.getClientRects().length);
        };
        return (
          visible("[data-onboarding-bootstrap]") ||
          visible("[data-onboarding-finish]") ||
          !visible("[data-onboarding]")
        );
      },
      null,
      { timeout: 30_000 },
    );
    if (await bootstrap.isVisible().catch(() => false)) {
      await bootstrap.click();
      await root
        .locator('[data-onboarding-stage="flow"]')
        .waitFor({ state: "visible", timeout: 120_000 });
    }
    if (await finish.isVisible().catch(() => false)) await finish.click();
    await root.locator("[data-workbench-only]").first().waitFor({
      state: "visible",
      timeout: 30_000,
    });
  }

  await ensurePlaygroundEndpoint(root);
  const advanced = root.locator(".agent-playground-advanced");
  if (!(await advanced.evaluate((element) => element.open))) {
    await advanced.locator("summary").click();
  }
  const rotateResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname.endsWith("/api/agent-playground/rotate-credential"),
  );
  await advanced.locator("[data-rotate-credential]").click();
  const rotated = await rotateResponse;
  assert(rotated.ok(), `BoI knowledge credential rotation returned HTTP ${rotated.status()}`);
  await root.locator("[data-playground-toast]").getByText(/BoI PAT를 원자적으로 교체/).waitFor({
    timeout: 30_000,
  });
  result.playground.credential_rotation = "passed";
  const projectSelect = root.locator("[data-project-select]");
  await projectSelect.waitFor({ state: "visible", timeout: 30_000 });
  await projectSelect.selectOption({ label: "boi-100002" });
  await root.locator("[data-refresh-flows]").click();

  const flowButton = root.locator("[data-flow-list] .agent-playground-flow-item").filter({ hasText: flowId });
  await flowButton.waitFor({ timeout: 30_000 });
  await flowButton.click();
  await root.page().waitForFunction(
    (expectedFlowId) =>
      document.querySelector("[data-selected-flow-id]")?.textContent?.trim() === expectedFlowId,
    flowId,
    { timeout: 30_000 },
  );
  result.playground.rediscovered_flow_id = flowId;
  result.playground.endpoint_alias = endpointAlias;
  result.playground.project = "boi-100002";
  await screenshot(page, "06-playground-rediscovered-desktop");
  await screenshot(page, "06b-playground-rediscovered-viewport", { fullPage: false });

  await root.locator('[data-workbench-step="hub"]').click();
  const recordButton = root.locator("[data-record-deployment]");
  if (await recordButton.isEnabled()) {
    await recordButton.click();
    await root.locator("[data-playground-toast]").getByText(/exact ID로 연결/).waitFor({ timeout: 30_000 });
  }

  await root.locator('[data-workbench-step="test"]').click();
  const taskSelect = root.locator("[data-task-select]");
  await taskSelect.waitFor({ state: "visible" });
  await root.page().waitForFunction(
    () => (document.querySelector("[data-task-select]")?.options?.length || 0) > 1,
    null,
    { timeout: 30_000 },
  );
  const selectedTaskRef = await taskSelect.locator("option").nth(1).getAttribute("value");
  assert(
    Boolean(String(selectedTaskRef || "").trim()),
    "ACL-checked Task selector did not provide an actual Task anchor",
  );
  await taskSelect.selectOption(String(selectedTaskRef));
  result.playground.task_anchor = {
    source: "acl_inbox_selector",
    task_ref: selectedTaskRef,
  };

  const validateButton = root.locator("[data-validate-flow]");
  await validateButton.waitFor({ state: "visible" });
  await root.page().waitForFunction(
    () => !document.querySelector("[data-validate-flow]")?.disabled,
    null,
    { timeout: 30_000 },
  );
  assert(await validateButton.isEnabled(), "Flow validation button is disabled after deployment registration");
  await validateButton.click();
  await root.locator("[data-playground-toast]").getByText(/action_ready 검증을 통과/).waitFor({
    timeout: 90_000,
  });
  await root.locator("[data-selected-flow-status]").getByText("action_ready", { exact: true }).waitFor();
  result.playground.validation_status = "action_ready";
  result.playground.artifact_checksum = (
    (await root.locator("[data-selected-flow-checksum]").textContent()) || ""
  ).trim();
  await screenshot(page, "07-playground-flow-validation");

  const testResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname.endsWith(`/flows/${flowId}/test`),
    { timeout: 240_000 },
  );
  await root.locator("[data-test-form]").getByRole("button", { name: "선택 Flow 테스트" }).click();
  const runtimeResponse = await testResponse;
  assert(runtimeResponse.ok(), `Playground runtime test failed with HTTP ${runtimeResponse.status()}`);
  const runtimePayload = await runtimeResponse.json();
  const runtimeText = JSON.stringify(runtimePayload);
  assert(runtimeText.includes("source_references"), "Runtime result did not include source references");
  assert(runtimeText.includes("ontology"), "Runtime result did not include ontology evidence");
  result.playground.runtime = {
    ok: true,
    has_source_references: true,
    has_ontology: true,
    save_mode: "preview",
  };
  await root.locator("[data-playground-toast]").getByText(/runtime 테스트를 마쳤습니다/).waitFor({
    timeout: 90_000,
  });

  await root.locator('[data-workbench-step="action"]').click();
  const createAction = root.locator("[data-create-action]");
  await root.page().waitForFunction(
    () => !document.querySelector("[data-create-action]")?.disabled,
    null,
    { timeout: 30_000 },
  );
  assert(await createAction.isEnabled(), "Action connection button is disabled after Flow validation");
  const actionResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/agent-playground\/deployments\/[^/]+\/action-draft$/.test(new URL(response.url()).pathname),
  );
  await createAction.click();
  const actionPayloadResponse = await actionResponse;
  assert(actionPayloadResponse.ok(), `Action draft failed with HTTP ${actionPayloadResponse.status()}`);
  const actionPayload = await actionPayloadResponse.json();
  result.playground.action_draft = {
    draft_id: actionPayload.draft?.draft_id,
    draft_url: actionPayload.draft_url,
    flow_id: actionPayload.deployment_reference?.flow_id || flowId,
    deployment_reference: actionPayload.deployment_reference,
  };
  assert(
    actionPayload.deployment_reference?.flow_id === flowId,
    "Action draft did not reference the browser-deployed exact Flow",
  );
  await root.locator("[data-playground-toast]").getByText(/Action 등록 초안/).waitFor({ timeout: 30_000 });

  await screenshot(page, "08-playground-runtime-and-action");
  await screenshot(page, "08b-playground-runtime-viewport", { fullPage: false });

  const reviewPage = await context.newPage();
  await attachDiagnostics(reviewPage, "action-draft-review");
  await reviewPage.goto(new URL(actionPayload.draft_url, config.boiBaseUrl).toString(), {
    waitUntil: "domcontentloaded",
  });
  const review = reviewPage.locator("[data-action-draft-review]");
  await review.waitFor({ timeout: 30_000 });
  await review.locator(".action-draft-reference").getByText(flowId, { exact: true }).waitFor();
  const validateResponsePromise = reviewPage.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname.endsWith(`/registration/drafts/${actionPayload.draft.draft_id}/validate`),
  );
  await review.locator("[data-validate-draft]").click();
  const validateResponse = await validateResponsePromise;
  assert(validateResponse.ok(), `Action registration validation returned HTTP ${validateResponse.status()}`);
  await review.locator("[data-validation-state]").getByText("통과", { exact: true }).waitFor();
  const publishResponsePromise = reviewPage.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname.endsWith(`/registration/drafts/${actionPayload.draft.draft_id}/publish`),
  );
  await review.locator("[data-publish-draft]").click();
  const publishResponse = await publishResponsePromise;
  assert(publishResponse.ok(), `Action registration publish-request returned HTTP ${publishResponse.status()}`);
  const publishPayload = await publishResponse.json();
  assert(publishPayload.draft?.status === "publish_requested", "Action draft did not reach publish_requested");
  assert(publishPayload.draft?.catalog_applied === false, "Publish request modified the catalog directly");
  await review.locator("[data-draft-status]").getByText("publish_requested", { exact: true }).waitFor();
  await screenshot(reviewPage, "08c-action-draft-publish-request");

  const operatorEvidence = path.join(config.evidenceDir, "exact-action-chain-operator.json");
  const operator = await execFileAsync(
    "docker",
    [
      "exec",
      config.validationContainer,
      "python",
      "/workspace/scripts/apply_agent_playground_action_fixture.py",
      "--runtime-root", "/runtime",
      "--catalog-root", "/action_catalog",
      "--employee-id", config.agentHubUsername,
      "--draft-id", actionPayload.draft.draft_id,
    ],
    { cwd: repoRoot, maxBuffer: 1024 * 1024 },
  );
  const operatorPayload = JSON.parse(operator.stdout.trim());
  await fs.writeFile(
    operatorEvidence,
    `${JSON.stringify(operatorPayload, null, 2)}\n`,
    { mode: 0o600 },
  );
  assert(operatorPayload.deployment_reference?.flow_id === flowId, "Operator applied a different Flow");
  config.boiActionKey = operatorPayload.action_key;
  config.boiActionUrl = `${config.boiBaseUrl}/actions?action_key=${encodeURIComponent(config.boiActionKey)}`;
  result.playground.action_registration = {
    draft_id: actionPayload.draft.draft_id,
    validation_status: publishPayload.draft.validation?.valid ? "valid" : "invalid",
    publish_status: publishPayload.draft.status,
    catalog_applied_before_operator: publishPayload.draft.catalog_applied,
    operator_mode: operatorPayload.operator_mode,
    action_key: operatorPayload.action_key,
    deployment_reference: operatorPayload.deployment_reference,
  };
  await reviewPage.reload({ waitUntil: "domcontentloaded" });
  await reviewPage.locator("[data-catalog-applied]").getByText("완료", { exact: true }).waitFor();
  await screenshot(reviewPage, "08d-action-draft-catalog-applied");
  await reviewPage.close();

  const visibleText = await root.innerText();
  for (const secret of [config.agentHubPassword, config.langflowPassword, config.langflowApiKey]) {
    assert(!visibleText.includes(secret), "A credential was rendered in the Agent Playground");
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(400);
  const widthAudit = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    body: document.body.scrollWidth,
    root: document.querySelector("[data-agent-playground]")?.scrollWidth || 0,
  }));
  assert(widthAudit.body <= widthAudit.viewport + 1, `Mobile layout overflows horizontally: ${JSON.stringify(widthAudit)}`);
  result.playground.mobile_width = widthAudit;
  await screenshot(page, "09-playground-mobile");
  await screenshot(page, "09b-playground-mobile-viewport", { fullPage: false });
  await context.close();
  return result.playground.action_registration;
}

async function verifyBoiActionCatalog(browser) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  await attachDiagnostics(page, "boi-action");
  await loginBoi(page, config.boiActionUrl);

  const catalog = page.locator("[data-action-catalog]");
  await catalog.waitFor({ timeout: 30_000 });
  const actionButton = catalog.locator(`[data-action-open="${config.boiActionKey}"]`);
  await actionButton.waitFor({ state: "visible", timeout: 30_000 });
  await actionButton.click();

  const detail = catalog.locator("[data-action-detail-content]");
  await detail.locator("[data-action-preview-form]").waitFor({ timeout: 30_000 });
  const form = detail.locator("[data-action-preview-form]");
  await form.locator('[name="question"]').fill(
    "일반 Wiki 문서와 검증된 Ontology 근거를 정리해줘",
  );
  await form.locator('[name="business_context"]').fill(
    "SOP가 지정되지 않은 일반 지식 조회",
  );
  await form.locator('[name="save_mode"]').fill("preview");
  await form.locator('[name="title"]').fill("Playwright Action dry-run");

  const previewResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname.endsWith(`/api/actions/catalog/${config.boiActionKey}/preview`),
  );
  await form.getByRole("button", { name: "요청 확인" }).click();
  const previewResponse = await previewResponsePromise;
  assert(previewResponse.ok(), `BoI Action request preview returned HTTP ${previewResponse.status()}`);
  const previewPayload = await previewResponse.json();
  await detail
    .locator("[data-action-preview-result]")
    .getByText(/시험 요청을 실행할 준비가 되었습니다|확인했습니다/)
    .waitFor({ timeout: 30_000 });

  const invokeResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname.endsWith("/api/actions/invoke"),
  );
  await form.getByRole("button", { name: "Dry-run 실행" }).click();
  const invokeResponse = await invokeResponsePromise;
  assert(invokeResponse.ok(), `BoI Action dry-run returned HTTP ${invokeResponse.status()}`);
  const invokePayload = await invokeResponse.json();
  assert(invokePayload.ok === true, "BoI Action dry-run did not return ok=true");
  assert(invokePayload.status === "dry_run", "BoI Action UI did not preserve dry-run mode");
  await detail
    .locator("[data-action-preview-result]")
    .getByText("Dry-run을 완료했습니다.", { exact: true })
    .waitFor({ timeout: 30_000 });

  const invokeActual = async (scenario) => {
    page.once("dialog", (dialog) => dialog.accept());
    const responsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname.endsWith("/api/actions/invoke"),
      { timeout: 240_000 },
    );
    await form.getByRole("button", { name: "실제 실행" }).click();
    const response = await responsePromise;
    const payload = await response.json();
    assert(response.ok(), `${scenario} Action execution returned HTTP ${response.status()}`);
    assert(payload.ok === true, `${scenario} Action execution did not return ok=true`);
    const serialized = JSON.stringify(payload);
    assert(serialized.includes(result.agent_hub.deployment.flow_id), `${scenario} used a different Flow`);
    assert(serialized.includes("source_references"), `${scenario} did not return Wiki sources`);
    assert(serialized.includes("ontology"), `${scenario} did not return Ontology evidence`);
    await detail
      .locator("[data-action-preview-result]")
      .getByText("Action 실행을 완료했습니다.", { exact: true })
      .waitFor({ timeout: 120_000 });
    return payload;
  };

  const resultData = (payload) => {
    const visit = (value) => {
      if (!value || typeof value !== "object") return null;
      if (
        !Array.isArray(value) &&
        Array.isArray(value.source_references) &&
        value.task_context &&
        typeof value.task_context === "object"
      ) {
        return value;
      }
      for (const child of Array.isArray(value) ? value : Object.values(value)) {
        const found = visit(child);
        if (found) return found;
      }
      return null;
    };
    return visit(payload) || {};
  };

  const safeExecutionSummary = (payload) => {
    const data = resultData(payload);
    const provenance = data.provenance && typeof data.provenance === "object" ? data.provenance : {};
    const taskContext =
      data.task_context && typeof data.task_context === "object" ? data.task_context : {};
    return {
      request_id: payload.request_id,
      status: payload.status,
      flow_id: data.flow_id || payload.flow_id,
      grounding_status: data.grounding_status,
      source_reference_count: (data.source_references || []).length,
      ontology_relationship_count: (data.ontology_relationships || []).length,
      draft_reference: data.draft_reference || "",
      wiki_url: data.wiki_url || "",
      trace_id: provenance.trace_id || "",
      task_context: {
        profile: taskContext.profile || "",
        task_ref: taskContext.task_ref || "",
        sop_ref: taskContext.sop_ref || "",
        sop_stage: taskContext.sop_stage || "",
        event_ref: taskContext.event_ref || "",
        action_ref: taskContext.action_ref || "",
        prior_results: taskContext.prior_results || [],
        required_evidence: taskContext.required_evidence || [],
        missing_evidence: taskContext.missing_evidence || [],
      },
    };
  };

  const generalPayload = await invokeActual("general");
  await screenshot(page, "10-boi-action-general-executed");

  const fillIfPresent = async (name, value) => {
    const input = form.locator(`[name="${name}"]`);
    if (await input.count()) await input.fill(value);
  };
  const inboxPayload = await page.evaluate(async () => {
    const response = await fetch("/api/inbox?limit=50");
    return {
      status: response.status,
      body: await response.json().catch(() => ({})),
    };
  });
  assert(inboxPayload.status === 200, `BoI Task inbox returned HTTP ${inboxPayload.status}`);
  const actualTaskRef = (inboxPayload.body.items || [])
    .map((item) => String(item.task_id || ""))
    .find((value) => value.startsWith("task:"));
  assert(actualTaskRef, "No ACL-checked Task anchor is available for Action validation");
  await fillIfPresent("question", "SOP Task 수행에 필요한 Wiki 및 Ontology 근거를 정리해줘");
  await fillIfPresent("business_context", "선택한 실제 Task를 서버 권위 Context로 해석");
  await fillIfPresent("task_ref", actualTaskRef);
  await fillIfPresent("sop_ref", "");
  await fillIfPresent("sop_stage", "");
  await fillIfPresent("event_ref", "");
  await fillIfPresent("action_ref", "");
  await fillIfPresent("prior_results", "");
  await fillIfPresent("required_evidence", "");
  await fillIfPresent("missing_evidence", "");
  await fillIfPresent("save_mode", "preview");
  await fillIfPresent("title", "Playwright SOP Task Action");
  const sopPayload = await invokeActual("sop_task");
  await screenshot(page, "10c-boi-action-sop-executed");

  await fillIfPresent("question", "검증 결과를 내 개인 Wiki 초안으로 저장해줘");
  await fillIfPresent("save_mode", "private_draft");
  await fillIfPresent("title", `Playwright private draft ${runId}`);
  const privateDraftPayload = await invokeActual("private_draft");
  const privateText = JSON.stringify(privateDraftPayload);
  assert(privateText.includes("draft_reference"), "private_draft did not return a draft reference");
  await screenshot(page, "10d-boi-action-private-draft");
  const generalSummary = safeExecutionSummary(generalPayload);
  const sopSummary = safeExecutionSummary(sopPayload);
  const privateDraftSummary = safeExecutionSummary(privateDraftPayload);
  assert(
    generalSummary.task_context.profile === "knowledge_lookup"
      && !generalSummary.task_context.sop_ref,
    "general Action execution created a false SOP context",
  );
  assert(
    sopSummary.task_context.profile === "sop_task_execution"
      && sopSummary.task_context.task_ref === actualTaskRef
      && sopSummary.task_context.sop_ref
      && sopSummary.task_context.sop_stage
      && sopSummary.task_context.event_ref
      && sopSummary.task_context.action_ref,
    "actual SOP Task Context was not preserved",
  );
  assert(Array.isArray(sopSummary.task_context.prior_results), "SOP prior_results is not an array");
  assert(Array.isArray(sopSummary.task_context.required_evidence), "SOP required_evidence is not an array");
  assert(Array.isArray(sopSummary.task_context.missing_evidence), "SOP missing_evidence is not an array");

  result.boi_action = {
    action_key: config.boiActionKey,
    preview_ready: previewPayload.ok === true,
    dry_run_status: invokePayload.status,
    request_id: invokePayload.request_id,
    exact_flow_id: result.agent_hub.deployment.flow_id,
    general_status: generalPayload.status,
    sop_status: sopPayload.status,
    private_draft_status: privateDraftPayload.status,
    private_draft_owner: config.agentHubUsername,
    general_execution: generalSummary,
    sop_execution: sopSummary,
    private_draft_execution: privateDraftSummary,
  };
  await screenshot(page, "10-boi-action-catalog-dry-run");
  await screenshot(page, "10b-boi-action-catalog-viewport", { fullPage: false });

  const visibleText = await catalog.innerText();
  for (const secret of [config.agentHubPassword, config.langflowPassword, config.langflowApiKey]) {
    assert(!visibleText.includes(secret), "A credential was rendered in the BoI Action catalog");
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(400);
  const widthAudit = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    body: document.body.scrollWidth,
    catalog: document.querySelector("[data-action-catalog]")?.scrollWidth || 0,
  }));
  assert(
    widthAudit.body <= widthAudit.viewport + 1,
    `BoI Action mobile layout overflows horizontally: ${JSON.stringify(widthAudit)}`,
  );
  result.boi_action.mobile_width = widthAudit;
  await screenshot(page, "11-boi-action-catalog-mobile");
  await screenshot(page, "11b-boi-action-catalog-mobile-viewport", { fullPage: false });
  await context.close();
}

async function verifyViewerActionDenial(browser) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await attachDiagnostics(page, "boi-action-viewer");
  config.boiViewerPassword = await resetViewerPassword();
  await loginBoi(page, config.boiActionUrl, "100003");

  const catalog = page.locator("[data-action-catalog]");
  await catalog.waitFor({ timeout: 30_000 });
  const actionButton = catalog.locator(`[data-action-open="${config.boiActionKey}"]`);
  await actionButton.waitFor({ state: "visible", timeout: 30_000 });
  const detailResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "GET"
      && new URL(response.url()).pathname.endsWith(
        `/api/actions/catalog/${config.boiActionKey}`,
      ),
  );
  await actionButton.click();
  const detailResponse = await detailResponsePromise;
  const detail = catalog.locator("[data-action-detail-content]");
  const form = detail.locator("[data-action-preview-form]");
  if (detailResponse.status() === 404) {
    await detail.getByText("Action 정보를 불러오지 못했습니다.").waitFor();
  } else {
    assert(detailResponse.ok(), `Viewer Action detail returned HTTP ${detailResponse.status()}`);
    await form.waitFor({ timeout: 30_000 });
  }
  const invoke = await page.evaluate(async ({ actionKey }) => {
    const response = await fetch("/api/actions/invoke", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action_key: actionKey,
        payload: {
          question: "조회 전용 사용자의 Action 실행 권한 확인",
          save_mode: "private_draft",
          title: "Viewer denial check",
        },
        dry_run: false,
      }),
    });
    return {
      status: response.status,
      body: await response.json().catch(() => ({})),
    };
  }, { actionKey: config.boiActionKey });
  assert(invoke.status === 403, `Viewer Action denial returned HTTP ${invoke.status}`);
  const invokePayload = invoke.body;
  assert(
    JSON.stringify(invokePayload.detail || "").includes("boi.action_invoker"),
    "Viewer Action denial did not identify the missing execution role",
  );
  const identityText = await page.locator(".identity-strip").innerText();
  assert(identityText.includes("100003"), "Viewer browser did not resolve employee 100003");
  result.boi_action.viewer_denial = {
    employee_id: "100003",
    status: invoke.status,
    catalog_detail_status: detailResponse.status(),
    save_mode: "private_draft",
    reason: "missing boi.action_invoker",
  };
  await screenshot(page, "12-boi-action-viewer-denied");
  await screenshot(page, "12b-boi-action-viewer-denied-viewport", { fullPage: false });
  await context.close();
}

async function verifyBoiLogout(browser) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await attachDiagnostics(page, "boi-logout");
  await loginBoi(page, config.playgroundUrl);
  const cookiesBefore = await context.cookies(config.boiBaseUrl);
  assert(
    cookiesBefore.some((cookie) => cookie.name === "boi_session"),
    "BoI session cookie was not issued before logout",
  );
  await page.goto(`${config.boiBaseUrl}/auth/logout?next=%2Fplayground`, {
    waitUntil: "domcontentloaded",
  });
  await page.waitForURL(
    (url) =>
      url.origin === new URL(config.boiBaseUrl).origin ||
      url.pathname.includes("/protocol/openid-connect/"),
    { timeout: 30_000 },
  );
  const cookiesAfter = await context.cookies(config.boiBaseUrl);
  assert(
    !cookiesAfter.some((cookie) => cookie.name === "boi_session"),
    "BoI session cookie remained after logout",
  );
  const apiStatus = (
    await context.request.get(`${config.boiBaseUrl}/api/agent-playground`, {
      headers: { Accept: "application/json" },
      maxRedirects: 0,
    })
  ).status();
  assert(apiStatus === 401, `BoI API session remained usable after logout: HTTP ${apiStatus}`);
  result.boi_logout = {
    session_cookie_removed: true,
    api_status_after_logout: apiStatus,
  };
  await context.close();
}

const browser = await chromium.launch({
  headless: process.env.PLAYWRIGHT_HEADFUL !== "1",
  ...(config.chromiumExecutable ? { executablePath: config.chromiumExecutable } : {}),
});
try {
  if (process.env.PLAYWRIGHT_ONLY_BOI_SSO === "1") {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await attachDiagnostics(page, "boi-sso-smoke");
    await loginBoi(page, config.playgroundUrl);
    result.exact_chain = { sso_principal: result.boi_sso, mode: "boi_sso_smoke" };
    await context.close();
    result.passed = true;
    result.finished_at = new Date().toISOString();
  } else if (process.env.PLAYWRIGHT_ONLY_BOI_ACTION === "1") {
    assert(config.boiActionKey, "BOI_ACTION_KEY is required for Action-only validation");
    assert(config.boiFlowId, "BOI_FLOW_ID is required for Action-only validation");
    result.agent_hub.deployment = { flow_id: config.boiFlowId };
    await verifyBoiActionCatalog(browser);
    await verifyViewerActionDenial(browser);
    await verifyBoiLogout(browser);
    const expectedHttpError = (item) =>
      (item.status === 403 && item.url.endsWith("/api/agent-playground")) ||
      (item.scope === "boi-logout" &&
        item.status === 401 &&
        item.url.includes("/api/agent-playground")) ||
      (item.scope === "boi-action-viewer" &&
        item.status === 403 &&
        item.url.endsWith("/api/actions/invoke")) ||
      (item.scope === "boi-action-viewer" &&
        item.status === 404 &&
        item.url.includes("/api/actions/catalog/"));
    result.expected_http_errors = result.http_errors.filter(expectedHttpError);
    result.unexpected_http_errors = result.http_errors.filter((item) => !expectedHttpError(item));
    assert(
      result.unexpected_http_errors.length === 0,
      `Unexpected browser HTTP errors: ${JSON.stringify(result.unexpected_http_errors)}`,
    );
    result.exact_chain = {
      mode: "boi_action_exact_regression",
      sso_principal: result.boi_sso,
      flow_id: config.boiFlowId,
      action_key: config.boiActionKey,
      execution: result.boi_action,
    };
    result.passed = true;
    result.finished_at = new Date().toISOString();
  } else {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const agentHubPage = await context.newPage();
  await attachDiagnostics(agentHubPage, "agent-hub");
  await loginAgentHub(agentHubPage);
  await uploadFlow(agentHubPage);
  const deployment = await deployFlow(agentHubPage);
  await context.close();

  await verifyLangflowCanvas(browser, deployment.flowId, deployment.flowUrl);
  await verifyPlayground(browser, deployment.flowId);
  await verifyBoiActionCatalog(browser);
  await verifyViewerActionDenial(browser);
  await verifyBoiLogout(browser);

  result.exact_chain = {
    sso_principal: result.boi_sso,
    agent_hub_asset: {
      asset_id: result.agent_hub.asset_id,
      asset_title: result.agent_hub.asset_title,
    },
    endpoint: result.playground.endpoint_alias,
    project_id: result.playground.project,
    flow_id: result.agent_hub.deployment?.flow_id,
    artifact_checksum: result.playground.artifact_checksum,
    deployment_reference: result.playground.action_registration?.deployment_reference,
    registration_draft_id: result.playground.action_registration?.draft_id,
    publish_status: result.playground.action_registration?.publish_status,
    action_key: result.playground.action_registration?.action_key,
    execution: result.boi_action,
  };

  const expectedHttpError = (item) =>
    (item.status === 403 && item.url.endsWith("/api/v1/auto_login")) ||
    (item.status === 403 && item.url.endsWith("/api/v1/admin/settings")) ||
    (item.status === 403 && item.url.endsWith("/api/v1/users/me")) ||
    (item.status === 403 && item.url.endsWith("/api/agent-playground")) ||
    (item.scope === "boi-logout" &&
      item.status === 401 &&
      item.url.includes("/api/agent-playground")) ||
    (item.scope === "boi-action-viewer" &&
      item.status === 403 &&
      item.url.endsWith("/api/actions/invoke")) ||
    (item.scope === "boi-action-viewer" &&
      item.status === 404 &&
      item.url.includes("/api/actions/catalog/"));
  result.expected_http_errors = result.http_errors.filter(expectedHttpError);
  result.unexpected_http_errors = result.http_errors.filter((item) => !expectedHttpError(item));
  assert(
    result.unexpected_http_errors.length === 0,
    `Unexpected browser HTTP errors: ${JSON.stringify(result.unexpected_http_errors)}`,
  );
  result.passed = true;
  result.finished_at = new Date().toISOString();
  }
} catch (error) {
  result.error = String(error.stack || error.message || error).replace(
    new RegExp(
      [config.agentHubPassword, config.langflowPassword, config.langflowApiKey]
        .filter(Boolean)
        .map((value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
        .join("|"),
      "g",
    ),
    "[REDACTED]",
  );
  result.finished_at = new Date().toISOString();
  throw error;
} finally {
  await browser.close();
  await fs.writeFile(
    path.join(config.evidenceDir, "playwright-result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
    { mode: 0o600 },
  );
}

console.log(
  JSON.stringify({
    ok: result.passed,
    evidence_dir: config.evidenceDir,
    flow_id: result.agent_hub.deployment?.flow_id,
    screenshots: result.screenshots.length,
  }),
);
