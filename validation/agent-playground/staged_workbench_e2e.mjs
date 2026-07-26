#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || "playwright");

const config = {
  boiUrl: process.env.BOI_URL || "http://localhost:28005",
  employeeId: process.env.BOI_EMPLOYEE_ID || "100002",
  identityFile:
    process.env.AGENT_HUB_IDENTITY_FILE
    || "/tmp/boi-ap-agent-hub-sso-users.json",
  evidenceDir:
    process.env.PLAYWRIGHT_EVIDENCE_DIR
    || "artifacts/agent-playground-staged-workbench",
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || "",
};

const identities = JSON.parse(await fs.readFile(config.identityFile, "utf8"));
const password = String(
  process.env.BOI_SSO_PASSWORD || identities[config.employeeId] || "",
);
if (!password) throw new Error(`${config.employeeId} validation password is unavailable`);
await fs.mkdir(config.evidenceDir, { recursive: true });

const result = {
  ok: false,
  identity: {},
  retrieval_default: {},
  desktop: {},
  mobile: {},
  task_selector: {},
  component_statuses: [],
  screenshots: [],
  console_errors: [],
  page_errors: [],
  unexpected_http_errors: [],
};

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const browser = await chromium.launch({
  headless: true,
  ...(config.executablePath ? { executablePath: config.executablePath } : {}),
  args: ["--no-sandbox"],
});
const context = await browser.newContext({ viewport: { width: 1440, height: 1050 } });
const page = await context.newPage();

page.on("console", (message) => {
  const text = message.text();
  if (
    message.type() === "error"
    && !text.includes("favicon")
    && !text.startsWith("Failed to load resource:")
  ) {
    result.console_errors.push(text.slice(0, 500));
  }
});
page.on("pageerror", (error) => {
  result.page_errors.push(String(error).slice(0, 500));
});
page.on("response", (response) => {
  const url = new URL(response.url());
  if (url.pathname === "/api/agents/boi-wiki/inbox") {
    result.task_selector.inbox_status = response.status();
  }
  if (response.status() < 400) return;
  result.unexpected_http_errors.push({
    status: response.status(),
    method: response.request().method(),
    url: `${url.origin}${url.pathname}`,
  });
});

async function capture(name) {
  const target = path.join(config.evidenceDir, `${name}.png`);
  await page.screenshot({ path: target, fullPage: true });
  result.screenshots.push(target);
}

async function visibleStepState() {
  return page.evaluate(() => {
    const visible = (element) => {
      const style = window.getComputedStyle(element);
      return !element.hidden && style.display !== "none" && style.visibility !== "hidden";
    };
    const steps = [...document.querySelectorAll("[data-workbench-step]")];
    return {
      steps: steps.length,
      active_actions: steps.filter(
        (element) => visible(element) && element.classList.contains("active"),
      ).length,
      next_action_count: [...document.querySelectorAll("[data-next-action] button.primary")]
        .filter(visible).length,
      active_step:
        steps.find((element) => element.getAttribute("aria-current") === "step")
          ?.dataset.workbenchStep || "",
      visible_panels: [
        ...document.querySelectorAll("[data-workbench-panel]"),
      ].filter(visible).map((element) => element.dataset.workbenchPanel),
    };
  });
}

try {
  await page.goto(`${config.boiUrl}/playground`, { waitUntil: "domcontentloaded" });
  if (page.url().includes("/protocol/openid-connect/")) {
    const authorization = new URL(page.url());
    assert(Boolean(authorization.searchParams.get("state")), "OIDC state is missing");
    assert(Boolean(authorization.searchParams.get("nonce")), "OIDC nonce is missing");
    assert(
      authorization.searchParams.get("code_challenge_method") === "S256",
      "OIDC PKCE S256 is missing",
    );
    await page.locator("#username").fill(config.employeeId);
    await page.locator("#password").fill(password);
    await Promise.all([
      page.waitForURL((url) => url.origin === new URL(config.boiUrl).origin),
      page.locator("#kc-login").click(),
    ]);
  }

  const root = page.locator("[data-agent-playground]");
  await root.waitFor();
  let state = await page.evaluate(async () => {
    const response = await fetch("/api/agent-playground");
    return { status: response.status, body: await response.json() };
  });
  assert(state.status === 200, `Playground state returned HTTP ${state.status}`);
  assert(
    state.body.identity?.employee_id === config.employeeId,
    "SSO Principal does not match the requested validation employee",
  );
  result.identity = {
    employee_id: state.body.identity.employee_id,
    auth_source: state.body.identity.auth_source,
  };
  if (
    state.body.onboarding?.required
    && state.body.onboarding?.next_action === "bootstrap"
  ) {
    await root.locator("[data-onboarding-bootstrap]").click();
    await root
      .locator('[data-onboarding-stage="flow"]')
      .waitFor({ state: "visible", timeout: 120_000 });
    await root.locator("[data-onboarding-finish]").click();
    state = await page.evaluate(async () => {
      const response = await fetch("/api/agent-playground");
      return { status: response.status, body: await response.json() };
    });
    assert(
      state.body.onboarding?.status === "ready",
      "resume bootstrap did not restore endpoint readiness",
    );
  }
  await root.locator("[data-workbench-step]").first().waitFor({ state: "visible" });
  await root.locator('[data-workbench-step="create"]').click();

  result.desktop = await visibleStepState();
  assert(result.desktop.steps === 4, "desktop workbench must expose four stages");
  assert(
    result.desktop.active_step === "create",
    "desktop create-stage evidence must capture the create stage",
  );
  assert(
    result.desktop.active_actions === 1,
    "desktop workbench must emphasize exactly one stage",
  );
  assert(
    result.desktop.next_action_count === 1,
    "desktop workbench must expose exactly one primary next action",
  );
  await capture("01-desktop-create-stage");

  const inboxResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET"
      && url.pathname === "/api/agents/boi-wiki/inbox"
    );
  }, { timeout: 30_000 }).catch(() => null);
  await root.locator('[data-workbench-step="test"]').click();
  await root.locator("[data-retrieval-default]").waitFor({ state: "visible" });
  const retrievalText = (
    await root.locator("[data-retrieval-default]").innerText()
  ).trim();
  const bodyText = await root.innerText();
  assert(
    retrievalText.includes("Task Context + Ontology"),
    "Ontology-first retrieval label is missing",
  );
  assert(
    retrievalText.includes("Wiki 문서로 보완"),
    "document fallback label is missing",
  );
  assert(
    !bodyText.toLowerCase().includes("boi_search"),
    "internal boi_search facade leaked into the Playground UI",
  );
  result.retrieval_default = {
    strategy: "task_context_ontology_hybrid",
    label: retrievalText,
    internal_facade_hidden: true,
  };
  await root.locator("[data-task-select]").waitFor();
  const inbox = await inboxResponse;
  if (inbox) result.task_selector.inbox_status = inbox.status();
  await page.waitForFunction(() => {
    const option = document.querySelector("[data-task-select] option");
    return option && !String(option.textContent || "").includes("불러오는 중");
  });
  result.task_selector = {
    ...result.task_selector,
    uses_acl_inbox: result.task_selector.inbox_status === 200,
    option_count: await root.locator("[data-task-select] option").count(),
  };
  assert(result.task_selector.uses_acl_inbox, "Task selector did not use the ACL inbox API");
  await capture("02-desktop-test-ontology-default");

  await root.locator('[data-workbench-step="hub"]').click();
  const hubModes = await root.locator("[data-hub-mode]").allTextContents();
  assert(
    hubModes.some((value) => value.includes("내 Flow 배포하기"))
      && hubModes.some((value) => value.includes("공유 자산 가져오기")),
    "Agent Hub own/shared journeys are not separated",
  );
  assert(
    await root.locator("[data-hub-onboarding]").isVisible(),
    "Agent Hub first-deployment guide is missing",
  );
  const componentStatuses = await root
    .locator("[data-component-status-legend] span")
    .allTextContents();
  result.component_statuses = componentStatuses.map((value) => value.trim());
  assert(
    JSON.stringify(result.component_statuses)
      === JSON.stringify(["배포됨", "연결 필요", "연결됨", "실행 검증됨"]),
    "Component lifecycle statuses are incomplete",
  );
  await capture("03-desktop-hub-component-lifecycle");

  await page.setViewportSize({ width: 390, height: 844 });
  await root.locator('[data-workbench-step="create"]').click();
  result.mobile = {
    ...(await visibleStepState()),
    viewport_width: await page.evaluate(() => window.innerWidth),
    body_width: await page.evaluate(() => document.body.scrollWidth),
  };
  assert(result.mobile.steps === 4, "mobile workbench must expose four stages");
  assert(
    result.mobile.active_actions === 1,
    "mobile workbench must emphasize exactly one stage",
  );
  assert(
    result.mobile.next_action_count === 1,
    "mobile workbench must expose exactly one primary next action",
  );
  assert(
    result.mobile.body_width <= result.mobile.viewport_width,
    "mobile workbench has horizontal overflow",
  );
  await capture("04-mobile-create-stage");

  result.ok = (
    result.console_errors.length === 0
    && result.page_errors.length === 0
    && result.unexpected_http_errors.length === 0
  );
  assert(result.ok, "browser diagnostics recorded unexpected errors");
} finally {
  await context.close();
  await browser.close();
  await fs.writeFile(
    path.join(config.evidenceDir, "result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
  );
}

console.log(JSON.stringify({ ok: result.ok, evidence_dir: config.evidenceDir }));
