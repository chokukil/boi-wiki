import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const baseUrl = process.env.BOI_BASE_URL || "http://localhost:28005";
const identityFile =
  process.env.AGENT_HUB_IDENTITY_FILE
  || "/tmp/boi-ap-agent-hub-sso-users.json";
const outputDir =
  process.env.ACTION_FLOW_EVIDENCE_DIR
  || path.resolve("artifacts/agent-playground-handoff/action-flow-visibility");
const employeeId = process.env.BOI_EMPLOYEE_ID || "100002";
const identities = JSON.parse(fs.readFileSync(identityFile, "utf8"));
const password = String(identities[employeeId] || "");
if (!password) throw new Error(`${employeeId} validation password is unavailable`);
fs.mkdirSync(outputDir, { recursive: true });

const unexpected = [];
const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};

function monitor(page, label) {
  page.on("pageerror", (error) => {
    unexpected.push({ label, kind: "pageerror", message: error.message });
  });
  page.on("console", (message) => {
    if (message.type() === "error") {
      unexpected.push({ label, kind: "console", message: message.text() });
    }
  });
  page.on("response", (response) => {
    if (response.status() >= 400 && !response.url().includes("/favicon")) {
      unexpected.push({
        label,
        kind: "http",
        status: response.status(),
        url: response.url(),
      });
    }
  });
}

async function login(page, loginEmployeeId = employeeId) {
  const loginPassword = String(identities[loginEmployeeId] || "");
  if (!loginPassword) {
    throw new Error(`${loginEmployeeId} validation password is unavailable`);
  }
  await page.goto(`${baseUrl}/actions?connector_kind=langflow`, {
    waitUntil: "domcontentloaded",
  });
  const username = page.locator("#username");
  await Promise.race([
    username.waitFor({ state: "visible", timeout: 20_000 }).catch(() => null),
    page.locator("[data-action-catalog]").waitFor({
      state: "visible",
      timeout: 20_000,
    }).catch(() => null),
  ]);
  if (await username.isVisible().catch(() => false)) {
    await username.fill(loginEmployeeId);
    await page.locator("#password").fill(loginPassword);
    await page.locator("#kc-login").click();
  }
  await page.waitForURL((url) => url.origin === baseUrl, { timeout: 30_000 });
  await page.locator("[data-action-catalog]").waitFor({
    state: "visible",
    timeout: 30_000,
  });
}

async function openWorkingAction(page) {
  const identity = await page.evaluate(async () => {
    const response = await fetch("/api/auth/me");
    return response.json();
  });
  const attempts = [];
  const rows = page.locator(
    '[data-action-open^="agent-playground."][data-action-open*="."]',
  );
  const count = await rows.count();
  assert(count > 0, "No Agent Playground Action is visible to the user");
  for (let index = 0; index < count; index += 1) {
    const row = rows.nth(index);
    const actionKey = String(await row.getAttribute("data-action-open") || "");
    await row.click();
    const flowButton = page.locator("[data-action-flow-load]");
    await flowButton.waitFor({ state: "visible", timeout: 8_000 }).catch(() => null);
    if (!await flowButton.isVisible().catch(() => false)) continue;
    await flowButton.click();
    const flowView = page.locator("[data-action-flow-view]");
    await flowView.waitFor({ state: "visible", timeout: 20_000 }).catch(() => null);
    await page.waitForFunction(
      () => {
        const view = document.querySelector("[data-action-flow-view]");
        return Boolean(
          view
          && !String(view.textContent || "").includes(
            "현재 Flow 구조와 검증 상태를 확인하고 있습니다.",
          )
        );
      },
      { timeout: 25_000 },
    ).catch(() => null);
    const playgroundLink = flowView.getByRole("link", {
      name: "Playground에서 열기",
    });
    const componentCount = await flowView.locator(".action-flow-pipeline li").count();
    if (
      await playgroundLink.isVisible().catch(() => false)
      && componentCount > 0
    ) {
      return {
        actionKey,
        actionTitle: String(await row.locator("strong").first().textContent() || "").trim(),
        flowName: String(
          await flowView.locator(".action-flow-live-heading strong").textContent()
          || "",
        ).trim(),
        componentCount,
      };
    }
    attempts.push({
      actionKey,
      text: String(await flowView.textContent().catch(() => "") || "").trim().slice(0, 400),
    });
  }
  throw new Error(
    `No owner Action exposed a valid Playground Flow link: ${JSON.stringify({
      identity,
      attempts,
    })}`,
  );
}

async function verifyDesktop(browser) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });
  const page = await context.newPage();
  await login(page);
  monitor(page, "desktop");
  const selected = await openWorkingAction(page);
  assert(selected.componentCount > 0, "Action Flow execution path is empty");
  await page.screenshot({
    path: path.join(outputDir, "01-action-linked-flow-desktop.png"),
    fullPage: true,
  });
  const playgroundLink = page.getByRole("link", {
    name: "Playground에서 열기",
  });
  await playgroundLink.click();
  await page.waitForURL((url) => url.pathname === "/playground", {
    timeout: 30_000,
  });
  await page.locator("[data-agent-playground]").waitFor({
    state: "visible",
    timeout: 30_000,
  });
  await page.locator("[data-selected-flow-pipeline] li").first().waitFor({
    state: "visible",
    timeout: 30_000,
  });
  const selectedFlowName = String(
    await page.locator("[data-selected-flow-name]").textContent() || "",
  ).trim();
  const selectedFlowId = String(
    await page.locator("[data-selected-flow-id]").textContent() || "",
  ).trim();
  const linkedActionCount = await page.locator(
    "[data-selected-flow-action-list] a",
  ).count();
  assert(selectedFlowName === selected.flowName, "Action and Playground Flow names differ");
  assert(selectedFlowId && selectedFlowId !== "—", "Exact Flow ID was not selected");
  assert(linkedActionCount > 0, "Playground does not link back to its Action");
  await page.screenshot({
    path: path.join(outputDir, "02-playground-exact-flow-desktop.png"),
    fullPage: true,
  });
  const playgroundUrl = page.url();
  await page.goto(
    `${baseUrl}/docs/boi:public:boi-wiki-manual:langflow:agent-playground-action-wiki`,
    { waitUntil: "domcontentloaded" },
  );
  await page.getByText("Action에 연결된 Flow를 확인한다", {
    exact: true,
  }).waitFor({ state: "visible", timeout: 20_000 });
  const petDomCount = await page.locator(
    "[data-pet-agent], .boi-agent-panel, [data-boi-agent-panel]",
  ).count();
  assert(petDomCount === 0, "Pet agent DOM is visible in the Wiki guide");
  await page.screenshot({
    path: path.join(outputDir, "04-action-flow-wiki-guide.png"),
    fullPage: true,
  });
  const result = {
    ...selected,
    selectedFlowName,
    selectedFlowId,
    linkedActionCount,
    playgroundUrl,
    wikiGuide: {
      url: `${baseUrl}/docs/boi:public:boi-wiki-manual:langflow:agent-playground-action-wiki`,
      petDomCount,
    },
  };
  await context.close();
  return result;
}

async function verifyMobile(browser, actionKey) {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
  });
  const page = await context.newPage();
  await login(page);
  monitor(page, "mobile");
  await page.goto(
    `${baseUrl}/actions?connector_kind=langflow&action_key=${encodeURIComponent(actionKey)}`,
    { waitUntil: "domcontentloaded" },
  );
  const row = page.locator(`[data-action-open="${actionKey}"]`);
  await row.waitFor({ state: "visible", timeout: 20_000 });
  await row.click();
  await page.locator("[data-action-flow-load]").click();
  await page.locator(".action-flow-pipeline li").first().waitFor({
    state: "visible",
    timeout: 20_000,
  });
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  assert(overflow <= 1, `Mobile page has ${overflow}px horizontal overflow`);
  await page.screenshot({
    path: path.join(outputDir, "03-action-linked-flow-mobile.png"),
    fullPage: true,
  });
  const result = {
    viewport: { width: 390, height: 844 },
    horizontalOverflow: overflow,
    componentCount: await page.locator(".action-flow-pipeline li").count(),
  };
  await context.close();
  return result;
}

async function verifySharedViewer(browser, actionKey) {
  const context = await browser.newContext({
    viewport: { width: 1180, height: 860 },
  });
  const page = await context.newPage();
  await login(page, "100001");
  monitor(page, "shared-viewer");
  await page.goto(
    `${baseUrl}/actions?connector_kind=langflow&action_key=${encodeURIComponent(actionKey)}`,
    { waitUntil: "domcontentloaded" },
  );
  const row = page.locator(`[data-action-open="${actionKey}"]`);
  await row.waitFor({ state: "visible", timeout: 20_000 });
  await row.click();
  await page.locator("[data-action-flow-load]").waitFor({
    state: "visible",
    timeout: 20_000,
  });
  await page.locator("[data-action-flow-load]").click();
  const flowView = page.locator("[data-action-flow-view]");
  await page.waitForFunction(
    () => {
      const view = document.querySelector("[data-action-flow-view]");
      return Boolean(
        view
        && !String(view.textContent || "").includes(
          "현재 Flow 구조와 검증 상태를 확인하고 있습니다.",
        )
      );
    },
    { timeout: 25_000 },
  );
  const componentCount = await flowView.locator(".action-flow-pipeline li").count();
  const privateLinkCount = await flowView.getByRole("link", {
    name: /Playground에서 열기|Langflow Canvas 열기/,
  }).count();
  assert(componentCount > 0, "Shared viewer cannot inspect the Flow structure");
  assert(privateLinkCount === 0, "Shared viewer received an owner-only Flow link");
  const result = { employeeId: "100001", componentCount, privateLinkCount };
  await context.close();
  return result;
}

const browser = await chromium.launch({
  headless: true,
  executablePath:
    process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    || "/home/chokukil/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome",
});
try {
  const desktop = await verifyDesktop(browser);
  const mobile = await verifyMobile(browser, desktop.actionKey);
  const sharedViewer = await verifySharedViewer(browser, desktop.actionKey);
  assert(unexpected.length === 0, `Unexpected browser errors: ${JSON.stringify(unexpected)}`);
  const result = {
    passed: true,
    generatedAt: new Date().toISOString(),
    baseUrl,
    employeeId,
    desktop,
    mobile,
    sharedViewer,
    unexpected,
  };
  fs.writeFileSync(
    path.join(outputDir, "result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
  );
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
} finally {
  await browser.close();
}
