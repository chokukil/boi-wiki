#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";

const boiUrl = process.env.BOI_BASE_URL || "http://localhost:28005";
const langflowUrl = process.env.LANGFLOW_BROWSER_URL || "http://localhost:17867";
const employeeId = process.env.BOI_EMPLOYEE_ID || "100002";
const identityFile =
  process.env.AGENT_HUB_IDENTITY_FILE
  || "/tmp/boi-ap-agent-hub-sso-users.json";
const evidenceDir =
  process.env.PLAYWRIGHT_EVIDENCE_DIR
  || "artifacts/agent-playground-browser-sso";
const identities = JSON.parse(await fs.readFile(identityFile, "utf8"));
const password = String(process.env.BOI_SSO_PASSWORD || identities[employeeId] || "");
if (!password) throw new Error(`${employeeId} validation password is unavailable`);
await fs.mkdir(evidenceDir, { recursive: true });

const result = {
  ok: false,
  employee_id: employeeId,
  boi_auth_source: "",
  langflow_user: "",
  second_password_form: false,
  browser_sso_status: "",
  screenshots: [],
  unexpected_http_errors: [],
  console_errors: [],
  page_errors: [],
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
  page.on("pageerror", (error) => result.page_errors.push(String(error).slice(0, 500)));
  page.on("response", (response) => {
    if (response.status() < 400 || response.url().includes("/favicon")) return;
    result.unexpected_http_errors.push({
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

const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const boiPage = await context.newPage();

try {
  await boiPage.goto(`${boiUrl}/playground`, { waitUntil: "domcontentloaded" });
  if (boiPage.url().includes("/protocol/openid-connect/")) {
    const authorization = new URL(boiPage.url());
    assert(
      authorization.searchParams.get("code_challenge_method") === "S256",
      "BoI OIDC PKCE S256 is missing",
    );
    await boiPage.locator("#username").fill(employeeId);
    await boiPage.locator("#password").fill(password);
    await Promise.all([
      boiPage.waitForURL((url) => url.origin === new URL(boiUrl).origin, {
        timeout: 30_000,
      }),
      boiPage.locator("#kc-login").click(),
    ]);
  }
  await boiPage.locator("[data-agent-playground]").waitFor({
    state: "visible",
    timeout: 30_000,
  });
  const boiIdentity = await boiPage.evaluate(async () => {
    const response = await fetch("/api/auth/me");
    return response.json();
  });
  assert(boiIdentity.employee_id === employeeId, "BoI SSO employee mismatch");
  result.boi_auth_source = String(boiIdentity.auth_source || "");

  const langflowPage = await context.newPage();
  monitor(langflowPage);
  await langflowPage.goto(langflowUrl, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await langflowPage.waitForURL(
    (url) => url.origin === new URL(langflowUrl).origin,
    { timeout: 30_000 },
  );
  result.second_password_form = await langflowPage.locator('input[type="password"]').count() > 0;
  assert(!result.second_password_form, "Langflow displayed a second password form");

  let whoami = null;
  let whoamiBody = {};
  const whoamiDeadline = Date.now() + 60_000;
  while (Date.now() < whoamiDeadline) {
    whoami = await context.request.get(`${langflowUrl}/api/v1/users/whoami`);
    whoamiBody = await whoami.json().catch(() => ({}));
    if (whoami.status() === 200) break;
    await langflowPage.waitForTimeout(250);
  }
  assert(
    whoami?.status() === 200,
    `Langflow whoami failed: ${whoami?.status()} ${JSON.stringify(whoamiBody)}`,
  );
  assert(
    String(whoamiBody.username || "") === employeeId,
    "Langflow browser user does not match BoI employee",
  );
  result.langflow_user = String(whoamiBody.username || "");
  await langflowPage.waitForFunction(
    () => {
      const text = document.body?.innerText || "";
      return !text.includes("Loading...") && text.trim().length > 50;
    },
    undefined,
    { timeout: 60_000 },
  );
  assert(
    !(await langflowPage.locator("body").innerText()).includes("Loading..."),
    "Langflow browser remained on the loading screen",
  );
  await capture(langflowPage, "langflow-sso-no-second-login");

  const verify = await boiPage.evaluate(
    async ({ employee, userId }) => {
      const state = await (await fetch("/api/agent-playground")).json();
      const response = await fetch("/api/agent-playground/browser-sso/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          endpoint_id: state.default_endpoint_id || "",
          langflow_username: employee,
          langflow_user_id: userId,
        }),
      });
      return { status: response.status, body: await response.json() };
    },
    { employee: employeeId, userId: String(whoamiBody.id || "") },
  );
  assert(verify.status === 200, `Browser SSO verification failed: ${JSON.stringify(verify)}`);
  assert(verify.body.browser_sso?.status === "ready", "Browser SSO did not become ready");
  result.browser_sso_status = verify.body.browser_sso.status;

  await boiPage.reload({ waitUntil: "domcontentloaded" });
  await boiPage.locator("[data-agent-playground]").waitFor({ state: "visible" });
  await capture(boiPage, "playground-browser-sso-ready");

  assert(result.console_errors.length === 0, "Unexpected Langflow console errors were detected");
  assert(result.page_errors.length === 0, "Unexpected Langflow page errors were detected");
  assert(
    result.unexpected_http_errors.length === 0,
    `Unexpected Langflow HTTP errors: ${JSON.stringify(result.unexpected_http_errors)}`,
  );
  result.ok = true;
} catch (error) {
  result.error = String(error && error.stack ? error.stack : error);
  await capture(boiPage, "failure").catch(() => null);
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
