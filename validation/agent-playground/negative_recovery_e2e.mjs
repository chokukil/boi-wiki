#!/usr/bin/env node

import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || "playwright");

const config = {
  boiUrl: process.env.BOI_URL || "http://localhost:28005",
  ssoPassword: process.env.BOI_SSO_PASSWORD || "",
  employeeId: process.env.BOI_EMPLOYEE_ID || "100002",
  identityFile:
    process.env.AGENT_HUB_IDENTITY_FILE
    || "/tmp/boi-ap-agent-hub-sso-users.json",
  primaryUrl: process.env.PRIMARY_LANGFLOW_URL || "http://localhost:7864",
  recoveryUrl: process.env.RECOVERY_LANGFLOW_URL || "http://localhost:17866",
  unsupportedUrl: process.env.UNSUPPORTED_LANGFLOW_URL || "http://localhost:17865",
  credentialFile: process.env.VALIDATION_USER_CREDENTIAL_FILE || "/tmp/boi-ap-negative-users.json",
  otherUserCredentialFile:
    process.env.OTHER_USER_CREDENTIAL_FILE
    || process.env.VALIDATION_USER_CREDENTIAL_FILE
    || "/tmp/boi-ap-negative-users.json",
  evidenceDir:
    process.env.PLAYWRIGHT_EVIDENCE_DIR ||
    "artifacts/agent-playground-negative-recovery",
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || "",
};

const ssoIdentities = JSON.parse(await fs.readFile(config.identityFile, "utf8"));
const ssoPassword = config.ssoPassword || String(ssoIdentities[config.employeeId] || "");
if (!ssoPassword) throw new Error("BoI SSO validation password is required");
const validationUsers = JSON.parse(await fs.readFile(config.credentialFile, "utf8"));
const otherValidationUsers = JSON.parse(
  await fs.readFile(config.otherUserCredentialFile, "utf8"),
);
const runId = process.env.PLAYWRIGHT_RUN_ID || new Date().toISOString().replace(/\W/g, "");
const result = {
  ok: false,
  run_id: runId,
  oidc: {},
  negative_connections: {},
  endpoint_independence: {},
  recovery: {},
  screenshots: [],
  console_errors: [],
  ignored_console_warnings: [],
  page_errors: [],
  expected_http_errors: [],
  ignored_http_errors: [],
  unexpected_http_errors: [],
};

await fs.mkdir(config.evidenceDir, { recursive: true });
const recoveryReset = await fetch(`${config.recoveryUrl}/__validation/reset`, {
  method: "POST",
});
if (!recoveryReset.ok) {
  throw new Error(`recovery validation gate reset returned HTTP ${recoveryReset.status}`);
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function fingerprint(value) {
  return crypto.createHash("sha256").update(value).digest("hex").slice(0, 12);
}

async function screenshot(page, name) {
  const target = path.join(config.evidenceDir, `${name}.png`);
  await page.screenshot({ path: target, fullPage: true });
  result.screenshots.push(target);
}

function expectedHttp(status, method, pathname) {
  if (
    method === "POST" &&
    pathname === "/api/agent-playground/endpoints/test" &&
    [403, 409, 502].includes(status)
  ) {
    return true;
  }
  return method === "POST" && pathname === "/api/agent-playground/bootstrap" && status === 502;
}

function diagnostics(page, scope) {
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (text.startsWith("Duplicate request:")) {
      result.ignored_console_warnings.push({
        scope,
        reason: "unmodified Langflow frontend duplicate-request guard",
        text: text.slice(0, 500),
      });
    } else if (
      scope.startsWith("langflow-key-")
      && (
        text.includes(
          "https://api.github.com/repos/langflow-ai/langflow",
        )
        || text.startsWith(
          "Error fetching repository data: AxiosError: Network Error",
        )
      )
    ) {
      result.ignored_console_warnings.push({
        scope,
        reason: "unmodified Langflow optional GitHub release metadata lookup",
        text: text.slice(0, 500),
      });
    } else if (!text.includes("favicon") && !text.startsWith("Failed to load resource:")) {
      result.console_errors.push({ scope, text: text.slice(0, 500) });
    }
  });
  page.on("pageerror", (error) => {
    result.page_errors.push({ scope, text: String(error.message || error).slice(0, 500) });
  });
  page.on("response", (response) => {
    if (response.status() < 400) return;
    const url = new URL(response.url());
    const entry = {
      scope,
      status: response.status(),
      method: response.request().method(),
      url: `${url.origin}${url.pathname}`,
    };
    if (
      scope.startsWith("langflow-key-") &&
      entry.status === 403 &&
      entry.method === "GET" &&
      url.pathname === "/api/v1/auto_login"
    ) {
      result.ignored_http_errors.push({
        ...entry,
        reason: "official Langflow AUTO_LOGIN=false authentication boundary",
      });
      return;
    }
    if (expectedHttp(entry.status, entry.method, url.pathname)) {
      result.expected_http_errors.push(entry);
    } else {
      result.unexpected_http_errors.push(entry);
    }
  });
}

async function loginBoi(page) {
  await page.goto(`${config.boiUrl}/playground`, { waitUntil: "domcontentloaded" });
  assert(page.url().includes("/protocol/openid-connect/"), "BoI did not start an OIDC login");
  const authorization = new URL(page.url());
  result.oidc = {
    state: Boolean(authorization.searchParams.get("state")),
    nonce: Boolean(authorization.searchParams.get("nonce")),
    pkce_s256: authorization.searchParams.get("code_challenge_method") === "S256",
  };
  assert(result.oidc.state && result.oidc.nonce && result.oidc.pkce_s256, "OIDC+PKCE evidence is incomplete");
  await page.locator("#username").fill(config.employeeId);
  await page.locator("#password").fill(ssoPassword);
  await Promise.all([
    page.waitForURL((url) => url.origin === new URL(config.boiUrl).origin),
    page.locator("#kc-login").click(),
  ]);
  const principal = await page.evaluate(async () => {
    const response = await fetch("/api/agent-playground");
    return { status: response.status, body: await response.json() };
  });
  assert(principal.status === 200, `Playground state returned HTTP ${principal.status}`);
  assert(principal.body.identity?.employee_id === config.employeeId, "OIDC principal mismatch");
  assert(
    ["oidc", "keycloak"].includes(principal.body.identity?.auth_source),
    "OIDC principal was not used",
  );
}

async function createLangflowKey(browser, account, label) {
  // Browser cookies are scoped by host rather than port. BoI and Langflow use
  // different localhost ports in validation, so keep the external Langflow
  // login in an isolated context just as a separate settings window would be
  // isolated by the corporate hostnames.
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  diagnostics(page, `langflow-key-${account.username}`);
  try {
    await page.goto(`${account.url}/settings/api-keys`, { waitUntil: "domcontentloaded" });
    const password = page.locator('input[type="password"]');
    const addNew = page.getByRole("button", { name: /Add New/i });
    // Official Langflow renders the requested settings route first, calls the
    // disabled auto-login endpoint, and only then redirects to /login. Wait
    // for the actual authenticated or login control instead of sampling the
    // intermediate DOM immediately after domcontentloaded.
    await Promise.race([
      password.waitFor({ state: "visible", timeout: 15_000 }).catch(() => null),
      addNew.waitFor({ state: "visible", timeout: 15_000 }).catch(() => null),
    ]);
    if (await password.isVisible().catch(() => false)) {
      await page.locator('input[name="username"], input[type="text"]').first().fill(account.username);
      await password.fill(account.password);
      await Promise.all([
        page.waitForURL((url) => !url.pathname.endsWith("/login")),
        page.getByRole("button", { name: "Sign In", exact: true }).click(),
      ]);
      await page.goto(`${account.url}/settings/api-keys`, { waitUntil: "domcontentloaded" });
    }
    await addNew.waitFor({ state: "visible", timeout: 30_000 });
    await addNew.click();
    const dialog = page.getByRole("dialog");
    await dialog.waitFor();
    await dialog.locator("input").first().fill(label);
    const created = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return response.request().method() === "POST" && /api[_/-]?keys?/i.test(url.pathname);
    });
    await dialog.getByRole("button", { name: /Generate|Create/i }).click();
    const response = await created;
    assert(response.ok(), `Langflow API Key creation returned HTTP ${response.status()}`);
    const payload = await response.json();
    const apiKey = String(payload.api_key || payload.key || payload.token || "");
    assert(apiKey.length >= 16, "Langflow API Key was not returned once");
    const done = dialog.getByRole("button", { name: "Done", exact: true });
    const close = dialog.getByRole("button", { name: "Close", exact: true });
    if (await done.count()) await done.click();
    else if (await close.count()) await close.click();
    else await page.keyboard.press("Escape");
    const saved = await context.request.get(`${account.url}/api/v1/api_key/`);
    const persisted = { status: saved.status(), body: await saved.json() };
    assert(persisted.status === 200, `Langflow API Key listing returned HTTP ${persisted.status}`);
    assert(
      (persisted.body.api_keys || []).some((item) => item.name === label),
      "generated Langflow API Key was not persisted",
    );
    assert(
      !JSON.stringify(persisted.body).includes(apiKey),
      "Langflow API Key listing returned the raw key",
    );
    const owner = await fetch(`${account.url}/api/v1/users/whoami`, {
      headers: { "x-api-key": apiKey },
    });
    const ownerPayload = await owner.json().catch(() => ({}));
    assert(owner.ok, `Langflow API Key owner lookup returned HTTP ${owner.status}`);
    assert(
      String(ownerPayload.username || "") === String(account.username || ""),
      `Langflow API Key owner mismatch: expected ${account.username}, got ${
        ownerPayload.username || "unknown"
      }`,
    );
    const visible = await page.locator("body").innerText();
    assert(!visible.includes(apiKey), "Langflow API Key remained visible after closing");
    return apiKey;
  } finally {
    await context.close();
  }
}

async function apiState(page) {
  return page.evaluate(async () => {
    const response = await fetch("/api/agent-playground");
    return { status: response.status, body: await response.json() };
  });
}

async function ensurePrimaryReady(page) {
  let state = await apiState(page);
  assert(state.status === 200, "Playground state failed");
  const endpointId = state.body.default_endpoint_id;
  const setup = state.body.endpoint_setups?.[endpointId] || {};
  if (setup.onboarding?.required) {
    const button = page.locator("[data-onboarding-bootstrap]");
    await button.waitFor({ state: "visible" });
    const response = page.waitForResponse((candidate) => {
      const url = new URL(candidate.url());
      return candidate.request().method() === "POST" && url.pathname === "/api/agent-playground/bootstrap";
    });
    await button.click();
    const completed = await response;
    assert(completed.ok(), `primary bundle revalidation returned HTTP ${completed.status()}`);
    await page.locator('[data-onboarding-stage="flow"]').waitFor({ state: "visible", timeout: 120_000 });
    await page.locator("[data-onboarding-finish]").click();
  }
  await page.locator("[data-workbench-only]").first().waitFor({ state: "visible" });
  state = await apiState(page);
  const ready = state.body.endpoint_setups?.[endpointId]?.readiness;
  assert(ready?.ready === true, "primary endpoint is not ready");
  assert(ready?.checks?.bundle === true, "primary bundle was not verified");
  return endpointId;
}

async function openConnectionSettings(page) {
  const settings = page.locator(".agent-playground-connection-settings");
  await settings.waitFor({ state: "visible" });
  if (!(await settings.evaluate((details) => details.open))) {
    await settings.locator("summary").click();
  }
}

async function testUnsaved(page, { name, url, key, expectedStatus, screenshotName }) {
  await openConnectionSettings(page);
  await page.locator("[data-new-endpoint]").click();
  const form = page.locator("[data-endpoint-form]");
  await form.locator('[name="name"]').fill(name);
  await form.locator('[name="base_url"]').fill(url);
  await form.locator('[name="api_key"]').fill(key);
  const response = page.waitForResponse((candidate) => {
    const target = new URL(candidate.url());
    return candidate.request().method() === "POST" && target.pathname === "/api/agent-playground/endpoints/test";
  });
  await form.locator("[data-test-unsaved]").click();
  const tested = await response;
  assert(tested.status() === expectedStatus, `${name} returned HTTP ${tested.status()}`);
  const output = form.locator("[data-endpoint-test-output]");
  await output.waitFor();
  const message = (await output.textContent())?.trim() || "";
  assert(message.length > 0, `${name} did not show a failure reason`);
  await form.locator('[name="api_key"]').fill("");
  await screenshot(page, screenshotName);
  await form.locator("[data-cancel-endpoint]").click();
  return { status: tested.status(), message };
}

async function addRecoveryEndpoint(page, apiKey) {
  await openConnectionSettings(page);
  await page.locator("[data-new-endpoint]").click();
  const form = page.locator("[data-endpoint-form]");
  await form.locator('[name="name"]').fill("Recovery Langflow 1.11");
  await form.locator('[name="base_url"]').fill(config.recoveryUrl);
  await form.locator('[name="api_key"]').fill(apiKey);
  const testedPromise = page.waitForResponse((candidate) => {
    const target = new URL(candidate.url());
    return candidate.request().method() === "POST" && target.pathname === "/api/agent-playground/endpoints/test";
  });
  await form.locator("[data-test-unsaved]").click();
  const tested = await testedPromise;
  assert(tested.status() === 200, `recovery endpoint test returned HTTP ${tested.status()}`);
  const savedPromise = page.waitForResponse((candidate) => {
    const target = new URL(candidate.url());
    return candidate.request().method() === "POST" && target.pathname === "/api/agent-playground/endpoints";
  });
  await form.getByRole("button", { name: "저장", exact: true }).click();
  const saved = await savedPromise;
  assert(saved.ok(), `recovery endpoint save returned HTTP ${saved.status()}`);
  const payload = await saved.json();
  await page.locator('[data-onboarding-stage="knowledge"]').waitFor({ state: "visible" });
  return payload.endpoint.endpoint_id;
}

async function removeStaleRecoveryEndpoints(page) {
  const state = await apiState(page);
  const target = config.recoveryUrl.replace(/\/+$/, "");
  for (const endpoint of state.body.endpoints || []) {
    if (String(endpoint.base_url || "").replace(/\/+$/, "") !== target) continue;
    const removed = await page.evaluate(async (endpointId) => {
      const response = await fetch(
        `/api/agent-playground/endpoints/${encodeURIComponent(endpointId)}`,
        { method: "DELETE" },
      );
      return { status: response.status, body: await response.json() };
    }, endpoint.endpoint_id);
    assert(removed.status === 200, `stale recovery endpoint removal returned HTTP ${removed.status}`);
    assert(!removed.body.deactivated, "stale recovery endpoint is still referenced by a deployment");
  }
}

async function langflowCounts(baseUrl, apiKey) {
  const headers = { "x-api-key": apiKey };
  const [projectsResponse, variablesResponse, flowsResponse] = await Promise.all([
    fetch(`${baseUrl}/api/v1/projects/`, { headers }),
    fetch(`${baseUrl}/api/v1/variables/`, { headers }),
    fetch(`${baseUrl}/api/v1/flows/`, { headers }),
  ]);
  for (const [label, response] of [
    ["projects", projectsResponse],
    ["variables", variablesResponse],
    ["flows", flowsResponse],
  ]) {
    assert(response.ok, `Langflow ${label} count returned HTTP ${response.status}`);
  }
  const projects = await projectsResponse.json();
  const variables = await variablesResponse.json();
  const flows = await flowsResponse.json();
  return {
    projects: projects.filter((item) => item.name === `boi-${config.employeeId}`).length,
    credentials: variables.filter((item) => item.name === "BOI_WIKI_PAT").length,
    canonical_flows: flows.filter((item) => item.name === "BoI Wiki Agent Loop").length,
  };
}

async function resetRecoveryLangflowAssets(baseUrl, apiKey) {
  const headers = { "x-api-key": apiKey };
  const targets = [
    {
      collection: "/api/v1/flows/",
      matches: (item) => item.name === "BoI Wiki Agent Loop",
      remove: (item) => `/api/v1/flows/${encodeURIComponent(item.id)}`,
    },
    {
      collection: "/api/v1/variables/",
      matches: (item) => item.name === "BOI_WIKI_PAT",
      remove: (item) => `/api/v1/variables/${encodeURIComponent(item.id)}`,
    },
    {
      collection: "/api/v1/projects/",
      matches: (item) => item.name === `boi-${config.employeeId}`,
      remove: (item) => `/api/v1/projects/${encodeURIComponent(item.id)}`,
    },
  ];
  for (const target of targets) {
    const response = await fetch(`${baseUrl}${target.collection}`, { headers });
    assert(response.ok, `recovery reset lookup returned HTTP ${response.status}`);
    for (const item of (await response.json()).filter(target.matches)) {
      const removed = await fetch(`${baseUrl}${target.remove(item)}`, {
        method: "DELETE",
        headers,
      });
      assert(
        [200, 202, 204, 404].includes(removed.status),
        `recovery reset delete returned HTTP ${removed.status}`,
      );
    }
  }
}

async function patSnapshot(page) {
  return page.evaluate(async () => {
    const response = await fetch("/api/v2/tokens");
    const payload = await response.json();
    return {
      status: response.status,
      token_ids: (payload.items || []).map((item) => item.token_id).sort(),
    };
  });
}

async function clickBootstrap(page, expectedStatus) {
  const response = page.waitForResponse((candidate) => {
    const target = new URL(candidate.url());
    return candidate.request().method() === "POST" && target.pathname === "/api/agent-playground/bootstrap";
  });
  await page.locator("[data-onboarding-bootstrap]").click();
  const completed = await response;
  const payload = await completed.json().catch(() => ({}));
  const allowed = Array.isArray(expectedStatus) ? expectedStatus : [expectedStatus];
  assert(
    allowed.includes(completed.status()),
    `bootstrap returned HTTP ${completed.status()}: ${JSON.stringify(payload)}`,
  );
  return { status: completed.status(), payload };
}

async function bootstrapEndpoint(page, endpointId) {
  return page.evaluate(async (id) => {
    const response = await fetch("/api/agent-playground/bootstrap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint_id: id }),
    });
    return {
      status: response.status,
      body: await response.json().catch(() => ({})),
    };
  }, endpointId);
}

const browser = await chromium.launch({
  headless: process.env.PLAYWRIGHT_HEADFUL !== "1",
  ...(config.executablePath ? { executablePath: config.executablePath } : {}),
});

try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  diagnostics(page, "boi-negative-recovery");
  await loginBoi(page);
  const primaryEndpointId = await ensurePrimaryReady(page);
  await screenshot(page, "01-primary-endpoint-ready");

  const otherUserAccount = {
    ...(otherValidationUsers.other_user || {}),
  };
  assert(
    otherUserAccount.username === "100003"
      && otherUserAccount.password
      && otherUserAccount.url,
    "primary Langflow 100003 account is unavailable",
  );
  const otherUserKey = await createLangflowKey(
    browser,
    otherUserAccount,
    `Other owner negative validation ${runId}`,
  );
  const recoveryKey = await createLangflowKey(
    browser,
    validationUsers.recovery_user,
    `Recovery endpoint validation ${runId}`,
  );
  await resetRecoveryLangflowAssets(validationUsers.recovery_user.url, recoveryKey);
  await removeStaleRecoveryEndpoints(page);

  const beforeNegative = await apiState(page);
  const endpointCountBefore = beforeNegative.body.endpoints.length;
  result.negative_connections.invalid_key = await testUnsaved(page, {
    name: "Invalid key",
    url: config.primaryUrl,
    key: "invalid-validation-api-key",
    expectedStatus: 502,
    screenshotName: "02-invalid-key-blocked",
  });
  result.negative_connections.other_user_key = await testUnsaved(page, {
    name: "Other user key",
    url: config.primaryUrl,
    key: otherUserKey,
    expectedStatus: 403,
    screenshotName: "03-other-user-key-blocked",
  });
  result.negative_connections.unsupported_version = await testUnsaved(page, {
    name: "Unsupported Langflow",
    url: config.unsupportedUrl,
    key: "unsupported-version-validation-key",
    expectedStatus: 409,
    screenshotName: "04-unsupported-version-blocked",
  });
  const afterNegative = await apiState(page);
  result.negative_connections.endpoint_count_unchanged =
    afterNegative.body.endpoints.length === endpointCountBefore;
  assert(result.negative_connections.endpoint_count_unchanged, "failed tests created an endpoint");
  result.negative_connections.key_fingerprints = {
    other_user: fingerprint(otherUserKey),
    recovery_user: fingerprint(recoveryKey),
  };

  const recoveryEndpointId = await addRecoveryEndpoint(page, recoveryKey);
  const stateBeforeFailure = await apiState(page);
  const primaryBefore = stateBeforeFailure.body.endpoint_setups?.[primaryEndpointId];
  const recoveryBefore = stateBeforeFailure.body.endpoint_setups?.[recoveryEndpointId];
  assert(primaryBefore?.readiness?.ready === true, "primary readiness changed after adding endpoint");
  assert(recoveryBefore?.readiness?.ready === false, "new endpoint was incorrectly ready");
  result.endpoint_independence.before_failure = {
    endpoint_count: stateBeforeFailure.body.endpoints.length,
    primary_ready: primaryBefore.readiness.ready,
    recovery_ready: recoveryBefore.readiness.ready,
  };
  await screenshot(page, "05-second-endpoint-independent-onboarding");

  const assetsBefore = await langflowCounts(validationUsers.recovery_user.url, recoveryKey);
  const patsBefore = await patSnapshot(page);
  assert(patsBefore.status === 200, "PAT listing failed before recovery");
  const firstBootstrap = await clickBootstrap(page, [502, 200]);
  const stateAfterFailure = await apiState(page);
  const firstSetup = stateAfterFailure.body.endpoint_setups?.[recoveryEndpointId];
  if (firstBootstrap.status === 502) {
    await page.locator('[data-onboarding-stage="knowledge"]').waitFor({ state: "visible" });
    assert(firstSetup?.onboarding?.status === "error", "injected failure was not recorded");
    assert(firstSetup?.onboarding?.current_step === "knowledge", "retry action is not visible");
    await screenshot(page, "06-bootstrap-partial-failure-retry-visible");
  } else {
    await page.locator('[data-onboarding-stage="flow"]').waitFor({
      state: "visible",
      timeout: 120_000,
    });
    assert(
      firstSetup?.readiness?.ready === true,
      "transient failure was not recovered within the bootstrap request",
    );
    await screenshot(page, "06-bootstrap-transient-failure-recovered");
  }
  const assetsAfterFailure = await langflowCounts(validationUsers.recovery_user.url, recoveryKey);
  const patsAfterFailure = await patSnapshot(page);
  assert(assetsAfterFailure.projects === assetsBefore.projects + 1, "project was not created once");
  assert(assetsAfterFailure.credentials === assetsBefore.credentials + 1, "credential was not created once");
  assert(assetsAfterFailure.canonical_flows === assetsBefore.canonical_flows + 1, "Flow was not created once");
  assert(
    patsAfterFailure.token_ids.length === patsBefore.token_ids.length + 1,
    "PAT was not created exactly once before smoke failure",
  );

  const retryBootstrap = firstBootstrap.status === 502
    ? await clickBootstrap(page, 200)
    : await bootstrapEndpoint(page, recoveryEndpointId);
  assert(
    retryBootstrap.status === 200,
    `idempotent bootstrap returned HTTP ${retryBootstrap.status}`,
  );
  await page.locator('[data-onboarding-stage="flow"]').waitFor({ state: "visible", timeout: 120_000 });
  const stateAfterRecovery = await apiState(page);
  const recoveredSetup = stateAfterRecovery.body.endpoint_setups?.[recoveryEndpointId];
  const primaryAfter = stateAfterRecovery.body.endpoint_setups?.[primaryEndpointId];
  const assetsAfterRecovery = await langflowCounts(validationUsers.recovery_user.url, recoveryKey);
  const patsAfterRecovery = await patSnapshot(page);
  assert(recoveredSetup?.readiness?.ready === true, "recovery endpoint did not become ready");
  assert(primaryAfter?.readiness?.ready === true, "primary endpoint readiness was affected");
  assert(
    JSON.stringify(assetsAfterRecovery) === JSON.stringify(assetsAfterFailure),
    "idempotent retry duplicated Langflow assets",
  );
  assert(
    JSON.stringify(patsAfterRecovery.token_ids) === JSON.stringify(patsAfterFailure.token_ids),
    "idempotent retry duplicated PATs",
  );
  const gate = await fetch(`${config.recoveryUrl}/__validation/state`).then((response) => response.json());
  assert(gate.injected_failures === 1 && gate.run_attempts >= 2, "recovery gate evidence is incomplete");
  result.recovery = {
    first_bootstrap_status: firstBootstrap.status,
    retry_bootstrap_status: 200,
    transient_failure_recovered_in_request: firstBootstrap.status === 200,
    assets_before: assetsBefore,
    assets_after_failure: assetsAfterFailure,
    assets_after_recovery: assetsAfterRecovery,
    pat_count_before: patsBefore.token_ids.length,
    pat_count_after_failure: patsAfterFailure.token_ids.length,
    pat_count_after_recovery: patsAfterRecovery.token_ids.length,
    duplicate_free: true,
    gate,
  };
  result.endpoint_independence.after_recovery = {
    primary_ready: primaryAfter.readiness.ready,
    recovery_ready: recoveredSetup.readiness.ready,
    distinct_endpoint_ids: primaryEndpointId !== recoveryEndpointId,
    distinct_project_ids:
      primaryAfter.project.id !== recoveredSetup.project.id,
  };
  assert(result.endpoint_independence.after_recovery.distinct_endpoint_ids, "endpoint IDs collided");
  assert(result.endpoint_independence.after_recovery.distinct_project_ids, "project IDs collided");
  await screenshot(page, "07-bootstrap-recovered-without-duplicates");

  assert(result.console_errors.length === 0, "unexpected browser console errors");
  assert(result.page_errors.length === 0, "unexpected browser page errors");
  assert(result.unexpected_http_errors.length === 0, "unexpected browser HTTP errors");
  const expectedFailureCount = firstBootstrap.status === 502 ? 4 : 3;
  assert(
    result.expected_http_errors.length === expectedFailureCount,
    "negative browser checks did not emit the expected policy failures",
  );
  result.ok = true;
  await context.close();
} finally {
  await browser.close();
  await fs.writeFile(
    path.join(config.evidenceDir, "negative-recovery-result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
    { mode: 0o600 },
  );
}

console.log(JSON.stringify({ ok: result.ok, evidence_dir: config.evidenceDir }));
