#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";

const baseUrl = process.env.BOI_BASE_URL || "http://localhost:28005";
const langflowBrowserUrl =
  process.env.LANGFLOW_BROWSER_URL || "http://localhost:17867";
const employeeId = process.env.BOI_EMPLOYEE_ID || "100002";
const identityFile =
  process.env.AGENT_HUB_IDENTITY_FILE
  || "/tmp/boi-ap-agent-hub-sso-users.json";
const evidenceDir =
  process.env.PLAYWRIGHT_EVIDENCE_DIR
  || "artifacts/agent-playground-flow-origin";
const agentHubEvidenceFile =
  process.env.AGENT_HUB_EVIDENCE_FILE
  || "artifacts/agent-playground-agent-hub-sso/playwright-result.json";
const identities = JSON.parse(await fs.readFile(identityFile, "utf8"));
const agentHubEvidence = JSON.parse(await fs.readFile(agentHubEvidenceFile, "utf8"));
const expectedPrdFlowId = String(
  agentHubEvidence.agent_hub?.deployment?.flow_id || "",
);
if (!expectedPrdFlowId) throw new Error("Agent Hub exact Flow evidence is missing");
const password = String(process.env.BOI_SSO_PASSWORD || identities[employeeId] || "");
if (!password) throw new Error(`${employeeId} validation password is unavailable`);
await fs.mkdir(evidenceDir, { recursive: true });

const result = {
  ok: false,
  identity: {},
  desktop: {},
  mobile: {},
  links: [],
  screenshots: [],
  console_errors: [],
  page_errors: [],
  unexpected_http_errors: [],
};

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function monitor(page) {
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("favicon")) {
      result.console_errors.push(message.text().slice(0, 500));
    }
  });
  page.on("pageerror", (error) => {
    result.page_errors.push(String(error).slice(0, 500));
  });
  page.on("response", (response) => {
    if (response.status() < 400 || response.url().includes("/favicon")) return;
    result.unexpected_http_errors.push({
      status: response.status(),
      method: response.request().method(),
      url: response.url().replace(/[?#].*$/, ""),
    });
  });
}

async function login(page) {
  await page.goto(`${baseUrl}/playground`, { waitUntil: "domcontentloaded" });
  if (page.url().includes("/protocol/openid-connect/")) {
    const authorization = new URL(page.url());
    assert(authorization.searchParams.get("code_challenge_method") === "S256", "OIDC PKCE S256 is missing");
    await page.locator("#username").fill(employeeId);
    await page.locator("#password").fill(password);
    await Promise.all([
      page.waitForURL((url) => url.origin === new URL(baseUrl).origin, {
        timeout: 30_000,
      }),
      page.locator("#kc-login").click(),
    ]);
  }
  await page.locator("[data-agent-playground]").waitFor({
    state: "visible",
    timeout: 30_000,
  });
  const firstFlowRow = page.locator(".agent-playground-flow-row").first();
  await firstFlowRow.waitFor({
    state: "attached",
    timeout: 30_000,
  });
  const createStep = page.locator('[data-workbench-step="create"]');
  if (await createStep.isVisible().catch(() => false)) {
    await createStep.click();
  }
  await firstFlowRow.waitFor({
    state: "visible",
    timeout: 30_000,
  });
}

async function capture(page, name) {
  const target = path.resolve(evidenceDir, `${name}.png`);
  await page.screenshot({ path: target, fullPage: true });
  result.screenshots.push(target);
}

async function verifySelectedFlow(page, environment, flowId = "") {
  const rows = page.locator(
    `.agent-playground-flow-row[data-environment="${environment}"]`,
  );
  const row = (
    flowId
      ? rows.filter({
          has: page.locator(
            `.agent-playground-flow-item[data-flow-id="${flowId}"]`,
          ),
        })
      : rows
  ).first();
  assert(await row.isVisible(), `${environment.toUpperCase()} Flow row is missing`);
  const rowLink = row.locator(".agent-playground-flow-original-link");
  const expectedUrl = String(await rowLink.getAttribute("href") || "");
  assert(expectedUrl.includes("/flow/"), `${environment.toUpperCase()} exact Flow URL is missing`);
  assert(expectedUrl.includes("/folder/"), `${environment.toUpperCase()} project folder is missing`);
  assert(!expectedUrl.includes("host.docker.internal"), `${environment.toUpperCase()} URL exposes a container hostname`);
  assert(!/(boi_pat_|boi_run_|api[_-]?key)/i.test(expectedUrl), `${environment.toUpperCase()} URL exposes a secret`);

  await row.locator(".agent-playground-flow-item").click();
  const badge = page.locator("[data-selected-flow-environment]");
  await badge.waitFor({ state: "visible" });
  assert(
    String(await badge.textContent() || "").trim().startsWith(environment.toUpperCase()),
    `Selected Flow badge is not ${environment.toUpperCase()}`,
  );
  const selectedLink = page.locator("[data-open-selected-flow]");
  assert(
    String(await selectedLink.getAttribute("href") || "") === expectedUrl,
    `Selected ${environment.toUpperCase()} Flow link differs from the row link`,
  );
  const sourceLink = page.locator("[data-open-selected-source]");
  if (environment === "dev") {
    assert(await sourceLink.isHidden(), "DEV Flow exposes an Agent Hub source link");
  }
  result.links.push({
    environment,
    canvas_url: expectedUrl,
    source_visible: await sourceLink.isVisible().catch(() => false),
  });
  return selectedLink;
}

const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1050 } });
const page = await context.newPage();

try {
  await login(page);
  monitor(page);
  const identity = await page.evaluate(async () => {
    const response = await fetch("/api/auth/me");
    return response.json();
  });
  assert(identity.employee_id === employeeId, "SSO Principal does not match");
  result.identity = identity;

  assert(
    await page.locator("[data-selected-flow-pipeline]").count() === 0,
    "The misleading linear Flow renderer is still present",
  );
  const devRows = page.locator('.agent-playground-flow-row[data-environment="dev"]');
  const prdRows = page.locator('.agent-playground-flow-row[data-environment="prd"]');
  assert(await devRows.count() > 0, "No DEV Playground Flow is visible");
  assert(await prdRows.count() > 0, "No PRD Agent Hub Flow is visible");

  await verifySelectedFlow(page, "dev");
  const prdSelectedLink = await verifySelectedFlow(page, "prd", expectedPrdFlowId);
  const sourceFlow = await page.evaluate(async (expectedFlowId) => {
    const endpointId = document.querySelector("[data-endpoint-select]")?.value || "";
    const projectId = document.querySelector("[data-project-select]")?.value || "";
    if (!endpointId || !projectId) return null;
    const response = await fetch(
      `/api/agent-playground/endpoints/${encodeURIComponent(endpointId)}`
      + `/projects/${encodeURIComponent(projectId)}/flows`,
    );
    const payload = await response.json();
    return (payload.flows || []).find(
      (flow) => (
        flow.flow_id === expectedFlowId
        && flow.environment === "prd"
        && flow.source?.asset_url
      ),
    ) || null;
  }, expectedPrdFlowId);
  if (sourceFlow) {
    await page.locator(
      `.agent-playground-flow-item[data-flow-id="${sourceFlow.flow_id}"]`,
    ).click();
    const sourceLink = page.locator("[data-open-selected-source]");
    assert(await sourceLink.isVisible(), "Agent Hub asset source link is hidden");
    assert(
      String(await sourceLink.getAttribute("href") || "") === sourceFlow.source.asset_url,
      "Agent Hub asset source link differs from the approved catalog URL",
    );
    result.links.push({
      environment: "prd",
      asset_url: sourceFlow.source.asset_url,
      source_visible: true,
    });
  }
  await prdSelectedLink.scrollIntoViewIfNeeded();
  const popupPromise = context.waitForEvent("page");
  await prdSelectedLink.click();
  const popup = await popupPromise;
  await popup.waitForURL(
    (url) =>
      url.origin === new URL(langflowBrowserUrl).origin
      && url.pathname.includes("/flow/"),
    { timeout: 30_000 },
  );
  await popup.waitForLoadState("domcontentloaded", { timeout: 30_000 }).catch(() => null);
  const popupUrl = popup.url();
  assert(
    new URL(popupUrl).origin === new URL(langflowBrowserUrl).origin,
    "Original Flow did not open the SSO-protected Langflow browser URL",
  );
  assert(popupUrl.includes("/flow/"), "Original Flow popup lost the exact Flow path");
  assert(!popupUrl.includes("/login"), "Original Flow required a second Langflow login");
  assert(
    await popup.locator('input[type="password"]').count() === 0,
    "Original Flow displayed another credential form",
  );
  await popup.waitForFunction(
    () => {
      const text = document.body?.innerText || "";
      return !text.includes("Loading...") && text.trim().length > 50;
    },
    undefined,
    { timeout: 60_000 },
  );
  const langflowCookies = await popup.context().cookies(langflowBrowserUrl);
  const langflowWhoamiResponse = await popup.context().request.get(
    `${new URL(langflowBrowserUrl).origin}/api/v1/users/whoami`,
    {
      headers: {
        Cookie: langflowCookies
          .map((cookie) => `${cookie.name}=${cookie.value}`)
          .join("; "),
      },
    },
  );
  const langflowIdentity = {
    status: langflowWhoamiResponse.status(),
    body: await langflowWhoamiResponse.json().catch(() => ({})),
  };
  assert(
    langflowIdentity.status === 200,
    `Langflow SSO whoami failed: ${langflowIdentity.status} ${JSON.stringify(langflowIdentity.body)}`,
  );
  assert(
    String(langflowIdentity.body?.username || "") === employeeId,
    "Langflow SSO user does not match the BoI employee",
  );
  result.desktop = {
    dev_rows: await devRows.count(),
    prd_rows: await prdRows.count(),
    agent_hub_source_candidate: Boolean(sourceFlow),
    expected_prd_flow_id: expectedPrdFlowId,
    original_popup_url: popupUrl.replace(/[?#].*$/, ""),
    langflow_user: langflowIdentity.body.username,
  };
  await popup.close();
  await capture(page, "desktop-flow-origin");

  await page.setViewportSize({ width: 390, height: 844 });
  const mobile = await page.evaluate(() => ({
    viewport_width: document.documentElement.clientWidth,
    scroll_width: document.documentElement.scrollWidth,
    visible_origin_links: [...document.querySelectorAll(".agent-playground-flow-original-link")]
      .filter((element) => {
        const style = window.getComputedStyle(element);
        return style.display !== "none" && style.visibility !== "hidden";
      }).length,
  }));
  assert(mobile.scroll_width <= mobile.viewport_width + 2, "Mobile page has horizontal overflow");
  assert(mobile.visible_origin_links > 0, "Mobile original Flow links are not visible");
  result.mobile = mobile;
  await capture(page, "mobile-flow-origin");

  assert(result.console_errors.length === 0, "Unexpected console errors were detected");
  assert(result.page_errors.length === 0, "Unexpected page errors were detected");
  assert(result.unexpected_http_errors.length === 0, "Unexpected HTTP errors were detected");
  result.ok = true;
} catch (error) {
  result.error = String(error && error.stack ? error.stack : error);
  await capture(page, "failure").catch(() => null);
  throw error;
} finally {
  await fs.writeFile(
    path.resolve(evidenceDir, "playwright-result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
  );
  await context.close();
  await browser.close();
}

console.log(JSON.stringify(result, null, 2));
