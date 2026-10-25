import { expect, test, type Page, type Route } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";

// Overview wired to the presenter APIs (PR #78) through the same-origin proxy. Every test mocks the
// browser's /api/v1 requests, so no backend is needed; the connected test at the end needs one.

const FIXTURE_LABEL = "SIMULATED — static design fixture, not model output";
const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const HUB = id(1);
const RIVERBEND = id(2), OAK = id(3), CEDAR = id(4), MAPLE = id(5), WILLOW = id(6), PINE = id(7);
const MEAL = id(101), WATER = id(102);
const FORECAST = id(201);
const DAYS = ["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06", "2026-11-07", "2026-11-08"];
const TZ = "America/New_York";
const OBSERVED = "2026-11-02T14:30:00Z";

const SITES = [
  { id: HUB, name: "Gator Distribution Hub", role: "HUB", timezone: TZ },
  { id: RIVERBEND, name: "Riverbend Pantry", role: "BENEFICIARY", timezone: TZ },
  { id: OAK, name: "Oak Terrace Pantry", role: "BENEFICIARY", timezone: TZ },
  { id: CEDAR, name: "Cedar Grove Pantry", role: "BENEFICIARY", timezone: TZ },
  { id: MAPLE, name: "Maple Crossing Pantry", role: "BENEFICIARY", timezone: TZ },
  { id: WILLOW, name: "Willow Creek Pantry", role: "BENEFICIARY", timezone: TZ },
  { id: PINE, name: "Pine Ridge Pantry", role: "BENEFICIARY", timezone: TZ },
] as const;
const PRODUCTS = [{ id: MEAL, name: "Shelf-stable meals", base_unit: "meal" }, { id: WATER, name: "Bottled water", base_unit: "bottle" }];

const catalog = { sites: SITES, products: PRODUCTS, sources: [] };

function lot(n: number, quantity: string, expiry: "DATED" | "NON_EXPIRING", expiresOn: string | null, usable = true) {
  return { lot_id: id(1000 + n), batch_key: `B-${n}`, metadata_version: "m1", on_hand_quantity: quantity, eligibility: usable ? "ELIGIBLE" : "HELD",
    exclusion_reason: usable ? null : "HELD", expiry_kind: expiry, expires_on: expiresOn, usable };
}

function inventory(usableRiverbendMeals = "40.000") {
  return SITES.flatMap((site) => PRODUCTS.map((product) => {
    const riverbendMeals = site.id === RIVERBEND && product.id === MEAL;
    const usable = riverbendMeals ? usableRiverbendMeals : site.role === "HUB" ? "900.000" : "120.000";
    return {
      site_id: site.id, site_name: site.name, product_id: product.id, product_name: product.name, base_unit: product.base_unit,
      timezone: TZ, local_date: DAYS[0], observed_at: OBSERVED, inventory_version: "v7",
      on_hand_quantity: usable, usable_quantity: usable, excluded_quantity: riverbendMeals ? "10.000" : "0", excluded_quantities: riverbendMeals ? { HELD: "10.000" } : {},
      // Riverbend meals: one dated lot inside the horizon, one non-expiring, one held (never counted).
      lots: riverbendMeals ? [lot(1, "25.000", "DATED", "2026-11-04"), lot(2, "15.000", "NON_EXPIRING", null), lot(3, "10.000", "DATED", "2026-11-03", false)] : [],
    };
  }));
}

function summary({ latest = { id: FORECAST, job_id: id(301), planning_ready: true, recorded_at: "2026-11-02T12:05:00Z" } as object | null, usable = "40.000" } = {}) {
  return { observed_at: OBSERVED, inventory: inventory(usable), latest_forecast: latest };
}

type Day = [demand: number, served: number, unmet: number, eligibleEnd: number];
function series(siteId: string, productId: string, unit: string, days: Day[]) {
  return { site_id: siteId, product_id: productId, base_unit: unit, actual_provider: "SEASONAL_NAIVE",
    days: days.map(([demand, served, unmet, end], index) => ({ day: DAYS[index], demand: String(demand), served: String(served), unmet: String(unmet), eligible_end: String(end) })) };
}
const covered = (start: number): Day[] => DAYS.map((_, index) => [20, 20, 0, start - 20 * (index + 1)]);

const shortages = {
  forecast_run_id: FORECAST,
  observed_at: OBSERVED,
  warnings: ["Pine Ridge Pantry demand uses the moving-average fallback."],
  series: [
    // Riverbend meals: short from the first day (Shortfall).
    series(RIVERBEND, MEAL, "meal", [[70, 55, 15, 0], [60, 0, 60, 0], [60, 0, 60, 0], [60, 0, 60, 0], [60, 0, 60, 0], [60, 0, 60, 0], [60, 0, 60, 0]]),
    // Oak Terrace meals: covered until Wed, Nov 4 (Watch).
    series(OAK, MEAL, "meal", [[50, 50, 0, 70], [50, 50, 0, 20], [50, 20, 30, 0], [50, 0, 50, 0], [50, 0, 50, 0], [50, 0, 50, 0], [50, 0, 50, 0]]),
    series(CEDAR, MEAL, "meal", covered(300)),
    series(WILLOW, MEAL, "meal", covered(300)),
    series(PINE, MEAL, "meal", covered(300)),
    // Maple Crossing has no meal series: Not evaluated. Only Riverbend has a water series.
    series(RIVERBEND, WATER, "bottle", covered(400)),
  ],
};

type Reply = { status: number; body: unknown };
const ok = (body: unknown): Reply => ({ status: 200, body });
const fail = (status: number, code: string, message = code.toLowerCase().replaceAll("_", " ")): Reply => ({ status, body: { error: { code, message, details: {} }, request_id: id(999) } });

async function mockApi(page: Page, replies: { catalog?: Reply; summary?: Reply; shortages?: Reply }) {
  const hits: string[] = [];
  const handle = (key: "catalog" | "summary" | "shortages", fallback: Reply) => async (route: Route) => {
    hits.push(key);
    const reply = replies[key] ?? fallback;
    await route.fulfill({ status: reply.status, contentType: "application/json", body: JSON.stringify(reply.body) });
  };
  await page.route("**/api/v1/forecast-catalog", handle("catalog", ok(catalog)));
  await page.route("**/api/v1/dashboard/summary", handle("summary", ok(summary())));
  await page.route(`**/api/v1/shortages/**`, handle("shortages", ok(shortages)));
  return hits;
}

async function open(page: Page, width = 1440, height = 900) {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.setViewportSize({ width, height });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/overview");
  await expect(page.getByRole("heading", { level: 1, name: "Network Atlas" })).toBeVisible();
  // Initial snapshot waits on the API; mocks are instant but the dev server may still be compiling.
  await expect(page.locator("[data-marker-role]")).toHaveCount(7, { timeout: 15_000 });
  return pageErrors;
}

const marker = (page: Page, name: string) => page.getByRole("button", { name: new RegExp(`^${name}, `) });

async function inspect(page: Page, name: string) {
  await marker(page, name).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Inspect site" }).click();
  const inspector = page.getByTestId("site-inspector");
  await expect(inspector.getByRole("heading", { name })).toBeVisible();
  return inspector;
}

for (const [width, height] of [[1440, 900], [390, 844]]) {
  test(`presenter session shows live statuses, units, dates, provider and warnings at ${width}x${height}`, async ({ page }, testInfo) => {
    const hits = await mockApi(page, {});
    const pageErrors = await open(page, width, height);
    expect(hits.filter((hit) => hit === "shortages")).toHaveLength(1);

    await expect(page.getByText(FIXTURE_LABEL)).toHaveCount(0);
    await expect(page.getByText("Live · simulated network", { exact: true }).first()).toBeVisible();
    await expect(page.locator("[data-overview-source]")).toHaveAttribute("data-overview-source", "live");
    await expect(page.getByText("Pine Ridge Pantry demand uses the moving-average fallback.")).toBeVisible();
    await expect(page.getByText(/SEASONAL_NAIVE/).first()).toBeVisible();

    // Statuses from the shortage days (display-only rules), units from base_unit, dates from the days.
    await expect(marker(page, "Riverbend Pantry")).toHaveAccessibleName(/Shortfall, next deficit Mon, Nov 2: 15 meals unmet/);
    await expect(marker(page, "Oak Terrace Pantry")).toHaveAccessibleName(/Watch, next deficit Wed, Nov 4: 30 meals unmet/);
    await expect(marker(page, "Cedar Grove Pantry")).toHaveAccessibleName(/Covered/);
    await expect(marker(page, "Maple Crossing Pantry")).toHaveAccessibleName(/Not evaluated/);
    await expect(marker(page, "Gator Distribution Hub")).toHaveAccessibleName(/Hub · source, 900 meals eligible now/);
    await expect(page.locator("[data-supply-link]")).toHaveCount(6);
    await expect(page.getByRole("combobox", { name: "Local day" })).toHaveText(/Mon, Nov 2/);

    if (width >= 1024) {
      await expectNoSeriousA11yViolations(page, testInfo, `overview live ${width}x${height}`);
      await page.screenshot({ path: testInfo.outputPath(`overview-live-${width}.png`), fullPage: true });
    }

    const inspector = await inspect(page, "Riverbend Pantry");
    await expect(inspector.getByText("Live · simulated network", { exact: true })).toBeVisible();
    await expect(inspector).toContainText("SEASONAL_NAIVE");
    await expect(inspector).toContainText("40 meals now → 0 meals by Sun, Nov 8");
    await expect(inspector).toContainText("1 lot · 25 meals");
    await expect(inspector).toContainText("base unit: meal");
    await inspector.getByRole("tab", { name: "Demand" }).click();
    await expect(inspector).toContainText("Donation outlook: Not in this projection");
    await expect(inspector).toContainText("Projected served");
    await inspector.getByRole("button", { name: "Show data table" }).click();
    await expect(inspector.getByRole("columnheader", { name: "Served (projected, meals)" })).toBeVisible();
    await expect(inspector.getByRole("columnheader", { name: /Donation/ })).toHaveCount(0);
    if (width < 1024) {
      await expectNoSeriousA11yViolations(page, testInfo, `overview live ${width}x${height} inspector`);
      await page.screenshot({ path: testInfo.outputPath(`overview-live-${width}.png`), fullPage: true });
    }
    expect(pageErrors).toEqual([]);
  });

  test(`visitor (401) sees the labelled static fixture and a sign-in notice at ${width}x${height}`, async ({ page }, testInfo) => {
    const hits = await mockApi(page, { catalog: fail(401, "AUTHENTICATION_REQUIRED"), summary: fail(401, "AUTHENTICATION_REQUIRED") });
    const pageErrors = await open(page, width, height);
    await expect(page.getByText(FIXTURE_LABEL)).toBeVisible();
    await expect(page.locator("[data-overview-source]")).toHaveAttribute("data-overview-source", "fixture");
    const notice = page.locator("[data-live-notice]");
    await expect(notice).toContainText("Sign in for live data");
    await expect(notice.getByRole("link", { name: /optimization workspace/i })).toHaveAttribute("href", "/optimization");
    await expect(page.getByRole("alert").filter({ hasText: "Live data unavailable" })).toHaveCount(0);
    await expect(page.getByText("Live · simulated network", { exact: true })).toHaveCount(0);
    expect(hits).not.toContain("shortages");
    await expectNoSeriousA11yViolations(page, testInfo, `overview visitor ${width}x${height}`);
    if (width >= 1024) await page.screenshot({ path: testInfo.outputPath(`overview-visitor-${width}.png`), fullPage: true });
    expect(pageErrors).toEqual([]);
  });
}

test("403 is also treated as a visitor", async ({ page }) => {
  await mockApi(page, { summary: fail(403, "PRESENTER_REQUIRED") });
  await open(page);
  await expect(page.getByText(FIXTURE_LABEL)).toBeVisible();
  await expect(page.locator("[data-live-notice]")).toContainText("Sign in for live data");
});

for (const [label, latest] of [["no forecast", null], ["forecast not planning-ready", { id: FORECAST, job_id: id(301), planning_ready: false, recorded_at: "2026-11-02T12:05:00Z" }]] as const) {
  test(`${label}: live inventory, every beneficiary Not evaluated`, async ({ page }) => {
    const hits = await mockApi(page, { summary: ok(summary({ latest })) });
    await open(page);
    expect(hits).not.toContain("shortages");
    await expect(page.getByText(FIXTURE_LABEL)).toHaveCount(0);
    const notice = page.locator("[data-live-notice]");
    await expect(notice).toContainText("No planning-ready forecast yet");
    await expect(notice.getByRole("link", { name: /optimization workspace/i })).toHaveAttribute("href", "/optimization");
    for (const site of SITES.filter((item) => item.role === "BENEFICIARY")) await expect(marker(page, site.name)).toHaveAccessibleName(/Not evaluated/);
    const inspector = await inspect(page, "Riverbend Pantry");
    await expect(inspector).toContainText("40 meals");
  });
}

test("stale forecast (409) keeps live inventory and marks statuses Not evaluated", async ({ page }, testInfo) => {
  await mockApi(page, { shortages: fail(409, "FORECAST_HORIZON_ALREADY_STARTED") });
  await open(page);
  await expect(page.getByText(FIXTURE_LABEL)).toHaveCount(0);
  const notice = page.locator("[data-live-notice]");
  await expect(notice).toContainText("Stale: FORECAST_HORIZON_ALREADY_STARTED");
  await expect(notice).toContainText("Nov 2");
  await expect(notice.getByRole("link", { name: /Run a new forecast/i })).toHaveAttribute("href", "/optimization");
  for (const site of SITES.filter((item) => item.role === "BENEFICIARY")) await expect(marker(page, site.name)).toHaveAccessibleName(/Not evaluated/);
  await page.screenshot({ path: testInfo.outputPath("overview-stale-1440.png"), fullPage: true });
  const inspector = await inspect(page, "Riverbend Pantry");
  await expect(inspector).toContainText("40 meals");
});

test("DEMAND_FORECAST_UNAVAILABLE marks statuses Not evaluated with that reason", async ({ page }) => {
  await mockApi(page, { shortages: fail(409, "DEMAND_FORECAST_UNAVAILABLE", "The saved forecast has no demand series.") });
  await open(page);
  const notice = page.locator("[data-live-notice]");
  await expect(notice).toContainText("DEMAND_FORECAST_UNAVAILABLE");
  await expect(notice).toContainText("The saved forecast has no demand series.");
  await expect(marker(page, "Riverbend Pantry")).toHaveAccessibleName(/Not evaluated/);
  const inspector = await inspect(page, "Riverbend Pantry");
  await expect(inspector).toContainText("DEMAND_FORECAST_UNAVAILABLE");
});

test("503 shows the fixture with a Live data unavailable alert; Retry recovers to live", async ({ page }) => {
  const replies: { summary?: Reply } = { summary: fail(503, "BACKEND_NOT_CONFIGURED") };
  await page.route("**/api/v1/forecast-catalog", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(catalog) }));
  await page.route("**/api/v1/dashboard/summary", (route) => {
    const reply = replies.summary ?? ok(summary());
    return route.fulfill({ status: reply.status, contentType: "application/json", body: JSON.stringify(reply.body) });
  });
  await page.route("**/api/v1/shortages/**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(shortages) }));
  await open(page);
  const alert = page.getByRole("alert").filter({ hasText: "Live data unavailable" });
  await expect(alert).toContainText("BACKEND_NOT_CONFIGURED");
  await expect(page.getByText(FIXTURE_LABEL)).toBeVisible();
  await expect(page.locator("[data-overview-source]")).toHaveAttribute("data-overview-source", "fixture");
  replies.summary = undefined;
  await alert.getByRole("button", { name: "Retry" }).click();
  await expect(page.locator("[data-overview-source]")).toHaveAttribute("data-overview-source", "live");
  await expect(page.getByText(FIXTURE_LABEL)).toHaveCount(0);
  await expect(page.getByRole("alert").filter({ hasText: "Live data unavailable" })).toHaveCount(0);
  await expect(marker(page, "Riverbend Pantry")).toHaveAccessibleName(/Shortfall/);
});

test("a network error also falls back to the fixture with the alert", async ({ page }) => {
  await page.route("**/api/v1/forecast-catalog", (route) => route.abort("connectionrefused"));
  await page.route("**/api/v1/dashboard/summary", (route) => route.abort("connectionrefused"));
  await open(page);
  await expect(page.getByRole("alert").filter({ hasText: "Live data unavailable" })).toContainText("NETWORK_ERROR");
  await expect(page.getByText(FIXTURE_LABEL)).toBeVisible();
});

test("a quantity beyond Number.MAX_SAFE_INTEGER is shown as unavailable, never rounded", async ({ page }) => {
  await mockApi(page, { summary: ok(summary({ usable: "9007199254740993" })) });
  await open(page);
  const inspector = await inspect(page, "Riverbend Pantry");
  await expect(inspector).toContainText("Unavailable now → 0 meals by Sun, Nov 8");
  await expect(inspector).not.toContainText("9,007,199,254,740,99");
});

test("connected: a signed-in presenter sees live data from the seeded backend", async ({ page }) => {
  test.skip(process.env.PP_RUN_CONNECTED !== "1", "Requires isolated seeded PostgreSQL, API and Linux worker");
  await page.goto("/optimization");
  await page.getByLabel("Username", { exact: true }).fill(process.env.PP_E2E_USERNAME ?? "presenter");
  await page.getByLabel("Password", { exact: true }).fill(process.env.PP_E2E_PASSWORD ?? "pantry-local-demo");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "1 · Select a forecast" })).toBeVisible();
  await page.goto("/overview");
  await expect(page.locator("[data-overview-source]")).toHaveAttribute("data-overview-source", "live");
  await expect(page.getByText(FIXTURE_LABEL)).toHaveCount(0);
  await expect(page.locator("[data-marker-role]")).not.toHaveCount(0);
});
