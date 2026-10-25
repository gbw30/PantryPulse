import { expect, test } from "@playwright/test";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import path from "node:path";
import { expectNoSeriousA11yViolations } from "./a11y";

test("connected presenter forecast scenario comparison and revision", async ({ page }, testInfo) => {
  test.skip(process.env.PP_RUN_CONNECTED !== "1", "Requires isolated seeded PostgreSQL, API and Linux worker");
  test.setTimeout(180_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/optimization");
  await page.getByLabel("Username", { exact: true }).fill(process.env.PP_E2E_USERNAME ?? "presenter");
  await page.getByLabel("Password", { exact: true }).fill(process.env.PP_E2E_PASSWORD ?? "pantry-local-demo");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "1 · Select a forecast" })).toBeVisible();
  await expect(page.getByLabel("Transfer mode (required)")).toHaveValue("");
  await page.getByRole("button", { name: "Generate forecast", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("SUCCEEDED", { timeout: 90_000 });
  await expect(page.getByLabel("Saved planning-ready forecast")).not.toHaveValue("");
  await page.getByLabel("Transfer mode (required)").selectOption("HUB_ONLY");
  await page.getByRole("button", { name: "Freeze scenario", exact: true }).click();
  await expect(page.getByRole("button", { name: "Compare frozen scenario", exact: true })).toBeEnabled();
  const first = await page.getByLabel("Read a saved scenario").inputValue();
  await page.getByLabel("Native search per method (seconds)").fill("1");
  await page.getByRole("button", { name: "Compare frozen scenario", exact: true }).click();
  await expect(page).toHaveURL(/kind=comparisons/);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Comparison results · SUCCEEDED", exact: true })).toBeVisible({ timeout: 90_000 });
  await expect(page.getByText("Independent replay: passed.", { exact: false })).toHaveCount(2);
  await expect(page.getByRole("table")).toHaveCount(2);
  await page.getByText("Edit simulated policy and assumptions", { exact: true }).focus();
  await page.keyboard.press("Enter");
  const assumptions = JSON.parse(await page.getByLabel("Assumptions JSON").inputValue());
  assumptions.policy.beta_percent = assumptions.policy.beta_percent === 75 ? 50 : 75;
  await page.getByLabel("Assumptions JSON").fill(JSON.stringify(assumptions, null, 2));
  await page.getByRole("button", { name: "Save new assumptions version", exact: true }).click();
  await expect(page.getByRole("button", { name: "Save new assumptions version", exact: true })).toBeDisabled();
  await page.getByLabel("Demand multiplier").fill("1.1");
  await page.getByLabel("Transfer mode (required)").selectOption("HUB_AND_PANTRY");
  // A refresh restores saved computation, while revised controls remain explicit.
  const forecast = await page.getByLabel("Saved planning-ready forecast").locator("option").nth(1).getAttribute("value");
  await page.getByLabel("Saved planning-ready forecast").selectOption(forecast!);
  await page.getByRole("button", { name: "Save revised scenario", exact: true }).click();
  await expect(page.getByLabel("Read a saved scenario")).not.toHaveValue(first);
  await page.getByRole("button", { name: "Compare frozen scenario", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Comparison results · SUCCEEDED", exact: true })).toBeVisible({ timeout: 90_000 });
  await page.getByText("Edit simulated policy and assumptions", { exact: true }).click();
  for (const [width, height] of [[1440, 900], [1280, 720], [390, 844]]) {
    await page.setViewportSize({ width, height });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expectNoSeriousA11yViolations(page, testInfo, `optimization ${width}x${height}`);
    await page.screenshot({ path: testInfo.outputPath(`optimization-${width}.png`), fullPage: true });
  }
  expect(errors).toEqual([]);
});

test("a real failed partner preserves and displays the verified survivor", async ({ page }) => {
  test.skip(process.env.PP_RUN_CONNECTED !== "1", "Requires isolated connected demo and Linux worker");
  test.setTimeout(120_000);
  await page.goto("/optimization");
  await page.getByLabel("Username", { exact: true }).fill(process.env.PP_E2E_USERNAME ?? "presenter");
  await page.getByLabel("Password", { exact: true }).fill(process.env.PP_E2E_PASSWORD ?? "pantry-local-demo");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByLabel("Read a saved scenario").locator("option").nth(1)).toHaveAttribute("value", /.+/);
  await page.getByLabel("Read a saved scenario").selectOption({ index: 1 });
  await page.getByLabel("Native search per method (seconds)").fill("3");
  await page.getByRole("button", { name: "Compare frozen scenario", exact: true }).click();
  await expect(page).toHaveURL(/kind=comparisons/);
  const jobId = new URL(page.url()).searchParams.get("job")!;
  const root = path.resolve(process.cwd(), "../..");
  const docker = process.env.PP_E2E_DOCKER;
  const command = docker ?? path.join(root, "apps/api/.venv/bin/python");
  const args = docker
    ? ["exec", process.env.PP_E2E_WORKER_CONTAINER ?? "pantrypulse-or-worker", "/app/.venv/bin/python", "/workspace/scripts/quality/fail-demo-partner.py", jobId]
    : [path.join(root, "scripts/quality/fail-demo-partner.py"), jobId];
  await promisify(execFile)(command, args, { timeout: 70_000 });
  await expect(page.getByRole("heading", { name: "Comparison results · PARTIAL", exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Independent replay: passed.", { exact: false })).toHaveCount(1);
  await expect(page.getByRole("table")).toHaveCount(1);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Comparison results · PARTIAL", exact: true })).toBeVisible();
  await expect(page.getByText("Independent replay: passed.", { exact: false })).toHaveCount(1);
});

test("cancel and retry a durable comparison through the real proxy", async ({ page }) => {
  test.skip(process.env.PP_RUN_CONNECTED !== "1", "Requires isolated connected demo");
  test.setTimeout(120_000);
  await page.goto("/optimization");
  await page.getByLabel("Username", { exact: true }).fill(process.env.PP_E2E_USERNAME ?? "presenter");
  await page.getByLabel("Password", { exact: true }).fill(process.env.PP_E2E_PASSWORD ?? "pantry-local-demo");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const selector = page.getByLabel("Read a saved scenario");
  await expect(selector.locator("option").nth(1)).toHaveAttribute("value", /.+/);
  await selector.selectOption({ index: 1 });
  await page.getByLabel("Native search per method (seconds)").fill("2");
  await page.getByRole("button", { name: "Compare frozen scenario", exact: true }).click();
  await expect(page).toHaveURL(/kind=comparisons/);
  await page.getByRole("button", { name: "Cancel computation", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("CANCELLED", { timeout: 30_000 });
  await page.reload();
  await expect(page.getByRole("status")).toContainText("CANCELLED");
  await page.getByRole("button", { name: "Retry frozen attempt", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Comparison results · SUCCEEDED", exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("2s search per method.", { exact: false })).toBeVisible();
});

test("a late real comparison response cannot replace a newly frozen scenario", async ({ page }) => {
  test.skip(process.env.PP_RUN_CONNECTED !== "1", "Requires isolated connected demo");
  test.setTimeout(120_000);
  await page.goto("/optimization");
  await page.getByLabel("Username", { exact: true }).fill(process.env.PP_E2E_USERNAME ?? "presenter");
  await page.getByLabel("Password", { exact: true }).fill(process.env.PP_E2E_PASSWORD ?? "pantry-local-demo");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const selector = page.getByLabel("Read a saved scenario");
  await expect(selector.locator("option").nth(1)).toHaveAttribute("value", /.+/);
  await selector.selectOption({ index: 1 });
  await expect(page.getByRole("button", { name: "Compare frozen scenario", exact: true })).toBeEnabled();
  const original = await selector.inputValue();
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  let received!: () => void;
  const responseReady = new Promise<void>((resolve) => { received = resolve; });
  await page.route("**/api/v1/comparisons/*", async (route) => {
    const response = await route.fetch(); // Genuine committed output, only transport is delayed.
    expect(response.status()).toBe(200);
    received();
    await gate;
    await route.fulfill({ response });
  });
  try {
    await page.getByLabel("Native search per method (seconds)").fill("4");
    await page.getByRole("button", { name: "Compare frozen scenario", exact: true }).click();
    await responseReady;
    await page.getByLabel("Demand multiplier").fill("1.2");
    const savedResponse = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/v1/scenarios" && response.request().method() === "POST");
    await page.getByRole("button", { name: "Save revised scenario", exact: true }).click();
    const revised = (await (await savedResponse).json()).id;
    expect(revised).not.toBe(original);
    await expect(selector).toHaveValue(revised);
    const returnedScenario = page.waitForResponse((response) => response.url().includes(`/api/v1/scenarios/${original}`));
    release();
    await returnedScenario;
    await page.getByRole("button", { name: "Refresh saved work", exact: true }).click();
    await expect(selector).toHaveValue(revised);
    await expect(page.getByRole("heading", { name: /Comparison results/ })).toHaveCount(0);
  } finally {
    release();
    await page.unrouteAll({ behavior: "wait" });
  }
});
