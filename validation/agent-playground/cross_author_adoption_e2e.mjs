#!/usr/bin/env node

import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || "playwright");

const config = {
  agentHubUrl: process.env.AGENT_HUB_URL || "http://localhost:18080/AgentHub.html",
  boiUrl: process.env.BOI_URL || "http://localhost:28005",
  keycloakUrl: process.env.KEYCLOAK_URL || "http://localhost:18082",
  langflowUrl: process.env.LANGFLOW_URL || "http://localhost:7866",
  langflowPlaygroundUrl:
    process.env.LANGFLOW_PLAYGROUND_URL
    || process.env.LANGFLOW_URL
    || "http://localhost:7866",
  langflowContainerUrl:
    process.env.LANGFLOW_CONTAINER_URL || "http://host.docker.internal:7866",
  identityFile:
    process.env.AGENT_HUB_IDENTITY_FILE || "/tmp/boi-ap-agent-hub-sso-users.json",
  boiSsoPassword: process.env.BOI_SSO_PASSWORD || "",
  agentHubAdopterPassword: process.env.AGENT_HUB_ADOPTER_PASSWORD || "",
  langflowIdentityFile:
    process.env.LANGFLOW_IDENTITY_FILE || "/tmp/boi-ap-negative-users.json",
  flowFile:
    process.env.SHARED_FLOW_FILE || "langflow/flows/boi_wiki_agent_loop.json",
  componentFile:
    process.env.SHARED_COMPONENT_FILE ||
    "validation/agent-playground/assets/shared_evidence_priority_selector.py",
  evidenceDir:
    process.env.PLAYWRIGHT_EVIDENCE_DIR ||
    "artifacts/agent-playground-cross-author",
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || "",
};

const identities = JSON.parse(await fs.readFile(config.identityFile, "utf8"));
const langflowIdentities = JSON.parse(
  await fs.readFile(config.langflowIdentityFile, "utf8"),
);
const langflowAccount = (
  langflowIdentities.recovery_user
  || langflowIdentities.users?.["100002"]
);
if (
  !identities["100001"]
  || !identities["100002"]
  || !identities["2074795"]
  || !langflowAccount?.password
) {
  throw new Error("validation identities are incomplete");
}

const runId =
  process.env.PLAYWRIGHT_RUN_ID
  || new Date().toISOString().replace(/\W/g, "").slice(0, 15);
const sharedFlowArtifact = JSON.parse(await fs.readFile(config.flowFile, "utf8"));
const flowTitle = `Shared ${sharedFlowArtifact.name || "BoI Flow"} ${runId}`;
const componentTitle = `${
  path.basename(config.componentFile).includes("shared_gemma")
    ? "Shared Gemma Simulation Agent"
    : "Shared Agent Component"
} ${runId}`;
const endpointAlias = `Cross-author Langflow ${runId}`;

const result = {
  ok: false,
  run_id: runId,
  authorship: {},
  approval: {},
  langflow_key: {},
  agent_hub_deploy: {},
  playground_adoption: {},
  composition: {},
  validation: {},
  screenshots: [],
  console_errors: [],
  ignored_console_errors: [],
  page_errors: [],
  unexpected_http_errors: [],
  ignored_http_errors: [],
};

await fs.mkdir(config.evidenceDir, { recursive: true });

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function prepareKeycloakUsers() {
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
  const token = String((await tokenResponse.json()).access_token || "");
  const headers = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
  const profileResponse = await fetch(
    `${config.keycloakUrl}/admin/realms/boi-validation/users/profile`,
    { headers },
  );
  assert(
    profileResponse.ok,
    `Keycloak user profile lookup returned ${profileResponse.status}`,
  );
  const profile = await profileResponse.json();
  if (!(profile.attributes || []).some((item) => item.name === "empno")) {
    profile.attributes = [
      ...(profile.attributes || []),
      {
        name: "empno",
        displayName: "Employee number",
        validations: { length: { min: 1, max: 32 } },
        permissions: { view: ["admin", "user"], edit: ["admin"] },
        multivalued: false,
      },
    ];
    const profileUpdate = await fetch(
      `${config.keycloakUrl}/admin/realms/boi-validation/users/profile`,
      {
        method: "PUT",
        headers,
        body: JSON.stringify(profile),
      },
    );
    assert(
      profileUpdate.ok,
      `Keycloak empno profile update returned ${profileUpdate.status}`,
    );
  }
  for (const employeeId of ["100001", "100002", "2074795"]) {
    const search = await fetch(
      `${config.keycloakUrl}/admin/realms/boi-validation/users?username=${employeeId}&exact=true`,
      { headers },
    );
    assert(search.ok, `Keycloak user lookup for ${employeeId} returned ${search.status}`);
    let user = (await search.json())[0];
    if (!user) {
      const created = await fetch(
        `${config.keycloakUrl}/admin/realms/boi-validation/users`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            username: employeeId,
            enabled: true,
            emailVerified: true,
            email: `${employeeId}@boi.validation`,
            attributes: { empno: [employeeId] },
          }),
        },
      );
      assert(
        created.status === 201,
        `Keycloak user creation for ${employeeId} returned ${created.status}`,
      );
      const refreshed = await fetch(
        `${config.keycloakUrl}/admin/realms/boi-validation/users?username=${employeeId}&exact=true`,
        { headers },
      );
      user = (await refreshed.json())[0];
    }
    const updated = await fetch(
      `${config.keycloakUrl}/admin/realms/boi-validation/users/${user.id}`,
      {
        method: "PUT",
        headers,
        body: JSON.stringify({
          ...user,
          enabled: true,
          attributes: {
            ...(user.attributes || {}),
            empno: [employeeId],
          },
        }),
      },
    );
    assert(
      updated.status === 204,
      `Keycloak empno update for ${employeeId} returned ${updated.status}`,
    );
    const reset = await fetch(
      `${config.keycloakUrl}/admin/realms/boi-validation/users/${user.id}/reset-password`,
      {
        method: "PUT",
        headers,
        body: JSON.stringify({
          type: "password",
          value: identities[employeeId],
          temporary: false,
        }),
      },
    );
    assert(
      reset.status === 204,
      `Keycloak password reset for ${employeeId} returned ${reset.status}`,
    );
  }
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
  if (status === 403 && pathname === "/api/v1/auto_login") return true;
  if (status === 401 && pathname === "/api/v1/users/me") return true;
  if (
    status === 403
    && method === "GET"
    && ["/api/v1/users/me", "/api/v1/admin/settings"].includes(pathname)
  ) {
    return true;
  }
  return false;
}

function diagnostics(page, scope) {
  page.on("console", (message) => {
    const text = message.text();
    if (
      message.type() === "error"
      && !text.startsWith("Failed to load resource:")
      && !text.includes("favicon")
      && !text.startsWith("Duplicate request:")
    ) {
      const item = { scope, text: text.slice(0, 500) };
      if (
        scope.startsWith("agent-hub-")
        && text.startsWith("Failed to load components: TypeError: Failed to fetch")
      ) {
        result.ignored_console_errors.push({
          ...item,
          reason: "immutable Agent Hub optional component lookup during auth bootstrap",
        });
      } else {
        result.console_errors.push(item);
      }
    }
  });
  page.on("pageerror", (error) => {
    result.page_errors.push({
      scope,
      text: String(error.message || error).slice(0, 500),
    });
  });
  page.on("response", (response) => {
    if (response.status() < 400) return;
    const url = new URL(response.url());
    const item = {
      scope,
      status: response.status(),
      method: response.request().method(),
      url: `${url.origin}${url.pathname}`,
    };
    const credentialRefreshBootstrap = (
      scope === "boi-playground-100002"
      && item.status === 401
      && item.method === "GET"
      && /^\/api\/agent-playground\/endpoints\/[^/]+\/projects$/.test(url.pathname)
    );
    if (expectedHttp(item.status, item.method, url.pathname) || credentialRefreshBootstrap) {
      result.ignored_http_errors.push({
        ...item,
        ...(credentialRefreshBootstrap
          ? { reason: "existing endpoint credential is replaced immediately after SSO bootstrap" }
          : {}),
      });
    } else {
      result.unexpected_http_errors.push(item);
    }
  });
}

async function loginAgentHub(browser, employeeId) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  diagnostics(page, `agent-hub-${employeeId}`);
  await page.goto(config.agentHubUrl, { waitUntil: "domcontentloaded" });
  const username = page.locator("#username");
  await Promise.race([
    username.waitFor({ state: "visible", timeout: 20_000 }).catch(() => null),
    page.waitForFunction(
      () => Boolean(localStorage.getItem("agenthub_token")),
      null,
      { timeout: 20_000 },
    ).catch(() => null),
  ]);
  if (await username.isVisible().catch(() => false)) {
    await page.locator("#username").fill(employeeId);
    const password = (
      employeeId === "100002" && config.agentHubAdopterPassword
        ? config.agentHubAdopterPassword
        : identities[employeeId]
    );
    await page.locator("#password").fill(password);
    await Promise.all([
      page.waitForURL((url) => url.origin === new URL(config.agentHubUrl).origin),
      page.locator("#kc-login").click(),
    ]);
  }
  await page.waitForFunction(() => Boolean(localStorage.getItem("agenthub_token")));
  const me = await page.evaluate(async () => {
    const response = await fetch("/api/v1/users/me");
    return { status: response.status, body: await response.json() };
  });
  assert(me.status === 200, `Agent Hub user ${employeeId} was not authenticated`);
  assert(me.body.employee_id === employeeId, `Agent Hub principal mismatch for ${employeeId}`);
  return { context, page, user: me.body };
}

async function uploadAsset(page, filePath, title, description) {
  await page.getByRole("button", { name: /제출|Upload/i }).first().click();
  const modal = page.locator(".modal");
  await modal.waitFor();
  const chooserPromise = page.waitForEvent("filechooser");
  await modal.locator(".dropzone").click();
  const chooser = await chooserPromise;
  await chooser.setFiles(path.resolve(filePath));
  await modal.getByRole("button", { name: /다음|Next/i }).click();
  const fields = modal.locator("input.input");
  await fields.nth(0).fill(title);
  await fields.nth(1).fill(description);
  await modal.locator("textarea").fill(
    [
      "## 목적",
      "",
      "다른 작성자가 승인된 Agent Hub 자산을 자신의 Langflow endpoint로 가져와",
      "exact Flow 단위로 검증하고 BoI Action으로 연결하는 통합 검증 자산입니다.",
      "",
      "## 보안과 권한",
      "",
      "- API Key와 PAT를 파일에 포함하지 않습니다.",
      "- Wiki 권한은 Action 호출자의 단기 run token으로 결정합니다.",
      "- Langflow와 Agent Hub 소스를 수정하지 않습니다.",
    ].join("\n"),
  );
  await modal.getByRole("button", { name: /다음|Next/i }).click();
  const selects = modal.locator("select.select");
  await selects.nth(0).selectOption("1.9.1");
  await selects.nth(1).selectOption({ index: 0 });
  const createdResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "POST"
      && url.pathname === "/api/v1/components"
    );
  });
  await modal.getByRole("button", { name: /제출하기|Submit/i }).click();
  const response = await createdResponse;
  assert(response.status() === 201, `Agent Hub upload returned HTTP ${response.status()}`);
  const created = await response.json();
  await page.waitForTimeout(1700);
  return created;
}

async function createLangflowKey(browser) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  diagnostics(page, "langflow-api-key-100002");
  try {
    await page.goto(`${config.langflowUrl}/settings/api-keys`, {
      waitUntil: "domcontentloaded",
    });
    const password = page.locator('input[type="password"]');
    const addNew = page.getByRole("button", { name: /Add New/i });
    await Promise.race([
      password.waitFor({ state: "visible", timeout: 20_000 }).catch(() => null),
      addNew.waitFor({ state: "visible", timeout: 20_000 }).catch(() => null),
    ]);
    if (await password.isVisible().catch(() => false)) {
      await page
        .locator('input[name="username"], input[type="text"]')
        .first()
        .fill(langflowAccount.username);
      await password.fill(langflowAccount.password);
      await Promise.all([
        page.waitForURL((url) => !url.pathname.endsWith("/login")),
        page.getByRole("button", { name: "Sign In", exact: true }).click(),
      ]);
      await page.goto(`${config.langflowUrl}/settings/api-keys`, {
        waitUntil: "domcontentloaded",
      });
    }
    await addNew.waitFor({ state: "visible", timeout: 30_000 });
    await addNew.click();
    const dialog = page.getByRole("dialog");
    await dialog.waitFor();
    await dialog.locator("input").first().fill(`Agent Hub cross-author ${runId}`);
    const responsePromise = page.waitForResponse((response) => (
      response.request().method() === "POST"
      && /api[_/-]?keys?/i.test(new URL(response.url()).pathname)
    ));
    await dialog.getByRole("button", { name: /Generate|Create/i }).click();
    const response = await responsePromise;
    assert(response.ok(), `Langflow API Key creation returned HTTP ${response.status()}`);
    const payload = await response.json();
    const apiKey = String(payload.api_key || payload.key || payload.token || "");
    assert(apiKey.length >= 16, "Langflow did not return the API Key once");
    const done = dialog.getByRole("button", { name: "Done", exact: true });
    const close = dialog.getByRole("button", { name: "Close", exact: true });
    if (await done.count()) await done.click();
    else if (await close.count()) await close.click();
    else await page.keyboard.press("Escape");
    assert(!(await page.locator("body").innerText()).includes(apiKey), "API Key remained visible");
    result.langflow_key = {
      owner: langflowAccount.username,
      fingerprint: fingerprint(apiKey),
      raw_key_visible_after_close: false,
    };
    return apiKey;
  } finally {
    await context.close();
  }
}

async function loginBoi(browser) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1050 } });
  const page = await context.newPage();
  diagnostics(page, "boi-playground-100002");
  await page.goto(`${config.boiUrl}/playground`, { waitUntil: "domcontentloaded" });
  if (page.url().includes("/protocol/openid-connect/")) {
    const authorization = new URL(page.url());
    assert(authorization.searchParams.get("state"), "BoI OIDC state is missing");
    assert(authorization.searchParams.get("nonce"), "BoI OIDC nonce is missing");
    assert(
      authorization.searchParams.get("code_challenge_method") === "S256",
      "BoI OIDC PKCE S256 is missing",
    );
    await page.locator("#username").fill("100002");
    await page.locator("#password").fill(
      config.boiSsoPassword || identities["100002"],
    );
    await Promise.all([
      page.waitForURL((url) => url.origin === new URL(config.boiUrl).origin),
      page.locator("#kc-login").click(),
    ]);
  }
  await page.locator("[data-agent-playground]").waitFor();
  const state = await page.evaluate(async () => {
    const response = await fetch("/api/agent-playground");
    return { status: response.status, body: await response.json() };
  });
  assert(state.status === 200, "BoI Playground state failed");
  assert(state.body.identity?.employee_id === "100002", "BoI SSO principal mismatch");
  assert(state.body.identity?.auth_source === "keycloak", "BoI is not using OIDC Principal");
  return { context, page, state: state.body };
}

async function ensurePlaygroundEndpoint(page, apiKey) {
  const normalizedTarget = config.langflowPlaygroundUrl.replace(/\/+$/, "");
  let state = await page.evaluate(async () => {
    const response = await fetch("/api/agent-playground");
    return response.json();
  });
  const matchingEndpoints = (state.endpoints || []).filter(
    (endpoint) => String(endpoint.base_url || "").replace(/\/+$/, "") === normalizedTarget,
  );
  let targetEndpoint = (state.endpoints || []).find(
    (endpoint) => endpoint.endpoint_id === state.default_endpoint_id,
  ) || matchingEndpoints[0];
  let created = false;
  if (!targetEndpoint) {
    const settings = page.locator(".agent-playground-connection-settings");
    await settings.waitFor({ state: "visible" });
    if (!(await settings.evaluate((details) => details.open))) {
      await settings.locator("summary").click();
    }
    await page.locator("[data-new-endpoint]").click();
    const form = page.locator("[data-endpoint-form]");
    await form.locator('[name="name"]').fill(endpointAlias);
    await form.locator('[name="base_url"]').fill(normalizedTarget);
    await form.locator('[name="api_key"]').fill(apiKey);
    const testedPromise = page.waitForResponse((response) => (
      response.request().method() === "POST"
      && new URL(response.url()).pathname === "/api/agent-playground/endpoints/test"
    ));
    await form.locator("[data-test-unsaved]").click();
    const tested = await testedPromise;
    assert(tested.ok(), `Playground endpoint test returned HTTP ${tested.status()}`);
    const savedPromise = page.waitForResponse((response) => (
      response.request().method() === "POST"
      && new URL(response.url()).pathname === "/api/agent-playground/endpoints"
    ));
    await form.getByRole("button", { name: "저장", exact: true }).click();
    const saved = await savedPromise;
    assert(saved.ok(), `Playground endpoint save returned HTTP ${saved.status()}`);
    targetEndpoint = (await saved.json()).endpoint;
    created = true;
  } else {
    const updated = await page.evaluate(
      async ({ endpointId, name, baseUrl, key }) => {
        const response = await fetch(
          `/api/agent-playground/endpoints/${encodeURIComponent(endpointId)}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name,
              base_url: baseUrl,
              api_key: key,
            }),
          },
        );
        return { status: response.status, body: await response.json() };
      },
      {
        endpointId: targetEndpoint.endpoint_id,
        name: targetEndpoint.name || endpointAlias,
        baseUrl: normalizedTarget,
        key: apiKey,
      },
    );
    assert(
      updated.status === 200,
      `Playground endpoint ${targetEndpoint.endpoint_id} update returned HTTP ${updated.status}: ${JSON.stringify(updated.body)}`,
    );
    targetEndpoint = updated.body.endpoint;
  }

  const endpointSelect = page.locator("[data-endpoint-select]");
  if (!created) {
    await endpointSelect.waitFor({ state: "attached" });
  }
  if (!created && (await endpointSelect.inputValue()) !== targetEndpoint.endpoint_id) {
    await endpointSelect.selectOption(targetEndpoint.endpoint_id);
    await page.waitForFunction(
      (endpointId) => document.querySelector("[data-endpoint-select]")?.value === endpointId,
      targetEndpoint.endpoint_id,
    );
  }
  state = await page.evaluate(async () => {
    const response = await fetch("/api/agent-playground");
    return response.json();
  });
  const setup = state.endpoint_setups?.[targetEndpoint.endpoint_id] || {};
  if (setup.onboarding?.required) {
    const bootstrap = page.locator("[data-onboarding-bootstrap]");
    await bootstrap.waitFor({ state: "visible" });
    const responsePromise = page.waitForResponse((response) => (
      response.request().method() === "POST"
      && new URL(response.url()).pathname === "/api/agent-playground/bootstrap"
    ), { timeout: 180_000 });
    await bootstrap.click();
    const response = await responsePromise;
    assert(response.ok(), `Playground endpoint bootstrap returned HTTP ${response.status()}`);
    await page.locator('[data-onboarding-stage="flow"]').waitFor({
      state: "visible",
      timeout: 180_000,
    });
    await page.locator("[data-onboarding-finish]").click();
  }
  await page.locator("[data-workbench-only]").first().waitFor({ state: "visible" });
  return targetEndpoint;
}

async function beginPlaygroundAdoption(page) {
  await page.locator('[data-workbench-step="create"]').click();
  const endpointSelect = page.locator("[data-endpoint-select]");
  await endpointSelect.waitFor({ state: "visible" });
  const state = await page.evaluate(async () => {
    const response = await fetch("/api/agent-playground");
    return response.json();
  });
  const normalizedTarget = config.langflowPlaygroundUrl.replace(/\/+$/, "");
  const targetEndpoint = (state.endpoints || []).find(
    (endpoint) => endpoint.endpoint_id === state.default_endpoint_id,
  ) || (state.endpoints || []).find((endpoint) => (
    String(endpoint.base_url || endpoint.endpoint || "").replace(/\/+$/, "") === normalizedTarget
  ));
  assert(targetEndpoint, `Playground endpoint ${normalizedTarget} is missing`);
  await endpointSelect.selectOption(targetEndpoint.endpoint_id);
  const projectSelect = page.locator("[data-project-select]");
  await projectSelect.waitFor();
  await page.waitForFunction(() => {
    const select = document.querySelector("[data-project-select]");
    return select && !select.disabled && [...select.options].some(
      (option) => option.textContent.includes("boi-100002"),
    );
  });
  await projectSelect.selectOption({
    label: (await projectSelect.locator("option").allTextContents())
      .find((text) => text.includes("boi-100002")),
  });
  await page.locator('[data-workbench-step="hub"]').click();
  const initialCatalogResponse = page.waitForResponse((response) => (
    response.request().method() === "GET"
    && new URL(response.url()).pathname === "/api/agent-playground/agent-hub/assets"
  ));
  await page.locator('[data-hub-mode="shared"]').click();
  await initialCatalogResponse;
  const search = page.locator("[data-hub-search-form]");
  await search.waitFor({ state: "visible" });
  await search.locator('input[name="search"]').fill(runId);
  const responsePromise = page.waitForResponse((response) => (
    response.request().method() === "GET"
    && new URL(response.url()).pathname === "/api/agent-playground/agent-hub/assets"
  ));
  await search.getByRole("button", { name: "승인 자산 찾기" }).click();
  const response = await responsePromise;
  assert(response.ok(), `Playground Agent Hub catalog returned HTTP ${response.status()}`);
  const catalog = await response.json();
  const cards = page.locator(".agent-playground-hub-asset");
  await cards.first().waitFor();
  assert(await cards.count() >= 2, "Playground did not show the approved shared assets");
  // Switching to the shared-assets tab starts an initial catalog request. Let
  // that render settle before interacting with the explicit search result so
  // a late response cannot replace a button during the user click.
  await page.waitForTimeout(750);
  for (const title of [flowTitle, componentTitle]) {
    const card = page.locator(".agent-playground-hub-asset").filter({ hasText: title });
    const asset = (catalog.items || []).find((candidate) => candidate.title === title);
    const authorLabel = String(asset?.author?.name || asset?.author?.employee_id || "");
    assert(await card.count() === 1, `Playground asset missing: ${title}`);
    assert(authorLabel, `source author metadata is missing: ${title}`);
    assert((await card.innerText()).includes(authorLabel), "source author is not visible");
    await card.getByRole("button", { name: "이 자산 사용" }).click();
    await page.waitForFunction(
      (assetTitle) => [...document.querySelectorAll(".agent-playground-hub-asset")]
        .some((node) => node.textContent.includes(assetTitle) && node.dataset.selected === "true"),
      title,
    );
  }
  assert(
    await page.locator("[data-hub-validation-profile]").inputValue()
      === "boi_knowledge_draft",
    "shared asset adoption did not default to the Wiki/Ontology validation profile",
  );
  const beginResponse = page.waitForResponse((candidate) => (
    candidate.request().method() === "POST"
    && new URL(candidate.url()).pathname === "/api/agent-playground/agent-hub/adoptions"
  ));
  await page.locator("[data-hub-adoption-begin]").click();
  const created = await beginResponse;
  assert(created.ok(), `Playground adoption begin returned HTTP ${created.status()}`);
  const body = await created.json();
  await screenshot(page, "01-playground-approved-assets-pinned");
  return body.adoption;
}

async function deployFromAgentHub(page, asset, apiKey, { targetFlowName = "" } = {}) {
  await page.goto(
    `${config.agentHubUrl}#/${asset.type === "json" ? "flow" : "component"}/${asset.id}`,
    { waitUntil: "domcontentloaded" },
  );
  await page.getByRole("button", { name: "배포", exact: true }).waitFor();
  await page.getByRole("button", { name: "배포", exact: true }).click();
  const modal = page.locator(".modal").filter({ hasText: "Agent Builder에 배포" });
  await modal.waitFor();
  const existingUrl = modal.getByText(config.langflowContainerUrl, { exact: true }).first();
  await existingUrl.waitFor({ state: "visible", timeout: 10_000 }).catch(() => null);
  if (!(await existingUrl.count())) {
    await modal.getByRole("button", { name: /엔드포인트 추가/ }).click();
    const form = modal.locator(".card.card-pad").filter({ hasText: "Agent Builder 주소" });
    const inputs = form.locator("input.input");
    await inputs.nth(0).fill(endpointAlias);
    await inputs.nth(1).fill(config.langflowContainerUrl);
    await inputs.nth(2).fill(apiKey);
    const testResponse = page.waitForResponse((response) => (
      response.request().method() === "POST"
      && new URL(response.url()).pathname === "/api/v1/deploy/test"
    ));
    await form.getByRole("button", { name: "연결 테스트" }).click();
    const tested = await testResponse;
    assert(tested.ok(), `Agent Hub endpoint test returned HTTP ${tested.status()}`);
    await form.getByText(/Agent Builder 1\.11/).waitFor();
    const saveResponse = page.waitForResponse((response) => (
      response.request().method() === "POST"
      && new URL(response.url()).pathname === "/api/v1/deploy/endpoints"
    ));
    await form.getByRole("button", { name: "저장", exact: true }).click();
    assert((await saveResponse).ok(), "Agent Hub endpoint save failed");
  } else {
    const row = existingUrl.locator("xpath=../..");
    await row.click();
    await row.getByTitle("수정").click();
    const form = modal.locator(".card.card-pad").filter({ hasText: "Agent Builder 주소" });
    const inputs = form.locator("input.input");
    await inputs.nth(2).fill(apiKey);
    const testResponse = page.waitForResponse((response) => (
      response.request().method() === "POST"
      && new URL(response.url()).pathname === "/api/v1/deploy/test"
    ));
    await form.getByRole("button", { name: "연결 테스트" }).click();
    assert((await testResponse).ok(), "Agent Hub endpoint key rotation test failed");
    await form.getByText(/Agent Builder 1\.11/).waitFor();
    const saveResponse = page.waitForResponse((response) => (
      response.request().method() === "PATCH"
      && /\/api\/v1\/deploy\/endpoints\/.+/.test(new URL(response.url()).pathname)
    ));
    await form.getByRole("button", { name: "저장", exact: true }).click();
    assert((await saveResponse).ok(), "Agent Hub endpoint key rotation failed");
  }
  await page.waitForFunction(
    () => [...document.querySelectorAll(".modal select.select option")]
      .some((option) => option.textContent.includes("boi-100002")),
  );
  const project = modal.locator("select.select").first();
  await project.waitFor();
  await project.selectOption({
    label: (await project.locator("option").allTextContents())
      .find((text) => text.includes("boi-100002")),
  });
  if (targetFlowName) {
    await page.waitForFunction(
      ({ name }) => [...document.querySelectorAll(".modal select option")]
        .some((option) => option.textContent.includes(name)),
      { name: targetFlowName },
    );
    const flowSelect = modal.locator("select.select").last();
    await flowSelect.selectOption({
      label: (await flowSelect.locator("option").allTextContents())
        .find((text) => text.includes(targetFlowName)),
    });
  }
  const deployResponse = page.waitForResponse((response) => (
    response.request().method() === "POST"
    && new URL(response.url()).pathname === `/api/v1/deploy/components/${asset.id}`
  ));
  await modal.getByRole("button", { name: "배포", exact: true }).last().click();
  const response = await deployResponse;
  assert(response.ok(), `Agent Hub deployment returned HTTP ${response.status()}`);
  const deployed = await response.json();
  await modal.getByText("배포 완료!").waitFor();
  await screenshot(
    page,
    asset.type === "json" ? "02-agent-hub-flow-deployed" : "03-agent-hub-component-added",
  );
  return deployed;
}

async function finishPlaygroundAdoption(page, adoption, expectedFlowId) {
  await page.bringToFront();
  const discoverResponse = page.waitForResponse((response) => (
    response.request().method() === "POST"
    && new URL(response.url()).pathname.endsWith(`/adoptions/${adoption.adoption_id}/discover`)
  ));
  await page.locator("[data-hub-adoption-discover]").click();
  const discoveredResponse = await discoverResponse;
  assert(discoveredResponse.ok(), "Playground adoption discovery failed");
  const discovered = await discoveredResponse.json();
  assert(
    discovered.candidates.some((item) => item.flow_id === expectedFlowId),
    "Agent Hub exact Flow was not rediscovered",
  );
  const candidate = page.locator(".agent-playground-hub-candidates article").filter({
    hasText: expectedFlowId,
  });
  await candidate.waitFor();
  const confirmResponse = page.waitForResponse((response) => (
    response.request().method() === "POST"
    && new URL(response.url()).pathname.endsWith(`/adoptions/${adoption.adoption_id}/confirm`)
  ));
  await candidate.getByRole("button", { name: "이 exact Flow 가져오기" }).click();
  const confirmedResponse = await confirmResponse;
  assert(confirmedResponse.ok(), "Playground exact Flow confirmation failed");
  const confirmed = await confirmedResponse.json();
  assert(confirmed.deployment.flow_id === expectedFlowId, "confirmed Flow ID changed");
  assert(
    confirmed.deployment.source_assets.every(
      (asset) => asset.author.employee_id === "100001",
    ),
    "source authorship was not preserved",
  );
  await screenshot(page, "04-playground-exact-flow-confirmed");
  return confirmed;
}

async function createActualTask(page) {
  const traceId = `trace-cross-author-${runId}`;
  const eventId = `evt-cross-author-${runId}`;
  const response = await page.evaluate(async ({ traceId, eventId }) => {
    const result = await fetch("/api/actions/invoke", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action_key: "manual.equipment.review_root_cause",
        event: {
          event_id: eventId,
          event_type: "root_cause.analysis.requested.v1",
          trace_id: traceId,
        },
        payload: {
          title: "Cross-author component composition Task",
          equipment_id: "EQ-AP-CROSS-AUTHOR",
          owner: "100002",
        },
        dry_run: false,
      }),
    });
    return { status: result.status, body: await result.json() };
  }, { traceId, eventId });
  assert(response.status === 200, `actual Task creation returned HTTP ${response.status}`);
  assert(response.body.status === "manual_required", "actual Task was not recorded");
  return {
    taskRef: `task:${response.body.request_id}`,
    traceId,
    eventId,
  };
}

async function validateDisconnected(page, confirmed, taskRef) {
  const deployment = confirmed.deployment;
  const response = await page.evaluate(async ({ flowId, deployment, taskRef }) => {
    const request = await fetch(
      `/api/agent-playground/flows/${encodeURIComponent(flowId)}/validate`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          endpoint_id: deployment.endpoint_id,
          project_id: deployment.project_id,
          artifact_version: deployment.asset_version || "1.1.0",
          artifact_checksum: deployment.artifact_checksum,
          task_ref: taskRef,
        }),
      },
    );
    return { status: request.status, body: await request.json() };
  }, { flowId: deployment.flow_id, deployment, taskRef });
  assert(response.status === 200, "disconnected Flow validation request failed");
  assert(response.body.validation_status === "blocked", "disconnected component was not blocked");
  assert(
    response.body.failure_reason === "disconnected_component",
    `unexpected disconnected failure: ${response.body.failure_reason}`,
  );
  return response.body;
}

async function composeAdoption(page, adoption, flowId, componentAssetId) {
  const response = await page.evaluate(
    async ({ adoptionId, flowId, componentAssetId }) => {
      const request = await fetch(
        `/api/agent-playground/agent-hub/adoptions/${encodeURIComponent(adoptionId)}/compose`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            flow_id: flowId,
            component_asset_id: componentAssetId,
            replace_agent_slot: true,
          }),
        },
      );
      return { status: request.status, body: await request.json() };
    },
    {
      adoptionId: adoption.adoption_id,
      flowId,
      componentAssetId,
    },
  );
  assert(response.status === 200, `component compose returned HTTP ${response.status}`);
  assert(response.body.status === "connected", `component compose failed: ${response.body.reason}`);
  assert(
    response.body.previous_checksum !== response.body.live_checksum,
    "component composition did not create a new exact checksum revision",
  );
  assert(
    response.body.graph_health?.end_to_end_reachable,
    "composed Flow has no Chat Input to Chat Output path",
  );
  assert(
    response.body.graph_health?.connected_component_ids?.includes(componentAssetId),
    "composed component is not on the execution path",
  );
  return response;
}

async function validateAndDraft(page, flowId, taskRef, endpointId, projectId) {
  await page.locator('[data-workbench-step="create"]').click();
  const flowItem = page.locator(
    `.agent-playground-flow-item[data-flow-id="${flowId}"]`,
  );
  await flowItem.waitFor({ state: "attached" });
  if (
    !(await flowItem.isVisible().catch(() => false))
    && await flowItem.getAttribute("data-active") !== "true"
  ) {
    const history = page.locator(".agent-playground-flow-history");
    if (await history.count()) {
      await history.locator("summary").click();
    }
  }
  if (await flowItem.isVisible().catch(() => false)) {
    await flowItem.click();
  } else {
    assert(
      await flowItem.getAttribute("data-active") === "true",
      "exact Flow is neither visible nor selected for validation",
    );
  }
  await page.locator('[data-workbench-step="test"]').click();
  const taskSelect = page.locator("[data-task-select]");
  await taskSelect.waitFor();
  const listed = await page.waitForFunction(
    (expected) => [...(document.querySelector("[data-task-select]")?.options || [])]
      .some((option) => option.value === expected),
    taskRef,
    { timeout: 5_000 },
  ).then(() => true).catch(() => false);
  if (listed) {
    await taskSelect.selectOption(taskRef);
  } else {
    await page.locator(".agent-playground-task-anchor summary").click();
    await page.locator("[name='manual_task_ref']").fill(taskRef);
  }
  const validationResponse = page.waitForResponse((response) => (
    response.request().method() === "POST"
    && new URL(response.url()).pathname === `/api/agent-playground/flows/${flowId}/validate`
  ), { timeout: 200_000 });
  await page.locator("[data-validate-flow]").click();
  const validatedResponse = await validationResponse;
  assert(validatedResponse.ok(), `Flow validation returned HTTP ${validatedResponse.status()}`);
  const validated = await validatedResponse.json();
  assert(validated.validation_status === "action_ready", validated.failure_reason);

  await page.reload({ waitUntil: "domcontentloaded" });
  await page.locator("[data-agent-playground]").waitFor();
  await page.locator('[data-workbench-step="create"]').click();
  const endpointSelect = page.locator("[data-endpoint-select]");
  await endpointSelect.waitFor({ state: "visible" });
  await endpointSelect.selectOption(endpointId);
  const projectSelect = page.locator("[data-project-select]");
  await page.waitForFunction(
    ({ expectedEndpoint, expectedProject }) => {
      const endpoint = document.querySelector("[data-endpoint-select]");
      const project = document.querySelector("[data-project-select]");
      return (
        endpoint?.value === expectedEndpoint
        && project
        && !project.disabled
        && [...project.options].some((option) => option.value === expectedProject)
      );
    },
    { expectedEndpoint: endpointId, expectedProject: projectId },
  );
  await projectSelect.selectOption(projectId);
  const refreshedFlowItem = page.locator(
    `.agent-playground-flow-item[data-flow-id="${flowId}"]`,
  );
  await refreshedFlowItem.waitFor({ state: "visible" });
  await refreshedFlowItem.click();
  await page.locator('[data-workbench-step="action"]').click();
  await page.locator('input[name="action_scope"][value="team"]').check();
  await page.locator("[data-action-team]").selectOption("aix-tf");
  const createActionButton = page.locator("[data-create-action]");
  await createActionButton.waitFor({ state: "visible" });
  await page.waitForFunction(() => {
    const button = document.querySelector("[data-create-action]");
    return button instanceof HTMLButtonElement && !button.disabled;
  });
  const draftResponse = page.waitForResponse((response) => (
    response.request().method() === "POST"
    && /\/api\/agent-playground\/deployments\/.+\/action-draft$/.test(
      new URL(response.url()).pathname,
    )
  ), { timeout: 60_000 });
  await createActionButton.evaluate((button) => button.click());
  const createdResponse = await draftResponse;
  assert(createdResponse.ok(), "Action draft creation failed");
  const created = await createdResponse.json();
  await screenshot(page, "05-playground-action-draft-ready");
  return { validated, draft: created };
}

const browser = await chromium.launch({
  headless: true,
  executablePath: config.executablePath || undefined,
  args: ["--no-sandbox"],
});

let authorSession;
let approverSession;
let adopterHubSession;
let boiSession;
try {
  await prepareKeycloakUsers();
  execFileSync(
    "python",
    [
      "validation/agent-hub/prepare_e2e_user_mapping.py",
      "--identity-file",
      config.identityFile,
      "--keycloak-url",
      config.keycloakUrl,
      "--reset-endpoints-for",
      "100002",
    ],
    { stdio: "inherit" },
  );
  authorSession = await loginAgentHub(browser, "100001");
  assert(authorSession.user.role === "user", "author must not be an Agent Hub admin");
  const flowAsset = await uploadAsset(
    authorSession.page,
    config.flowFile,
    flowTitle,
    "BoI Wiki·Ontology 근거와 개인 초안을 연결하는 공유 Flow입니다.",
  );
  const componentAsset = await uploadAsset(
    authorSession.page,
    config.componentFile,
    componentTitle,
    "근거 provenance와 confidence를 보존해 우선순위를 정하는 공유 컴포넌트입니다.",
  );
  result.authorship = {
    author_employee_id: authorSession.user.employee_id,
    author_role: authorSession.user.role,
    assets: [
      { id: flowAsset.id, title: flowAsset.title, type: flowAsset.type },
      { id: componentAsset.id, title: componentAsset.title, type: componentAsset.type },
    ],
  };
  await screenshot(authorSession.page, "00-agent-hub-author-submitted");
  await authorSession.context.close();
  authorSession = null;

  approverSession = await loginAgentHub(browser, "2074795");
  assert(approverSession.user.role === "admin", "reviewer fixture is not Agent Hub admin");
  await approverSession.page.goto(`${config.agentHubUrl}#/admin`, {
    waitUntil: "domcontentloaded",
  });
  for (const title of [flowTitle, componentTitle]) {
    const row = approverSession.page.locator(".sub-row").filter({ hasText: title });
    await row.waitFor();
    await row.locator('input[type="checkbox"]').click();
  }
  const approveResponse = approverSession.page.waitForResponse((response) => (
    response.request().method() === "POST"
    && new URL(response.url()).pathname === "/api/v1/admin/review/bulk"
  ));
  approverSession.page.once("dialog", (dialog) => dialog.accept());
  await approverSession.page.getByRole("button", { name: /일괄 승인 \(2\)/ }).click();
  const approvedResponse = await approveResponse;
  assert(approvedResponse.ok(), "Agent Hub bulk approval failed");
  const approved = await approvedResponse.json();
  assert(approved.count === 2, "Agent Hub did not approve both assets");
  result.approval = {
    reviewer_employee_id: approverSession.user.employee_id,
    reviewer_role: approverSession.user.role,
    approved_ids: approved.reviewed,
  };
  await screenshot(approverSession.page, "00-agent-hub-assets-approved");
  await approverSession.context.close();
  approverSession = null;

  const apiKey = await createLangflowKey(browser);
  boiSession = await loginBoi(browser);
  await ensurePlaygroundEndpoint(boiSession.page, apiKey);
  const adoption = await beginPlaygroundAdoption(boiSession.page);

  adopterHubSession = await loginAgentHub(browser, "100002");
  const deployedFlow = await deployFromAgentHub(
    adopterHubSession.page,
    flowAsset,
    apiKey,
  );
  const deployedComponent = await deployFromAgentHub(
    adopterHubSession.page,
    componentAsset,
    apiKey,
    { targetFlowName: flowTitle },
  );
  assert(
    deployedComponent.flow_id === deployedFlow.flow_id,
    "Component was not added to the deployed Flow",
  );
  result.agent_hub_deploy = {
    adopter_employee_id: adopterHubSession.user.employee_id,
    endpoint_alias: endpointAlias,
    project: "boi-100002",
    flow_id: deployedFlow.flow_id,
    component_flow_id: deployedComponent.flow_id,
    flow_url_origin: new URL(deployedFlow.flow_url).origin,
  };

  const confirmed = await finishPlaygroundAdoption(
    boiSession.page,
    adoption,
    deployedFlow.flow_id,
  );
  result.playground_adoption = {
    adoption_id: adoption.adoption_id,
    validation_profile: adoption.validation_profile,
    source_authors: [
      ...new Set(
        confirmed.deployment.source_assets.map(
          (asset) => asset.author.employee_id,
        ),
      ),
    ],
    adopter_employee_id: "100002",
    endpoint_id: confirmed.deployment.endpoint_id,
    project_id: confirmed.deployment.project_id,
    flow_id: confirmed.deployment.flow_id,
    checksum: confirmed.deployment.artifact_checksum,
    origin: confirmed.deployment.origin,
  };
  const actualTask = await createActualTask(boiSession.page);
  const disconnected = await validateDisconnected(
    boiSession.page,
    confirmed,
    actualTask.taskRef,
  );
  const composed = await composeAdoption(
    boiSession.page,
    adoption,
    deployedFlow.flow_id,
    componentAsset.id,
  );
  result.composition = {
    disconnected: {
      validation_status: disconnected.validation_status,
      failure_reason: disconnected.failure_reason,
    },
    compose: {
      public_patch_status: composed.status,
      previous_checksum: composed.body.previous_checksum,
      live_checksum: composed.body.live_checksum,
      end_to_end_reachable: composed.body.graph_health.end_to_end_reachable,
      connected_component_ids:
        composed.body.graph_health.connected_component_ids,
      rollback_snapshot: composed.body.rollback_snapshot,
    },
    task: actualTask,
  };
  const validation = await validateAndDraft(
    boiSession.page,
    deployedFlow.flow_id,
    actualTask.taskRef,
    confirmed.deployment.endpoint_id,
    confirmed.deployment.project_id,
  );
  result.validation = {
    status: validation.validated.validation_status,
    profile: validation.validated.validation_profile,
    exact_flow_id: validation.validated.flow_id,
    checksum: validation.validated.artifact_checksum,
    action_draft_id: validation.draft.draft.draft_id,
    executed_component_ids:
      validation.validated.registry?.executed_component_ids
      || validation.validated.runtime?.executed_component_ids
      || [],
    draft_flow_id:
      validation.draft.deployment_reference?.flow_id
      || validation.draft.draft?.request?.connector_config?.flow_id
      || "",
  };
  assert(
    result.validation.draft_flow_id === deployedFlow.flow_id,
    "Action draft does not reference the exact deployed Flow",
  );
  assert(
    result.validation.executed_component_ids.includes(componentAsset.id),
    "runtime validation did not prove the adopted component executed",
  );

  result.ok = (
    result.console_errors.length === 0
    && result.page_errors.length === 0
    && result.unexpected_http_errors.length === 0
  );
  assert(result.ok, "browser diagnostics recorded unexpected errors");
} finally {
  await authorSession?.context.close().catch(() => {});
  await approverSession?.context.close().catch(() => {});
  await adopterHubSession?.context.close().catch(() => {});
  await boiSession?.context.close().catch(() => {});
  await browser.close();
  await fs.writeFile(
    path.join(config.evidenceDir, "cross-author-adoption-result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
  );
}
