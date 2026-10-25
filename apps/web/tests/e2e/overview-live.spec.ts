import { expect, test, type Locator, type Page, type Route } from "@playwright/test";
import type { components } from "../../../../packages/contracts/src/schema";
import { expectNoSeriousA11yViolations } from "./a11y";

// Overview wired to the presenter APIs (PR #78) through the same-origin proxy. Every test mocks the
// browser's /api/v1 requests, so no backend is needed; the connected test at the end needs one.
// Mocks are typed against the generated contract and use only values the API emits (integer strings,
// the error envelope's lower-cased message, the projection's own warnings).

type Schemas = components["schemas"];

const FIXTURE_LABEL = "SIMULATED — static design fixture, not model output";
const LIVE_PILL = "Live · simulated network";
const VISITOR_PILL = "Static fixture · visitor view";
const UNAVAILABLE_PILL = "Static fixture · live data unavailable";
const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const HUB = id(1);
const RIVERBEND = id(2), OAK = id(3), CEDAR = id(4), MAPLE = id(5), WILLOW = id(6), PINE = id(7);
const MEAL = id(101), WATER = id(102);
const FORECAST = id(201);
const DAYS = ["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06", "2026-11-07", "2026-11-08"];
const TZ = "America/New_York";
const OBSERVED = "2026-11-02T14:30:00Z";
const RECORDED = "2026-11-02T12:05:00Z";
// RECORDED in the network's zone (EST from Nov 1, 2026).
const RECORDED_LOCAL = "Nov 2, 7:05 AM EST";
const B = (value: number) => BigInt(value);

const SITES = [
  { id: HUB, name: "Gator Distribution Hub", role: "HUB", timezone: TZ },
  { id: RIVERBEND, name: "Riverbend Pantry", role: "BENEFICIARY", timezone: TZ },
  { id: OAK, name: "Oak Terrace Pantry", role: "BENEFICIARY", timezone: TZ },
  { id: CEDAR, name: "Cedar Grove Pantry", role: "BENEFICIARY", timezone: TZ },
  { id: MAPLE, name: "Maple Crossing Pantry", role: "BENEFICIARY", timezone: TZ },
  { id: WILLOW, name: "Willow Creek Pantry", role: "BENEFICIARY", timezone: TZ },
  { id: PINE, name: "Pine Ridge Pantry", role: "BENEFICIARY", timezone: TZ },
] satisfies Schemas["SiteSummary"][];
const PRODUCTS = [{ id: MEAL, name: "Shelf-stable meals", base_unit: "meal" }, { id: WATER, name: "Bottled water", base_unit: "bottle" }] satisfies Schemas["ProductSummary"][];
const BENEFICIARIES = SITES.filter((site) => site.role === "BENEFICIARY");

const catalog = { sites: SITES, products: PRODUCTS, sources: [{ id: id(401), name: "forecasting-core-demo-v1", classification: "SIMULATED" }] } satisfies Schemas["ForecastCatalog"];

// Usable (eligible) units now, per site: [meals, bottles]. Riverbend meals is overridable for the edge case.
const USABLE: Record<string, [bigint, bigint]> = {
  [HUB]: [B(900), B(900)], [RIVERBEND]: [B(40), B(400)], [OAK]: [B(120), B(120)],
  [CEDAR]: [B(300), B(120)], [MAPLE]: [B(300), B(120)], [WILLOW]: [B(300), B(120)], [PINE]: [B(300), B(120)],
};
const usableFor = (siteId: string, productId: string, riverbendMeals: bigint) =>
  siteId === RIVERBEND && productId === MEAL ? riverbendMeals : USABLE[siteId][productId === MEAL ? 0 : 1];

let lotCounter = 0;
function lot(quantity: bigint, expiry: "DATED" | "NON_EXPIRING", expiresOn: string | null, usable = true): Schemas["InventoryLotView"] {
  lotCounter += 1;
  return { lot_id: id(1000 + lotCounter), batch_key: `B-${lotCounter}`, metadata_version: "1", on_hand_quantity: String(quantity),
    eligibility: usable ? "ELIGIBLE" : "HELD", exclusion_reason: usable ? null : "HELD", expiry_kind: expiry, expires_on: expiresOn, usable };
}

function inventory(riverbendMeals: bigint): Schemas["InventorySnapshot"][] {
  return SITES.flatMap((site) => PRODUCTS.map((product) => {
    const usable = usableFor(site.id, product.id, riverbendMeals);
    // Riverbend meals: one dated lot inside the horizon, one non-expiring, one held (never counted as usable).
    const lots = site.id === RIVERBEND && product.id === MEAL
      ? [lot(B(25), "DATED", "2026-11-04"), lot(usable - B(25), "NON_EXPIRING", null), lot(B(10), "DATED", "2026-11-03", false)]
      : [lot(usable, "NON_EXPIRING", null)];
    const held = lots.filter((item) => !item.usable).reduce((total, item) => total + BigInt(item.on_hand_quantity), B(0));
    return {
      site_id: site.id, site_name: site.name, product_id: product.id, product_name: product.name, base_unit: product.base_unit,
      timezone: TZ, local_date: DAYS[0], observed_at: OBSERVED, inventory_version: "7",
      on_hand_quantity: String(usable + held), usable_quantity: String(usable), excluded_quantity: String(held),
      excluded_quantities: { HELD: String(held), INELIGIBLE: "0", UNKNOWN_ELIGIBILITY: "0", UNKNOWN_EXPIRY: "0", EXPIRED: "0" },
      lots,
    } satisfies Schemas["InventorySnapshot"];
  }));
}

type Latest = Schemas["LatestForecast"] | null;
const LATEST: Schemas["LatestForecast"] = { id: FORECAST, job_id: id(301), planning_ready: true, recorded_at: RECORDED };

function summary({ latest = LATEST as Latest, riverbendMeals = B(40) } = {}) {
  return { observed_at: OBSERVED, inventory: inventory(riverbendMeals), latest_forecast: latest } satisfies Schemas["DashboardSummary"];
}

type Method = { provider: string; fallbackReason: string | null };
const BASELINE: Method = { provider: "SEASONAL_NAIVE", fallbackReason: null };
const FALLBACK: Method = { provider: "MOVING_AVERAGE", fallbackReason: "INSUFFICIENT_DATA" };

/** Physical stock only, as the API projects it: served = min(demand, stock), unmet = demand − served. */
function series(siteId: string, productId: string, demand: number[], start: bigint, method = BASELINE): Schemas["ShortageSeries"] {
  let stock = start;
  const days = demand.map((units, index) => {
    const want = B(units);
    const served = want < stock ? want : stock;
    stock -= served;
    return { day: DAYS[index], demand: String(want), served: String(served), unmet: String(want - served), eligible_end: String(stock) };
  });
  const unit = PRODUCTS.find((product) => product.id === productId)!.base_unit;
  return { site_id: siteId, product_id: productId, base_unit: unit, actual_provider: method.provider, fallback_used: method.fallbackReason !== null, fallback_reason: method.fallbackReason, days };
}

const WARNINGS = ["Physical stock only; confirmed supply lacks expiry declarations", "No proposed transfers or P1 reservations included"];
const steady = (units: number) => DAYS.map(() => units);

function shortages({ riverbendMeals = B(40), pine = FALLBACK, everySite = false } = {}) {
  const start = (siteId: string, productId: string) => usableFor(siteId, productId, riverbendMeals);
  return {
    forecast_run_id: FORECAST,
    observed_at: OBSERVED,
    warnings: WARNINGS,
    series: [
      // Riverbend meals: 55 wanted on day one against 40 usable → Shortfall from Mon, Nov 2.
      series(RIVERBEND, MEAL, [55, 60, 60, 60, 60, 60, 60], start(RIVERBEND, MEAL)),
      // Oak Terrace meals: 120 usable at 50/day → short from Wed, Nov 4 (Watch).
      series(OAK, MEAL, steady(50), start(OAK, MEAL)),
      series(CEDAR, MEAL, steady(20), start(CEDAR, MEAL)),
      // Maple Crossing has no meal series (Not evaluated) unless every site is requested.
      ...(everySite ? [series(MAPLE, MEAL, steady(20), start(MAPLE, MEAL))] : []),
      series(WILLOW, MEAL, steady(20), start(WILLOW, MEAL)),
      // Pine Ridge meals: the primary method had too little history; the moving average filled in.
      series(PINE, MEAL, steady(20), start(PINE, MEAL), pine),
      series(RIVERBEND, WATER, steady(20), start(RIVERBEND, WATER)),
    ],
  } satisfies Schemas["ShortageProjection"];
}

type Reply = { status: number; body: unknown };
const ok = (body: unknown): Reply => ({ status: 200, body });
// The API's message is always the code lower-cased with spaces (apps/api/app/main.py).
const fail = (status: number, code: string): Reply => ({
  status,
  body: { error: { code, message: code.toLowerCase().replaceAll("_", " "), details: {} }, request_id: id(999) } satisfies Schemas["ErrorEnvelope"],
});

async function mockApi(page: Page, replies: { catalog?: Reply; summary?: Reply; shortages?: Reply }) {
  const hits: string[] = [];
  const handle = (key: "catalog" | "summary" | "shortages", fallback: Reply) => async (route: Route) => {
    hits.push(key);
    const reply = replies[key] ?? fallback;
    await route.fulfill({ status: reply.status, contentType: "application/json", body: JSON.stringify(reply.body) });
  };
  await page.route("**/api/v1/forecast-catalog", handle("catalog", ok(catalog)));
  await page.route("**/api/v1/dashboard/summary", handle("summary", ok(summary())));
  await page.route(`**/api/v1/shortages/**`, handle("shortages", ok(shortages())));
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
const chip = (page: Page, shortName: string) => page.getByRole("list", { name: "All sites" }).getByRole("button", { name: new RegExp(`^${shortName}`) });
const sourcePill = (page: Page) => page.locator("[data-overview-source]");
const notice = (page: Page) => page.locator("[data-live-notice]");

async function inspect(page: Page, name: string) {
  await marker(page, name).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Inspect site" }).click();
  const inspector = page.getByTestId("site-inspector");
  await expect(inspector.getByRole("heading", { name })).toBeVisible();
  return inspector;
}

async function textCount(scope: Locator, pattern: RegExp) {
  return scope.evaluate((element, source) => (element.textContent ?? "").match(new RegExp(source, "gi"))?.length ?? 0, pattern.source);
}

/** Notice headline (the <strong>) is plain language; the code, when shown, is small secondary text. */
async function expectNoticeCopy(scope: Locator, headline: string, code?: string) {
  await expect(scope.locator("strong").first()).toHaveText(headline);
  if (code) {
    await expect(scope.locator("[data-notice-code]")).toHaveText(code);
    await expect(scope.locator("strong").first()).not.toContainText(code);
    expect(await scope.textContent()).not.toContain(`${code}:`);
  }
}

for (const [width, height] of [[1440, 900], [390, 844]]) {
  test(`presenter session shows live statuses, units, dates, method and warnings at ${width}x${height}`, async ({ page }, testInfo) => {
    const hits = await mockApi(page, {});
    const pageErrors = await open(page, width, height);
    expect(hits.filter((hit) => hit === "shortages")).toHaveLength(1);

    await expect(page.getByText(FIXTURE_LABEL)).toHaveCount(0);
    await expect(sourcePill(page)).toHaveAttribute("data-overview-source", "live");
    await expect(sourcePill(page).getByText(LIVE_PILL, { exact: true })).toBeVisible();
    await expect(page.getByText(WARNINGS[0])).toBeVisible();
    // The footnote names the full forecast run id and the method per site in plain words.
    const footnote = page.locator("footer").last();
    await expect(footnote).toContainText(FORECAST);
    await expect(footnote).toContainText("Seasonal-naive baseline");
    await expect(footnote).toContainText(/Moving-average baseline, fallback: Pine Ridge/);
    await expect(footnote).toContainText(/No series: Maple Crossing/);

    // Statuses from the shortage days (display-only rules), units from base_unit, dates from the days.
    await expect(marker(page, "Riverbend Pantry")).toHaveAccessibleName(/Shortfall, next deficit Mon, Nov 2: 15 meals unmet/);
    await expect(marker(page, "Oak Terrace Pantry")).toHaveAccessibleName(/Watch, next deficit Wed, Nov 4: 30 meals unmet/);
    await expect(marker(page, "Cedar Grove Pantry")).toHaveAccessibleName(/Covered/);
    await expect(marker(page, "Maple Crossing Pantry")).toHaveAccessibleName(/Not evaluated/);
    await expect(marker(page, "Gator Distribution Hub")).toHaveAccessibleName(/Hub · source, 900 meals eligible now/);
    await expect(page.locator("[data-supply-link]")).toHaveCount(6);
    await expect(page.getByRole("combobox", { name: "Local day" })).toHaveText(/Mon, Nov 2/);

    await expectNoSeriousA11yViolations(page, testInfo, `overview live ${width}x${height}`);
    await page.screenshot({ path: testInfo.outputPath(`overview-live-${width}.png`), fullPage: true });

    const inspector = await inspect(page, "Riverbend Pantry");
    await expect(inspector.getByText(LIVE_PILL, { exact: true })).toBeVisible();
    await expect(inspector).toContainText("Forecast method: Seasonal-naive baseline");
    await expect(inspector).not.toContainText("Fallback forecast");
    await expect(inspector).toContainText("40 meals now → 0 meals by Sun, Nov 8");
    await expect(inspector).toContainText("1 lot · 25 meals");
    await expect(inspector).toContainText("base unit: meal");
    await inspector.getByRole("tab", { name: "Demand" }).click();
    await expect(inspector).toContainText("Donation outlook and confirmed supply: Not in this projection");
    await expect(inspector).toContainText("Projected served");
    await inspector.getByRole("button", { name: "Show data table" }).click();
    await expect(inspector.getByRole("columnheader", { name: "Served (projected, meals)" })).toBeVisible();
    await expect(inspector.getByRole("columnheader", { name: /Donation/ })).toHaveCount(0);
    // Said once in the Demand tab, not repeated in the summary and table caption.
    expect(await textCount(inspector, /not in this projection/)).toBe(1);
    if (width < 1024) await expectNoSeriousA11yViolations(page, testInfo, `overview live ${width}x${height} inspector`);
    expect(pageErrors).toEqual([]);
  });

  test(`visitor (401) sees the labelled static fixture and a sign-in notice at ${width}x${height}`, async ({ page }, testInfo) => {
    const hits = await mockApi(page, { catalog: fail(401, "AUTHENTICATION_REQUIRED"), summary: fail(401, "AUTHENTICATION_REQUIRED") });
    const pageErrors = await open(page, width, height);
    await expect(page.getByText(FIXTURE_LABEL)).toBeVisible();
    await expect(sourcePill(page)).toHaveAttribute("data-overview-source", "fixture");
    await expect(sourcePill(page).getByText(VISITOR_PILL, { exact: true })).toBeVisible();
    await expect(page.getByText("Static fixture", { exact: true })).toHaveCount(0);
    await expect(notice(page)).toHaveAttribute("role", "status");
    await expect(notice(page)).toContainText("Sign in for live data");
    await expect(notice(page).getByRole("link", { name: /optimization workspace/i })).toHaveAttribute("href", "/optimization");
    await expect(page.getByRole("alert").filter({ hasText: "Live data is unavailable" })).toHaveCount(0);
    await expect(page.getByText(LIVE_PILL, { exact: true })).toHaveCount(0);
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
  await expect(notice(page)).toContainText("Sign in for live data");
  await expect(sourcePill(page).getByText(VISITOR_PILL, { exact: true })).toBeVisible();
});

for (const [label, latest] of [["no forecast", null], ["forecast not planning-ready", { ...LATEST, planning_ready: false }]] as const) {
  test(`${label}: live inventory, every beneficiary Not evaluated`, async ({ page }, testInfo) => {
    const hits = await mockApi(page, { summary: ok(summary({ latest })) });
    await open(page);
    expect(hits).not.toContain("shortages");
    await expect(page.getByText(FIXTURE_LABEL)).toHaveCount(0);
    await expect(notice(page)).toHaveAttribute("role", "status");
    await expectNoticeCopy(notice(page), "No planning-ready forecast yet.");
    if (latest) await expect(notice(page)).toContainText(RECORDED_LOCAL);
    await expect(notice(page).getByRole("link", { name: /optimization workspace/i })).toHaveAttribute("href", "/optimization");
    for (const site of BENEFICIARIES) await expect(marker(page, site.name)).toHaveAccessibleName(/Not evaluated/);
    await expectNoSeriousA11yViolations(page, testInfo, `overview ${label} 1440x900`);
    const inspector = await inspect(page, "Riverbend Pantry");
    await expect(inspector).toContainText("40 meals");
  });
}

test("FORECAST_NOT_PLANNING_READY from the shortages read shows the not-ready notice", async ({ page }, testInfo) => {
  await mockApi(page, { shortages: fail(409, "FORECAST_NOT_PLANNING_READY") });
  await open(page);
  await expect(page.getByText(FIXTURE_LABEL)).toHaveCount(0);
  await expect(notice(page)).toHaveAttribute("role", "status");
  await expectNoticeCopy(notice(page), "No planning-ready forecast yet.", "FORECAST_NOT_PLANNING_READY");
  await expect(notice(page)).toContainText(RECORDED_LOCAL);
  await expect(notice(page).getByRole("link", { name: /optimization workspace/i })).toHaveAttribute("href", "/optimization");
  for (const site of BENEFICIARIES) await expect(marker(page, site.name)).toHaveAccessibleName(/Not evaluated/);
  await expectNoSeriousA11yViolations(page, testInfo, "overview not-ready 409 1440x900");
});

const STALE = [
  ["FORECAST_HORIZON_ALREADY_STARTED", "The latest forecast's first day has already passed. Run a new forecast."],
  ["FORECAST_UNIT_OR_CALENDAR_CHANGED", "A site's unit or calendar changed after this forecast."],
  ["FORECAST_NETWORK_SCOPE_CHANGED", "Sites or products changed after this forecast."],
] as const;

for (const [code, headline] of STALE) {
  test(`stale forecast (409 ${code}) keeps live inventory and marks statuses Not evaluated`, async ({ page }, testInfo) => {
    const horizon = code === "FORECAST_HORIZON_ALREADY_STARTED";
    await mockApi(page, { shortages: fail(409, code) });
    await open(page, horizon ? 1280 : 1440, horizon ? 720 : 900);
    await expect(page.getByText(FIXTURE_LABEL)).toHaveCount(0);
    await expect(sourcePill(page).getByText(LIVE_PILL, { exact: true })).toBeVisible();
    await expect(notice(page)).toHaveAttribute("role", "status");
    await expectNoticeCopy(notice(page), headline, code);
    await expect(notice(page)).toContainText(RECORDED_LOCAL);
    await expect(notice(page).getByRole("link", { name: /Run a new forecast/i })).toHaveAttribute("href", "/optimization");
    for (const site of BENEFICIARIES) await expect(marker(page, site.name)).toHaveAccessibleName(/Not evaluated/);
    await expectNoSeriousA11yViolations(page, testInfo, `overview stale ${code}`);
    if (horizon) await page.screenshot({ path: testInfo.outputPath("overview-stale-1280.png"), fullPage: true });
    const inspector = await inspect(page, "Riverbend Pantry");
    await expect(inspector).toContainText("40 meals");
    await expect(inspector).not.toContainText(code);
  });
}

test("FORECAST_INTEGRITY_FAILED shows its own notice and makes no claim about the network", async ({ page }, testInfo) => {
  await mockApi(page, { shortages: fail(409, "FORECAST_INTEGRITY_FAILED") });
  await open(page);
  await expect(page.getByText(FIXTURE_LABEL)).toHaveCount(0);
  const integrity = page.locator('[data-live-notice="integrity"]');
  await expectNoticeCopy(integrity, "The saved forecast failed its integrity check; statuses are not evaluated.", "FORECAST_INTEGRITY_FAILED");
  await expect(integrity).toContainText(RECORDED_LOCAL);
  await expect(integrity).not.toContainText(/network|stale/i);
  await expect(integrity.getByRole("link", { name: /Run a new forecast/i })).toHaveAttribute("href", "/optimization");
  for (const site of BENEFICIARIES) await expect(marker(page, site.name)).toHaveAccessibleName(/Not evaluated/);
  await expectNoSeriousA11yViolations(page, testInfo, "overview integrity 1440x900");
  await page.screenshot({ path: testInfo.outputPath("overview-integrity-1440.png"), fullPage: true });
});

test("DEMAND_FORECAST_UNAVAILABLE explains itself in a full sentence", async ({ page }, testInfo) => {
  await mockApi(page, { shortages: fail(409, "DEMAND_FORECAST_UNAVAILABLE") });
  await open(page);
  await expect(notice(page)).toHaveAttribute("role", "status");
  await expectNoticeCopy(notice(page), "A demand forecast in the latest run is unavailable, so statuses are not evaluated.", "DEMAND_FORECAST_UNAVAILABLE");
  await expect(notice(page)).not.toContainText("demand forecast unavailable");
  await expect(notice(page)).toContainText(RECORDED_LOCAL);
  await expect(marker(page, "Riverbend Pantry")).toHaveAccessibleName(/Not evaluated/);
  await expectNoSeriousA11yViolations(page, testInfo, "overview demand unavailable 1440x900");
  const inspector = await inspect(page, "Riverbend Pantry");
  await expect(inspector).toContainText("A demand forecast in the latest run is unavailable.");
  await expect(inspector).not.toContainText("DEMAND_FORECAST_UNAVAILABLE");
});

for (const [label, reply] of [["an unknown 409", fail(409, "FORECAST_HISTORY_STALE")], ["a 404 from shortages", fail(404, "FORECAST_NOT_FOUND")]] as const) {
  test(`${label} falls back to the fixture with the unavailable alert`, async ({ page }) => {
    await mockApi(page, { shortages: reply });
    await open(page);
    const alert = page.getByRole("alert").filter({ hasText: "Live data is unavailable right now." });
    await expect(alert).toBeVisible();
    await expect(alert.locator("[data-notice-code]")).toHaveText((reply.body as Schemas["ErrorEnvelope"]).error.code);
    await expect(page.getByText(FIXTURE_LABEL)).toBeVisible();
    await expect(sourcePill(page).getByText(UNAVAILABLE_PILL, { exact: true })).toBeVisible();
    await expect(page.locator("[data-live-notice]")).toHaveCount(0);
  });
}

for (const [width, height] of [[1440, 900], [1280, 720], [390, 844]]) {
  test(`503 shows the fixture with a plain unavailable alert at ${width}x${height}; Retry recovers to live`, async ({ page }, testInfo) => {
    const replies: { summary?: Reply } = { summary: fail(503, "BACKEND_NOT_CONFIGURED") };
    await page.route("**/api/v1/forecast-catalog", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(catalog) }));
    await page.route("**/api/v1/dashboard/summary", (route) => {
      const reply = replies.summary ?? ok(summary());
      return route.fulfill({ status: reply.status, contentType: "application/json", body: JSON.stringify(reply.body) });
    });
    await page.route("**/api/v1/shortages/**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(shortages()) }));
    await open(page, width, height);
    const alert = page.getByRole("alert").filter({ hasText: "Live data is unavailable right now." });
    await expect(alert.locator("strong").first()).toHaveText("Live data is unavailable right now.");
    await expect(alert).toContainText("Showing the static design fixture.");
    await expect(alert.locator("[data-notice-code]")).toHaveText("BACKEND_NOT_CONFIGURED");
    // Same type size as the other notices (text-sm).
    expect(await alert.evaluate((element) => getComputedStyle(element).fontSize)).toBe("14px");
    const retry = alert.getByRole("button", { name: "Retry" });
    if (width < 768) expect((await retry.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await expect(page.getByText(FIXTURE_LABEL)).toBeVisible();
    await expect(sourcePill(page)).toHaveAttribute("data-overview-source", "fixture");
    await expect(sourcePill(page).getByText(UNAVAILABLE_PILL, { exact: true })).toBeVisible();
    await expect(page.getByText("Static fixture", { exact: true })).toHaveCount(0);
    if (width !== 1280) await expectNoSeriousA11yViolations(page, testInfo, `overview unavailable ${width}x${height}`);
    await page.screenshot({ path: testInfo.outputPath(`overview-unavailable-${width}.png`), fullPage: true });
    replies.summary = undefined;
    await retry.click();
    await expect(sourcePill(page)).toHaveAttribute("data-overview-source", "live");
    await expect(page.getByText(FIXTURE_LABEL)).toHaveCount(0);
    await expect(page.getByRole("alert").filter({ hasText: "Live data is unavailable" })).toHaveCount(0);
    await expect(marker(page, "Riverbend Pantry")).toHaveAccessibleName(/Shortfall/);
  });
}

test("a network error also falls back to the fixture with the alert", async ({ page }) => {
  await page.route("**/api/v1/forecast-catalog", (route) => route.abort("connectionrefused"));
  await page.route("**/api/v1/dashboard/summary", (route) => route.abort("connectionrefused"));
  await open(page);
  const alert = page.getByRole("alert").filter({ hasText: "Live data is unavailable right now." });
  await expect(alert.locator("[data-notice-code]")).toHaveText("NETWORK_ERROR");
  await expect(page.getByText(FIXTURE_LABEL)).toBeVisible();
});

test("a fallback forecast is named on the site's popover, inspector, marker and chip", async ({ page }, testInfo) => {
  await mockApi(page, {});
  await open(page);
  const fallbackName = /fallback forecast: Moving-average baseline/i;
  await expect(marker(page, "Pine Ridge Pantry")).toHaveAccessibleName(fallbackName);
  await expect(chip(page, "Pine Ridge")).toHaveAccessibleName(fallbackName);
  await expect(marker(page, "Cedar Grove Pantry")).not.toHaveAccessibleName(/fallback/i);
  await expect(chip(page, "Cedar Grove")).not.toHaveAccessibleName(/fallback/i);

  await marker(page, "Pine Ridge Pantry").focus();
  await page.keyboard.press("Enter");
  const card = page.getByRole("dialog", { name: "Pine Ridge Pantry" });
  await expect(card).toContainText("Fallback forecast");
  await expect(card).toContainText("Moving-average baseline");
  await expect(card).toContainText("Too little history for the primary method (INSUFFICIENT_DATA)");
  await page.getByRole("button", { name: "Inspect site" }).click();
  const inspector = page.getByTestId("site-inspector");
  await expect(inspector.getByRole("heading", { name: "Pine Ridge Pantry" })).toBeVisible();
  await expect(inspector).toContainText("Forecast method: Moving-average baseline");
  const note = inspector.locator("[data-fallback-note]");
  await expect(note).toBeVisible();
  await expect(note).toContainText("Fallback forecast");
  await expect(note).toContainText("Too little history for the primary method (INSUFFICIENT_DATA)");
  await expectNoSeriousA11yViolations(page, testInfo, "overview live fallback selected 1440x900");
  await page.screenshot({ path: testInfo.outputPath("overview-live-fallback-1440.png"), fullPage: true });

  // A baseline site carries no fallback note.
  await page.keyboard.press("Escape");
  const cedar = await inspect(page, "Cedar Grove Pantry");
  await expect(cedar).toContainText("Forecast method: Seasonal-naive baseline");
  await expect(cedar.locator("[data-fallback-note]")).toHaveCount(0);
});

test("a uniform method reads 'all sites' and unknown provider names are shown verbatim", async ({ page }) => {
  await mockApi(page, { shortages: ok({ ...shortages({ pine: BASELINE, everySite: true }) }) });
  await open(page);
  const footnote = page.locator("footer").last();
  await expect(footnote).toContainText("Forecast method, all sites: Seasonal-naive baseline");
  await expect(footnote).toContainText(FORECAST);

  const custom = shortages({ pine: { provider: "LOCAL_EXPERIMENT", fallbackReason: null }, everySite: true });
  await page.unroute("**/api/v1/shortages/**");
  await page.route("**/api/v1/shortages/**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(custom) }));
  await page.reload();
  await expect(page.locator("[data-marker-role]")).toHaveCount(7, { timeout: 15_000 });
  const pine = await inspect(page, "Pine Ridge Pantry");
  await expect(pine).toContainText("Forecast method: LOCAL_EXPERIMENT");
  await expect(page.locator("footer").last()).toContainText("LOCAL_EXPERIMENT: Pine Ridge");
});

test("the live served line looks different from the fixture donation line, and the y-axis names the unit", async ({ page, context }) => {
  const lineStyles = async (target: Page) => {
    const inspector = await inspect(target, "Riverbend Pantry");
    await inspector.getByRole("tab", { name: "Demand" }).click();
    const figure = inspector.locator("figure");
    await expect(figure.locator("svg text").filter({ hasText: "meals per day" })).toHaveCount(1);
    return figure.evaluate((element) => ({
      dashes: [...element.querySelectorAll("path.recharts-line-curve")].map((path) => path.getAttribute("stroke-dasharray") ?? "solid"),
      servedMarkers: element.querySelectorAll("[data-chart-marker='served']").length,
    }));
  };
  await mockApi(page, {});
  await open(page);
  const live = await lineStyles(page);
  expect(live.servedMarkers).toBe(7);

  const visitor = await context.newPage();
  await mockApi(visitor, { catalog: fail(401, "AUTHENTICATION_REQUIRED"), summary: fail(401, "AUTHENTICATION_REQUIRED") });
  await open(visitor);
  const fixture = await lineStyles(visitor);
  expect(fixture.servedMarkers).toBe(0);
  // Demand (first line) matches; the second series uses a different dash pattern.
  expect(live.dashes[0]).toBe(fixture.dashes[0]);
  expect(live.dashes[1]).not.toBe(fixture.dashes[1]);
});

test("a quantity beyond Number.MAX_SAFE_INTEGER is shown as unavailable, never rounded", async ({ page }) => {
  const huge = BigInt("9007199254740993");
  await mockApi(page, { summary: ok(summary({ riverbendMeals: huge })), shortages: ok(shortages({ riverbendMeals: huge })) });
  await open(page);
  const inspector = await inspect(page, "Riverbend Pantry");
  // 9007199254740993 − 415 served = 9007199254740578, which is still exactly representable.
  await expect(inspector).toContainText("Unavailable now → 9,007,199,254,740,578 meals by Sun, Nov 8");
  await expect(inspector).not.toContainText("9,007,199,254,740,99");
});

test("connected: a signed-in presenter sees live data from the seeded backend", async ({ page }) => {
  test.skip(process.env.PP_RUN_CONNECTED !== "1", "Requires isolated seeded PostgreSQL, API and Linux worker");
  await page.goto("/overview");
  await page.getByRole("button", { name: "Presenter sign in" }).click();
  await page.getByLabel("Username", { exact: true }).fill(process.env.PP_E2E_USERNAME ?? "presenter");
  await page.getByLabel("Password", { exact: true }).fill(process.env.PP_E2E_PASSWORD ?? "pantry-local-demo");
  await Promise.all([page.waitForEvent("load"), page.getByRole("button", { name: "Sign in", exact: true }).click()]);
  await expect(page.getByText("Presenter session · simulated demo")).toBeVisible();
  await page.goto("/overview");
  await expect(page.locator("[data-overview-source]")).toHaveAttribute("data-overview-source", "live");
  await expect(page.getByText(FIXTURE_LABEL)).toHaveCount(0);
  await expect(page.locator("[data-marker-role]")).not.toHaveCount(0);
});
