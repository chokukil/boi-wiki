#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const gatewayUrl = process.env.BOI_TRUSTED_GATEWAY_URL || "http://localhost:28006";
const langflowGatewayUrl =
  process.env.LANGFLOW_TRUSTED_GATEWAY_URL || "http://localhost:17870";
const evidenceDir =
  process.env.PLAYWRIGHT_EVIDENCE_DIR
  || "artifacts/agent-playground-trusted-header";
await fs.mkdir(evidenceDir, { recursive: true });

async function waitForHealth(url) {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${url}/health`);
      if (response.ok) return;
    } catch {
      // Compose may have published the port before uvicorn accepts traffic.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`gateway did not become healthy: ${url}`);
}

await waitForHealth(gatewayUrl);
await waitForHealth(langflowGatewayUrl);

const result = {
  ok: false,
  identity: {},
  bridge: {},
  langflow: {},
  spoof: {},
  keycloak_callback_used: false,
  screenshots: [],
  console_errors: [],
  page_errors: [],
  unexpected_http_errors: [],
};

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
page.on("console", (message) => {
  if (message.type() === "error" && !message.text().includes("favicon")) {
    result.console_errors.push(message.text().slice(0, 500));
  }
});
page.on("pageerror", (error) => result.page_errors.push(String(error).slice(0, 500)));
page.on("request", (request) => {
  if (request.url().includes("/protocol/openid-connect/")) {
    result.keycloak_callback_used = true;
  }
});
page.on("response", (response) => {
  if (response.status() < 400 || response.url().includes("favicon")) return;
  result.unexpected_http_errors.push({
    status: response.status(),
    method: response.request().method(),
    url: response.url().replace(/[?#].*$/, ""),
  });
});

async function capture(name, targetPage = page) {
  const target = path.resolve(evidenceDir, `${name}.png`);
  await targetPage.screenshot({ path: target, fullPage: true });
  result.screenshots.push(target);
}

try {
  await page.goto(
    `${gatewayUrl}/mock-login/100002?next_path=/playground`,
    { waitUntil: "domcontentloaded" },
  );
  await page.locator("[data-agent-playground]").waitFor({
    state: "visible",
    timeout: 30_000,
  });
  const identity = await page.evaluate(async () => {
    const response = await fetch("/api/auth/me");
    return response.json();
  });
  assert(identity.employee_id === "100002", "trusted header employee mismatch");
  assert(identity.auth_source === "trusted_header", "trusted header auth source missing");
  result.identity = identity;

  const spoofed = await page.evaluate(async () => {
    const response = await fetch("/api/auth/me", {
      headers: {
        "X-BoI-Employee-ID": "100001",
        "X-Hynix-Employee-ID": "100001",
      },
    });
    return { status: response.status, body: await response.json() };
  });
  assert(spoofed.status === 200, "gateway rejected the authenticated session");
  assert(spoofed.body.employee_id === "100002", "gateway accepted a spoofed identity header");
  result.spoof = {
    submitted_employee_id: "100001",
    resolved_employee_id: spoofed.body.employee_id,
    stripped_by_gateway: true,
  };

  const querySpoof = await context.request.get(
    `${gatewayUrl}/api/agent-playground?employee_id=100001`,
  );
  assert(querySpoof.status() === 403, "query employee spoof was not rejected");
  result.unexpected_http_errors = result.unexpected_http_errors.filter(
    (item) => !(
      item.status === 403
      && item.url.endsWith("/api/agent-playground")
    ),
  );

  const bridgeResponse = await page.evaluate(async () => {
    const response = await fetch("/mock-bridge-proof");
    return { status: response.status, body: await response.json() };
  });
  assert(bridgeResponse.status === 200, "SSO Token Bridge proof failed");
  assert(bridgeResponse.body.employee_id === "100002", "bridge employee mismatch");
  assert(bridgeResponse.body.algorithm === "RS256", "bridge algorithm mismatch");
  assert(bridgeResponse.body.ttl_seconds === 60, "bridge TTL mismatch");
  assert(bridgeResponse.body.token_exposed === false, "bridge exposed its JWT");
  result.bridge = bridgeResponse.body;
  assert(result.keycloak_callback_used === false, "trusted header path used Keycloak callback");

  await capture("trusted-header-playground");

  const state = await page.evaluate(async () => {
    const response = await fetch("/api/agent-playground");
    return response.json();
  });
  const setup = state.endpoint_setups?.[state.default_endpoint_id] || {};
  const flowId = String(setup.recommended_flow?.id || setup.canonical_flow?.id || "");
  const projectId = String(setup.project?.id || "");
  assert(flowId && projectId, "trusted-header user has no ready Langflow Flow");

  const langflowPage = await context.newPage();
  langflowPage.on("console", (message) => {
    if (
      message.type() === "error"
      && !message.text().includes("favicon")
      && !message.text().startsWith("Duplicate request:")
    ) {
      result.console_errors.push(message.text().slice(0, 500));
    }
  });
  langflowPage.on(
    "pageerror",
    (error) => result.page_errors.push(String(error).slice(0, 500)),
  );
  langflowPage.on("request", (request) => {
    if (request.url().includes("/protocol/openid-connect/")) {
      result.keycloak_callback_used = true;
    }
  });
  await langflowPage.goto(
    `${langflowGatewayUrl}/flow/${flowId}/folder/${projectId}`,
    { waitUntil: "domcontentloaded", timeout: 60_000 },
  );
  const secondPasswordForm =
    await langflowPage.locator('input[type="password"]').count() > 0;
  assert(!secondPasswordForm, "embedded Langflow displayed a second password form");
  let whoami = {};
  const whoamiDeadline = Date.now() + 60_000;
  while (Date.now() < whoamiDeadline) {
    const response = await context.request.get(
      `${langflowGatewayUrl}/api/v1/users/whoami`,
    );
    whoami = {
      status: response.status(),
      body: await response.json().catch(() => ({})),
    };
    if (whoami.status === 200) break;
    await langflowPage.waitForTimeout(250);
  }
  assert(whoami.status === 200, "trusted corporate Langflow whoami failed");
  assert(
    String(whoami.body?.username || "") === "100002",
    "trusted corporate Langflow principal mismatch",
  );
  result.langflow = {
    mode: "embedded_sso",
    flow_id: flowId,
    project_id: projectId,
    employee_id: String(whoami.body.username || ""),
    second_password_form: secondPasswordForm,
    bridge_jwt_injected_server_side: true,
  };
  const browserSso = await page.evaluate(
    async ({ endpointId, employee, userId }) => {
      const response = await fetch("/api/agent-playground/browser-sso/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          endpoint_id: endpointId,
          langflow_username: employee,
          langflow_user_id: userId,
        }),
      });
      return { status: response.status, body: await response.json() };
    },
    {
      endpointId: state.default_endpoint_id,
      employee: "100002",
      userId: String(whoami.body.id || ""),
    },
  );
  assert(browserSso.status === 200, "trusted browser SSO verification failed");
  assert(
    browserSso.body?.browser_sso?.status === "ready",
    "trusted browser SSO did not become ready",
  );
  result.langflow.browser_sso_status =
    browserSso.body.browser_sso.status;
  await capture("trusted-header-langflow", langflowPage);

  const viewerContext = await browser.newContext();
  const viewerPage = await viewerContext.newPage();
  await viewerPage.goto(
    `${gatewayUrl}/mock-login/100003?next_path=/playground`,
    { waitUntil: "domcontentloaded" },
  );
  const viewerLangflow = await viewerContext.request.get(langflowGatewayUrl);
  assert(
    viewerLangflow.status() === 403,
    "employee-isolated Langflow gateway allowed a different employee",
  );
  await viewerContext.close();
  assert(result.console_errors.length === 0, "unexpected console errors");
  assert(result.page_errors.length === 0, "unexpected page errors");
  assert(result.unexpected_http_errors.length === 0, "unexpected HTTP errors");
  result.ok = true;
} catch (error) {
  result.error = String(error?.stack || error);
  await capture("failure").catch(() => null);
  throw error;
} finally {
  await fs.writeFile(
    path.resolve(evidenceDir, "result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
  );
  await context.close();
  await browser.close();
}

console.log(JSON.stringify(result, null, 2));
