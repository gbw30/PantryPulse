import { expect, test, type Page } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";
import {
  COMPARISON, COMPARISON_B, HASH_CLASSICAL, PLAN_CLASSICAL, SCENARIO_B, allocationResults, comparison, fail, method, mockApi, ok, scenario,
} from "./recommendations-fixtures";

// PP-54 Recommendations (Collage 2 Action Plan). Every test mocks the browser's /api/v1 requests;
// the connected test at the end needs a running backend and PP_RUN_CONNECTED=1.

const TABS = ["Action Plan", "Site Recommendations", "Network Optimization", "Impact & Fairness"];
const OPEN_02 = "not attributable to one transfer (V5 OPEN-02)";
const MOCKUP_ONLY = ["households", "Alex Chen", "Central Warehouse", "Critical", "+24 meals", "+320", "18 → 7", "−28%"];

async function open(page: Page, query = "", width = 1440, height = 900) {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width, height });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`/recommendations${query}`);
  await expect(page.getByRole("heading", { level: 1, name: "Recommendations" })).toBeVisible();
  return errors;
}

const rows = (page: Page) => page.locator("[data-action-row]");
const preview = (page: Page) => page.locator("[data-impact-preview]");
const notice = (page: Page, kind: string) => page.locator(`[data-rec-notice="${kind}"]`);
const methodButton = (page: Page, name: string) => page.getByRole("group", { name: "Plan method" }).getByRole("button", { name: new RegExp(`^${name}`) });
const reviewButton = (page: Page) => page.getByRole("button", { name: "Mark reviewed — simulation" });

async function expectNoMockupContent(page: Page) {
  const text = (await page.locator("main").textContent()) ?? "";
  for (const phrase of MOCKUP_ONLY) expect(text, `mockup-only "${phrase}"`).not.toContain(phrase);
  expect(text).not.toMatch(/\+\d+(\.\d+)?%/);
}

for (const [width, height] of [[1440, 900], [1280, 720], [390, 844]]) {
  test(`verified plan: queue, Impact Preview and four tabs at ${width}x${height}`, async ({ page }, testInfo) => {
    await mockApi(page);
    const errors = await open(page, "", width, height);
    await expect(rows(page)).toHaveCount(2, { timeout: 15_000 });

    await expect(page.getByRole("tab")).toHaveText(TABS);
    await expect(page.getByRole("tab", { name: "Action Plan" })).toHaveAttribute("aria-selected", "true");
    // Default: first VERIFIED method in API order, labelled.
    await expect(methodButton(page, "Classical GP")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByText("Simulated data", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Independent replay: passed").first()).toBeVisible();
    await expect(page.getByText(/Hub only/).first()).toBeVisible();

    const first = rows(page).first();
    await expect(first).toContainText("Gator Distribution Hub → Riverbend Pantry");
    await expect(first).toContainText("40 meals");
    await expect(first).toContainText("Arrives Tue, Nov 3");
    await expect(first).toContainText("Deficit Wed, Nov 4");
    await expect(rows(page).nth(1)).toContainText("No deficit in window");

    const impact = preview(page);
    for (const heading of ["Selected action details", "Plan-level projected impact", "Remaining unmet need"]) {
      await expect(impact.getByRole("heading", { name: heading })).toBeVisible();
    }
    await expect(impact).toContainText(OPEN_02);
    await expect(impact).toContainText("Selected action: Gator Distribution Hub → Riverbend Pantry · 40 meals");
    await expect(impact.locator("[data-metric='unmet'][data-product='meal']")).toContainText("90 meals → 20 meals");
    await expect(impact.locator("[data-metric='unmet'][data-product='bottle']")).toContainText("10 bottles → 10 bottles");
    await expect(impact.locator("[data-remaining]")).toContainText("Riverbend Pantry");
    await expect(page.getByText("No stock, purchase or dispatch effect").first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Compare in Scenario Lab" })).toHaveAttribute("href", `/scenarios?comparison=${COMPARISON}`);
    await expect(reviewButton(page)).toBeVisible();
    await expectNoMockupContent(page);

    // Inspect another row: the preview swaps, focus stays on the invoking control.
    const inspect = rows(page).nth(1).getByRole("button", { name: /^Inspect/ });
    await inspect.focus();
    await page.keyboard.press("Enter");
    await expect(impact).toContainText("Selected action: Gator Distribution Hub → Oak Terrace Pantry · 30 meals");
    await expect(inspect).toBeFocused();

    await expectNoSeriousA11yViolations(page, testInfo, `recommendations action plan ${width}x${height}`);
    await page.screenshot({ path: testInfo.outputPath(`recommendations-${width}.png`), fullPage: true });

    // The other verified method lists only its own actions.
    await methodButton(page, "EGP-PI-inspired").click();
    await expect(rows(page)).toHaveCount(3);
    await expect(page.locator("main")).toContainText("10 bottles");

    for (const name of TABS.slice(1)) {
      await page.getByRole("tab", { name }).click();
      await expect(page.getByRole("tab", { name })).toHaveAttribute("aria-selected", "true");
      await expectNoSeriousA11yViolations(page, testInfo, `recommendations ${name} ${width}x${height}`);
    }
    await expect(page).toHaveURL(/tab=fairness/);
    await expectNoMockupContent(page);
    expect(errors).toEqual([]);
  });
}

test("Impact & Fairness lists every goal with AP/RP, N/A ratios and decimal rationals", async ({ page }, testInfo) => {
  await mockApi(page);
  await open(page, "?tab=fairness");
  const table = page.getByRole("table", { name: /Per-goal outcome/ });
  await expect(table).toBeVisible({ timeout: 15_000 });
  await expect(table.locator("tbody tr")).toHaveCount(12);
  const riverbendMeals = table.locator("tbody tr").filter({ hasText: "Riverbend Pantry" }).filter({ hasText: "meal" }).first();
  await expect(riverbendMeals).toContainText("80 meals");
  await expect(riverbendMeals).toContainText("0.8");
  await expect(riverbendMeals).toContainText("AP yes");
  const pineWater = table.locator("tbody tr").filter({ hasText: "Pine Ridge Pantry" }).filter({ hasText: "bottle" });
  await expect(pineWater).toContainText("N/A");
  await expect(page.getByRole("table", { name: /Group counts/ })).toContainText("6");
  await expect(page.getByText(/vulnerability attributes are SIMULATED/i)).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("recommendations-fairness-1440.png"), fullPage: true });
});

test("Network Optimization shows both methods, verified constraints and the Scenario Lab link", async ({ page }) => {
  await mockApi(page);
  await open(page, "?tab=network");
  const panel = page.getByRole("tabpanel", { name: "Network Optimization" });
  await expect(panel.getByText("Classical GP").first()).toBeVisible({ timeout: 15_000 });
  await expect(panel.getByText("EGP-PI-inspired").first()).toBeVisible();
  await expect(panel.getByText("FEFO lot order")).toBeVisible();
  await expect(panel.getByText(/passed independent replay/).first()).toBeVisible();
  await expect(panel.getByRole("link", { name: "Open in Scenario Lab" })).toHaveAttribute("href", `/scenarios?comparison=${COMPARISON}`);
});

test("Site Recommendations separates receiving and sending rows with reserve floors", async ({ page }) => {
  await mockApi(page);
  await open(page, "?tab=sites");
  const panel = page.getByRole("tabpanel", { name: "Site Recommendations" });
  await expect(panel.getByRole("combobox", { name: "Site" })).toBeVisible({ timeout: 15_000 });
  // Default site is the hub: it sends, and its reserve floors are listed.
  await expect(panel.locator("[data-site-sending] [data-action-row]")).toHaveCount(2);
  await expect(panel).toContainText("25 meals");
  await panel.getByRole("combobox", { name: "Site" }).click();
  await page.getByRole("option", { name: /Riverbend Pantry/ }).click();
  await expect(panel.locator("[data-site-receiving] [data-action-row]")).toHaveCount(1);
  await expect(panel.locator("[data-site-sending] [data-action-row]")).toHaveCount(0);
  await expect(panel).toContainText("20 meals");
});

test("PARTIAL: the failed method shows its code, the verified one is the default and usable", async ({ page }, testInfo) => {
  await mockApi(page, { comparisons: { [COMPARISON]: ok(comparison({ outcome: "PARTIAL", methods: [
    method("CLASSICAL_GP", { outcome: "FAILED", errorCode: "SOLVER_MODEL_INVALID", nativeStatus: "MODEL_INVALID" }), method("EGP_PI_INSPIRED"),
  ] })) }, results: { [COMPARISON]: ok(allocationResults(["EGP_PI_INSPIRED"])) } });
  await open(page);
  await expect(notice(page, "partial")).toBeVisible({ timeout: 15_000 });
  await expect(methodButton(page, "EGP-PI-inspired")).toHaveAttribute("aria-pressed", "true");
  await expect(rows(page)).toHaveCount(3);
  await methodButton(page, "Classical GP").click();
  await expect(rows(page)).toHaveCount(0);
  await expect(page.locator("main")).toContainText("SOLVER_MODEL_INVALID");
  await expect(reviewButton(page)).toHaveCount(0);
  await expectNoSeriousA11yViolations(page, testInfo, "recommendations partial");
});

test("FAILED comparison lists no actions and explains why", async ({ page }) => {
  await mockApi(page, { comparisons: { [COMPARISON]: ok(comparison({ outcome: "FAILED", methods: [
    method("CLASSICAL_GP", { outcome: "TIMED_OUT", errorCode: "SEARCH_TIME_LIMIT" }), method("EGP_PI_INSPIRED", { outcome: "FAILED", errorCode: "SOLVER_UNKNOWN", nativeStatus: "UNKNOWN" }),
  ] })) }, results: { [COMPARISON]: ok(allocationResults([])) } });
  await open(page);
  await expect(notice(page, "failed")).toBeVisible({ timeout: 15_000 });
  await expect(rows(page)).toHaveCount(0);
  await expect(page.locator("main")).toContainText("SEARCH_TIME_LIMIT");
  await expect(reviewButton(page)).toHaveCount(0);
});

test("VERIFIED with zero assignments explains no feasible transfer and keeps residual need", async ({ page }) => {
  await mockApi(page, { comparisons: { [COMPARISON]: ok(comparison({ methods: [method("CLASSICAL_GP", { assignments: [] }), method("EGP_PI_INSPIRED", { assignments: [] })] })) } });
  await open(page);
  await expect(page.getByText("No feasible transfer with current resources").first()).toBeVisible({ timeout: 15_000 });
  await expect(rows(page)).toHaveCount(0);
  await expect(preview(page).locator("[data-remaining]")).toContainText("Riverbend Pantry");
});

test("FEASIBLE native status is labelled feasible, not proven optimal", async ({ page }) => {
  await mockApi(page, { comparisons: { [COMPARISON]: ok(comparison({ methods: [method("CLASSICAL_GP", { nativeStatus: "FEASIBLE" }), method("EGP_PI_INSPIRED")] })) } });
  await open(page);
  await expect(page.getByText(/feasible, not proven optimal/i).first()).toBeVisible({ timeout: 15_000 });
});

test("stale or historical scenario shows the sources-changed banner", async ({ page }) => {
  await mockApi(page, { comparisons: { [COMPARISON]: ok(comparison({ stale: true })) } });
  await open(page);
  await expect(notice(page, "stale")).toContainText("Sources changed since this scenario was frozen; review is still a simulation", { timeout: 15_000 });
  await expect(rows(page)).toHaveCount(2);
});

for (const [width, height] of [[1440, 900], [390, 844]]) {
  test(`visitor sees the read-only explanation and no review button at ${width}x${height}`, async ({ page }, testInfo) => {
    const hits = await mockApi(page, {}, { visitor: true });
    await open(page, "", width, height);
    await expect(notice(page, "visitor")).toBeVisible();
    await expect(notice(page, "visitor")).toContainText("Sign in");
    await expect(reviewButton(page)).toHaveCount(0);
    await expect(rows(page)).toHaveCount(0);
    expect(hits.paths).not.toContain("planning-catalog");
    await expectNoSeriousA11yViolations(page, testInfo, `recommendations visitor ${width}x${height}`);
    await page.screenshot({ path: testInfo.outputPath(`recommendations-visitor-${width}.png`), fullPage: true });
  });
}

test("no saved comparison points to Scenario Lab", async ({ page }) => {
  await mockApi(page, { catalog: ok({ source_revision: "r", next_before: null, next_before_id: null, assumptions: [], forecasts: [], scenarios: [], comparisons: [] }) });
  await open(page);
  await expect(notice(page, "empty")).toBeVisible({ timeout: 15_000 });
  await expect(notice(page, "empty").getByRole("link", { name: /Run a comparison in Scenario Lab/ })).toHaveAttribute("href", "/scenarios");
});

test("409 COMPARISON_NOT_PUBLISHED shows the still-computing notice", async ({ page }) => {
  await mockApi(page, { comparisons: { [COMPARISON]: fail(409, "COMPARISON_NOT_PUBLISHED") } });
  await open(page);
  await expect(notice(page, "computing")).toContainText("still computing", { timeout: 15_000 });
  await expect(rows(page)).toHaveCount(0);
  await expect(reviewButton(page)).toHaveCount(0);
});

test("network failure shows an alert with Retry that recovers", async ({ page }) => {
  const replies: { catalog?: "abort" } = { catalog: "abort" };
  await mockApi(page, replies);
  await open(page);
  const alert = page.getByRole("alert").filter({ hasText: "Could not load saved plans" });
  await expect(alert).toBeVisible({ timeout: 15_000 });
  await expect(alert).toContainText("NETWORK_ERROR");
  replies.catalog = undefined;
  await alert.getByRole("button", { name: "Retry" }).click();
  await expect(rows(page)).toHaveCount(2);
});

test("URL selects the comparison and tab; a late response for the previous comparison is ignored", async ({ page }) => {
  await mockApi(page, {
    comparisons: {
      [COMPARISON]: { status: 200, body: comparison(), delayMs: 1500 },
      [COMPARISON_B]: ok(comparison({ idValue: COMPARISON_B, scenarioId: SCENARIO_B, methods: [method("CLASSICAL_GP", { assignments: [] }), method("EGP_PI_INSPIRED", { assignments: [] })] })),
    },
    scenarios: { [SCENARIO_B]: ok(scenario(SCENARIO_B, 2)) },
  });
  await open(page, `?comparison=${COMPARISON}&tab=network`);
  await expect(page.getByRole("tab", { name: "Network Optimization" })).toHaveAttribute("aria-selected", "true");
  const select = page.getByRole("combobox", { name: "Saved comparison" });
  await select.click();
  await page.getByRole("option", { name: /PARTIAL/ }).click();
  await expect(page).toHaveURL(new RegExp(`comparison=${COMPARISON_B}`));
  await expect(page.getByText(/2 days from/).first()).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(1800);
  await expect(page.getByText(/2 days from/).first()).toBeVisible();
  await expect(page.getByText(/3 days from/)).toHaveCount(0);
});

test("presenter review POSTs once with the plan hash and shows Reviewed — simulation", async ({ page }, testInfo) => {
  const hits = await mockApi(page);
  await open(page);
  await expect(rows(page)).toHaveCount(2, { timeout: 15_000 });
  await reviewButton(page).click();
  const dialog = page.getByRole("dialog", { name: "Mark reviewed — simulation" });
  await expect(dialog).toContainText("No stock, purchase or dispatch effect");
  await dialog.getByLabel(/Note/).fill("Checked with the demo script.");
  await expectNoSeriousA11yViolations(page, testInfo, "recommendations review dialog");
  await dialog.getByRole("button", { name: "Mark reviewed" }).dblclick();
  await expect(page.getByText("Reviewed — simulation", { exact: true })).toBeVisible();
  expect(hits.reviews).toHaveLength(1);
  expect(hits.reviews[0].planId).toBe(PLAN_CLASSICAL);
  expect(hits.reviews[0].body).toMatchObject({ action: "REVIEWED", expected_result_hash: HASH_CLASSICAL, note: "Checked with the demo script." });
  expect(hits.reviews[0].key).toBeTruthy();
  await expect(dialog).toHaveCount(0);
  await expect(reviewButton(page)).toBeFocused();
});

test("review retry after a network error reuses the idempotency key", async ({ page }) => {
  const hits = await mockApi(page, { review: ["abort", { status: 201, body: {} }] });
  await open(page);
  await expect(rows(page)).toHaveCount(2, { timeout: 15_000 });
  await reviewButton(page).click();
  const dialog = page.getByRole("dialog", { name: "Mark reviewed — simulation" });
  await dialog.getByRole("button", { name: "Mark reviewed" }).click();
  await expect(dialog.getByRole("alert")).toContainText("Could not reach the server");
  await dialog.getByRole("button", { name: "Mark reviewed" }).click();
  await expect(page.getByText("Reviewed — simulation", { exact: true })).toBeVisible();
  expect(hits.reviews).toHaveLength(2);
  expect(hits.reviews[1].key).toBe(hits.reviews[0].key);
});

test("review 409 PLAN_REVISION_MISMATCH shows stale copy without retrying", async ({ page }) => {
  const hits = await mockApi(page, { review: [fail(409, "PLAN_REVISION_MISMATCH")] });
  await open(page);
  await expect(rows(page)).toHaveCount(2, { timeout: 15_000 });
  await reviewButton(page).click();
  await page.getByRole("dialog").getByRole("button", { name: "Mark reviewed" }).click();
  await expect(notice(page, "review-stale")).toContainText("This plan changed since it was loaded");
  await page.waitForTimeout(500);
  expect(hits.reviews).toHaveLength(1);
  await expect(page.getByText("Reviewed — simulation", { exact: true })).toHaveCount(0);
});

test("review 401 ends the presenter session", async ({ page }) => {
  await mockApi(page, { review: [fail(401, "PRESENTER_REQUIRED")] });
  await open(page);
  await expect(rows(page)).toHaveCount(2, { timeout: 15_000 });
  await reviewButton(page).click();
  await page.getByRole("dialog").getByRole("button", { name: "Mark reviewed" }).click();
  await expect(notice(page, "expired")).toContainText("session expired");
  await expect(reviewButton(page)).toHaveCount(0);
});

// Connected: creates and reviews its own real comparison through the current presenter flow.
test("connected: presenter reviews a real saved plan", async ({ page }) => {
  test.skip(process.env.PP_RUN_CONNECTED !== "1", "Set PP_RUN_CONNECTED=1 with a running backend");
  test.setTimeout(180_000);
  await page.goto("/overview");
  await page.getByRole("button", { name: "Presenter sign in" }).click();
  const signIn = page.getByRole("dialog", { name: "Presenter sign in" });
  await signIn.getByLabel("Username").fill(process.env.PP_E2E_USERNAME ?? "presenter");
  await signIn.getByLabel("Password").fill(process.env.PP_E2E_PASSWORD ?? "pantry-local-demo");
  await Promise.all([page.waitForEvent("load"), signIn.getByRole("button", { name: "Sign in", exact: true }).click()]);
  await page.goto("/scenarios");
  await page.getByRole("button", { name: "Generate forecast", exact: true }).click();
  await expect(page.locator("[data-job-state]")).toHaveAttribute("data-job-state", "SUCCEEDED", { timeout: 90_000 });
  await page.getByRole("radio", { name: "Hub to pantry only" }).check();
  await page.getByRole("button", { name: "Create frozen scenario" }).click();
  await page.getByLabel("Search seconds per method").fill("1");
  const submitting = page.waitForResponse((response) => /\/scenarios\/[^/]+\/compare-methods$/.test(new URL(response.url()).pathname) && response.request().method() === "POST");
  await page.getByRole("button", { name: "Compare methods", exact: true }).click();
  const accepted = await submitting;
  expect(accepted.status()).toBe(202);
  const comparisonId = (await accepted.json()).job_id as string;
  await expect(page.locator("[data-job-state]")).toContainText(comparisonId.slice(0, 8));
  await expect(page.locator("[data-job-state]")).toHaveAttribute("data-job-state", "SUCCEEDED", { timeout: 90_000 });
  await open(page, `?comparison=${comparisonId}`);
  await expect(reviewButton(page)).toBeVisible({ timeout: 30_000 });
  await reviewButton(page).click();
  await page.getByRole("dialog").getByRole("button", { name: "Mark reviewed" }).click();
  await expect(page.getByText("Reviewed — simulation", { exact: true })).toBeVisible({ timeout: 15_000 });
});
