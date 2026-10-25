import { expect, test, type Locator, type Page, type Route } from "@playwright/test";
import type { components } from "../../../../packages/contracts/src/schema";
import { expectNoSeriousA11yViolations } from "./a11y";

// Data Explorer (PP-53) over the same-origin /api/v1 proxy. Every test mocks the browser's API
// requests; the connected test at the end needs a seeded backend. Mocks are typed against the
// generated contract and use only values the API emits (integer strings, the error envelope).

type Schemas = components["schemas"];

const BASE = `http://127.0.0.1:${process.env.PLAYWRIGHT_PORT ?? "3000"}`;
const FIXTURE_LABEL = "SIMULATED — static design fixture, not model output";
const LIVE_PILL = "Live · simulated network";
const VISITOR_PILL = "Static fixture · visitor view";
// Mockup-only content (docs/design/reference/data-explorer.md) must never reach the app.
const MOCKUP_ONLY = ["2,340", "89%", "Riverside Community Pantry", "Lakeside Food Hub", "Maple Street Pantry", "Oakridge Pantry", "S-014", "Alex Chen", "4,200", "Midwest", "Northeast", "Equity & Access"];
const WIDTHS = [[1440, 900], [1280, 720], [390, 844]] as const;

const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const HUB = id(1);
const RIVERBEND = id(2), OAK = id(3), CEDAR = id(4), MAPLE = id(5), WILLOW = id(6), PINE = id(7);
const MEAL = id(101), WATER = id(102);
const FORECAST = id(201), JOB = id(301);
const DAYS = ["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06", "2026-11-07", "2026-11-08"];
const TZ = "America/New_York";
const OBSERVED = "2026-11-02T14:30:00Z";
const RECORDED = "2026-11-02T12:05:00Z";
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

// Usable units now per site: [meals, bottles].
const USABLE: Record<string, [bigint, bigint]> = {
  [HUB]: [B(900), B(900)], [RIVERBEND]: [B(40), B(400)], [OAK]: [B(120), B(120)], [CEDAR]: [B(300), B(120)],
  [MAPLE]: [B(300), B(120)], [WILLOW]: [B(300), B(120)], [PINE]: [B(300), B(120)],
};
const usable = (siteId: string, productId: string) => USABLE[siteId][productId === MEAL ? 0 : 1];

let lotCounter = 0;
function lot(quantity: bigint, kind: "eligible" | "held" | "expired"): Schemas["InventoryLotView"] {
  lotCounter += 1;
  const base = { lot_id: id(1000 + lotCounter), batch_key: `B-${lotCounter}`, metadata_version: "1", on_hand_quantity: String(quantity) };
  if (kind === "held") return { ...base, eligibility: "HELD", exclusion_reason: "HELD", expiry_kind: "NON_EXPIRING", expires_on: null, usable: false };
  if (kind === "expired") return { ...base, eligibility: "INELIGIBLE", exclusion_reason: "EXPIRED", expiry_kind: "DATED", expires_on: "2026-10-30", usable: false };
  return { ...base, eligibility: "ELIGIBLE", exclusion_reason: null, expiry_kind: "NON_EXPIRING", expires_on: null, usable: true };
}

function inventory(): Schemas["InventorySnapshot"][] {
  return SITES.flatMap((site) => PRODUCTS.map((product) => {
    const units = usable(site.id, product.id);
    const lots = [lot(units, "eligible")];
    // Riverbend meals: 10 held. Cedar Grove water: 12 expired. Neither is usable.
    if (site.id === RIVERBEND && product.id === MEAL) lots.push(lot(B(10), "held"));
    if (site.id === CEDAR && product.id === WATER) lots.push(lot(B(12), "expired"));
    const held = site.id === RIVERBEND && product.id === MEAL ? B(10) : B(0);
    const expired = site.id === CEDAR && product.id === WATER ? B(12) : B(0);
    return {
      site_id: site.id, site_name: site.name, product_id: product.id, product_name: product.name, base_unit: product.base_unit,
      timezone: TZ, local_date: DAYS[0], observed_at: OBSERVED, inventory_version: "7",
      on_hand_quantity: String(units + held + expired), usable_quantity: String(units), excluded_quantity: String(held + expired),
      excluded_quantities: { HELD: String(held), INELIGIBLE: "0", UNKNOWN_ELIGIBILITY: "0", UNKNOWN_EXPIRY: "0", EXPIRED: String(expired) },
      lots,
    } satisfies Schemas["InventorySnapshot"];
  }));
}

const LATEST: Schemas["LatestForecast"] = { id: FORECAST, job_id: JOB, planning_ready: true, recorded_at: RECORDED };
function summary({ latest = LATEST as Schemas["LatestForecast"] | null, empty = false } = {}) {
  return { observed_at: OBSERVED, inventory: empty ? [] : inventory(), latest_forecast: latest } satisfies Schemas["DashboardSummary"];
}

type Method = { provider: string; fallbackReason: string | null };
const BASELINE: Method = { provider: "SEASONAL_NAIVE", fallbackReason: null };
const FALLBACK: Method = { provider: "MOVING_AVERAGE", fallbackReason: "INSUFFICIENT_DATA" };

/** Physical stock only, as the API projects it: served = min(demand, stock), unmet = demand − served. */
function series(siteId: string, productId: string, demand: number[], method = BASELINE, skipDay?: number): Schemas["ShortageSeries"] {
  let stock = usable(siteId, productId);
  const days = demand.map((units, index) => {
    const want = B(units);
    const served = want < stock ? want : stock;
    stock -= served;
    return { day: DAYS[index], demand: String(want), served: String(served), unmet: String(want - served), eligible_end: String(stock) };
  }).filter((_, index) => index !== skipDay);
  const unit = PRODUCTS.find((product) => product.id === productId)!.base_unit;
  return { site_id: siteId, product_id: productId, base_unit: unit, actual_provider: method.provider, fallback_used: method.fallbackReason !== null, fallback_reason: method.fallbackReason, days };
}
const steady = (units: number) => DAYS.map(() => units);
const WARNINGS = ["Physical stock only; confirmed supply lacks expiry declarations", "No proposed transfers or P1 reservations included"];

function shortages(): Schemas["ShortageProjection"] {
  return {
    forecast_run_id: FORECAST, observed_at: OBSERVED, warnings: WARNINGS,
    series: [
      // Meals. Riverbend: 40 usable vs 55 on day one → Shortfall from Mon, Nov 2 (40 of 415 served).
      series(RIVERBEND, MEAL, [55, 60, 60, 60, 60, 60, 60]),
      // Oak Terrace: 120 usable at 50/day → first deficit Wed, Nov 4 (Watch; 120 of 350 served).
      series(OAK, MEAL, steady(50)),
      // Cedar Grove: an observed zero-demand day on Wed, Nov 4.
      series(CEDAR, MEAL, [20, 20, 0, 20, 20, 20, 20]),
      // Maple Crossing: no meal series (Not evaluated). Willow Creek: Thu, Nov 5 missing from its series.
      series(WILLOW, MEAL, steady(20), BASELINE, 3),
      // Pine Ridge: the primary method had too little history; the moving average filled in.
      series(PINE, MEAL, steady(20), FALLBACK),
      // Water: every beneficiary; Oak Terrace runs 20 short on Sun, Nov 8 (575 of 595 served).
      series(RIVERBEND, WATER, steady(20)), series(OAK, WATER, steady(20)), series(CEDAR, WATER, steady(15)),
      series(MAPLE, WATER, steady(10)), series(WILLOW, WATER, steady(10)), series(PINE, WATER, steady(10)),
    ],
  };
}

function forecastSeries(siteId: string, productId: string, target: "DEMAND" | "DONATION", values: number[], quantiles = false): Schemas["ForecastSeriesResult"] {
  const unit = PRODUCTS.find((product) => product.id === productId)!.base_unit;
  return {
    actual_provider: { name: "SEASONAL_NAIVE", adapter_version: "core-v1" },
    diagnostics: { missing_count: 0, observed_count: 90, proxy_fraction: 0, reference_weekday_count: 12, trailing_sample_count: 14 },
    errors: [], fallback_used: false, fallback_reason: null, generated_at: RECORDED, input_hash: "hash", result_id: id(600 + values.length + (quantiles ? 1 : 0)),
    scope: { calendar_version: "site-local-v1", key: { organization_id: id(900), site_id: siteId, product_id: productId, target_type: target }, required: true, timezone: TZ, unit, unit_version: "base-unit-v1" },
    status: "AVAILABLE", target_basis: target === "DEMAND" ? "REQUESTED" : "RECEIVED", warnings: [],
    points: values.map((value, index) => ({
      day: DAYS[index], central_estimate: value, estimate_kind: quantiles ? "MEDIAN" : "POINT", interval_method: quantiles ? "MODEL_QUANTILES" : "NONE",
      p10: quantiles ? value - 10 : null, p50: quantiles ? value : null, p90: quantiles ? value + 12 : null, postprocessing_policy: "reject-invalid-v1",
    })),
  };
}

function forecastResult(): Schemas["ForecastResult"] {
  return {
    attempt_id: id(310), job_id: JOB, planning_ready: true, published_at: RECORDED,
    forecast: {
      actual_providers: ["SEASONAL_NAIVE", "MOVING_AVERAGE"], completed_at: RECORDED, data_cutoff_date: "2026-11-01", generated_at: RECORDED,
      input_hash: "hash", partial_scope: false, ready_for_publication: true, run_id: FORECAST, schema_version: "forecast-output-experimental-v1", warnings: [],
      series: [
        // Riverbend meals demand carries model quantiles; everything else is point-only.
        forecastSeries(RIVERBEND, MEAL, "DEMAND", [55, 60, 60, 60, 60, 60, 60], true),
        forecastSeries(OAK, MEAL, "DEMAND", steady(50)),
        // Meal donations: 30/day at the hub, 5/day at Riverbend → 35 meals/day across the network. No water donations.
        forecastSeries(HUB, MEAL, "DONATION", steady(30)),
        forecastSeries(RIVERBEND, MEAL, "DONATION", steady(5)),
      ],
    },
  };
}

type Reply = { status: number; body: unknown } | "abort" | "hold";
const ok = (body: unknown): Reply => ({ status: 200, body });
const fail = (status: number, code: string): Reply => ({
  status, body: { error: { code, message: code.toLowerCase().replaceAll("_", " "), details: {} }, request_id: id(999) } satisfies Schemas["ErrorEnvelope"],
});
type Key = "catalog" | "summary" | "shortages" | "forecast";
type Replies = Partial<Record<Key, Reply>>;

/** One handler for every /api/v1 read. `presenter` sets the CSRF cookie and answers the session probe. */
async function mockApi(page: Page, replies: Replies = {}, { presenter = true } = {}) {
  const hits: Key[] = [];
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => { release = resolve; });
  if (presenter) await page.context().addCookies([{ name: "pp_csrf", value: "token", url: BASE }]);
  await page.route("**/api/v1/**", async (route: Route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1/", "");
    if (path === "allocation-methodology") {
      return presenter ? route.fulfill({ status: 200, json: { methods: [], transfer_modes: [], default_transfer_mode: null } }) : route.fulfill({ status: 401, json: (fail(401, "PRESENTER_REQUIRED") as { body: unknown }).body });
    }
    const key: Key | null = path === "forecast-catalog" ? "catalog" : path === "dashboard/summary" ? "summary" : path.startsWith("shortages/") ? "shortages" : path.startsWith("forecasts/") ? "forecast" : null;
    if (!key) return route.fulfill({ status: 404, json: (fail(404, "NOT_FOUND") as { body: unknown }).body });
    hits.push(key);
    const defaults: Record<Key, Reply> = { catalog: ok(catalog), summary: ok(summary()), shortages: ok(shortages()), forecast: ok(forecastResult()) };
    const reply = replies[key] ?? defaults[key];
    if (reply === "abort") return route.abort("connectionrefused");
    if (reply === "hold") { await held; return route.fulfill({ status: 200, json: (defaults[key] as { body: unknown }).body }); }
    await route.fulfill({ status: reply.status, contentType: "application/json", body: JSON.stringify(reply.body) });
  });
  return { hits, release: () => release() };
}

async function open(page: Page, path = "/data", [width, height]: readonly [number, number] = [1440, 900], { waitReady = true } = {}) {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.setViewportSize({ width, height });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(path);
  await expect(page.getByRole("heading", { level: 1, name: "Data Explorer" })).toBeVisible();
  if (waitReady) await expect(page.locator("[data-explorer-source]")).toBeVisible({ timeout: 15_000 });
  return pageErrors;
}

const kpi = (page: Page, name: string) => page.locator(`[data-kpi="${name}"]`);
const notice = (page: Page) => page.locator("[data-explorer-notice]");
const siteRow = (page: Page, name: string) => page.locator("[data-site-row]").filter({ has: page.getByRole("rowheader", { name: new RegExp(`^${name}`) }) });

async function chooseProduct(page: Page, name: RegExp) {
  await page.getByRole("combobox", { name: "Product" }).click();
  await page.getByRole("option", { name }).click();
}

/** Document-relative box: flip assertions must not be fooled by focus-driven scrolling. */
async function box(locator: Locator) {
  return locator.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return { x: rect.x + window.scrollX, y: rect.y + window.scrollY, width: rect.width, height: rect.height };
  });
}

async function expectNoMockupContent(page: Page) {
  const text = (await page.locator("body").textContent()) ?? "";
  for (const item of MOCKUP_ONLY) expect(text, `mockup content "${item}"`).not.toContain(item);
}

// ---------------------------------------------------------------- dashboard at three widths

for (const viewport of WIDTHS) {
  const [width, height] = viewport;
  test(`dashboard shows live KPIs, flips, chart and site table at ${width}x${height}`, async ({ page }, testInfo) => {
    const { hits } = await mockApi(page);
    const pageErrors = await open(page, "/data", viewport);
    expect(hits.filter((hit) => hit === "shortages")).toHaveLength(1);
    await expect(page.locator("[data-explorer-source]")).toHaveAttribute("data-explorer-source", "live");
    await expect(page.getByText(LIVE_PILL, { exact: true }).first()).toBeVisible();
    await expect(page.getByText(FIXTURE_LABEL)).toHaveCount(0);

    // Header: tabs from one config; all five built since PP-56 integration; Data input only for presenters.
    const tabs = page.getByRole("navigation", { name: "Data Explorer views" });
    await expect(tabs.getByRole("link", { name: "Dashboard" })).toHaveAttribute("aria-current", "page");
    await expect(tabs.getByRole("link", { name: "Seven-Day Pulse" })).toHaveAttribute("href", /\/data\/pulse/);
    await expect(tabs.getByRole("link", { name: "Operations Board" })).toHaveAttribute("href", /\/data\/operations/);
    await expect(tabs.getByRole("link", { name: "Inventory & Lots" })).toHaveAttribute("href", /\/data\/inventory/);
    await expect(tabs.getByRole("link", { name: "Data input" })).toHaveAttribute("href", /\/data\/inputs/);
    // Forecast-run chip: id prefix, recorded time and provider.
    const chip = page.locator("[data-run-chip]");
    await expect(chip).toContainText(FORECAST.slice(0, 8));
    await expect(chip).toContainText(RECORDED_LOCAL);
    await expect(chip).toContainText("Seasonal-naive baseline");

    // Exactly four KPI cards.
    await expect(page.locator("[data-kpi]")).toHaveCount(4);
    await expect(kpi(page, "households")).toContainText("Unavailable");
    await expect(kpi(page, "households")).toContainText("household data not supplied");
    await expect(kpi(page, "fill-rate")).toContainText("41%");
    await expect(kpi(page, "fill-rate")).toContainText("420 of 1,025 meals");
    await expect(kpi(page, "fill-rate")).toContainText("4 of 6 beneficiaries");
    await expect(kpi(page, "waste")).toContainText("Unavailable — waste accounting not supplied");
    await expect(kpi(page, "waste")).toContainText("12 bottles");
    await expect(kpi(page, "waste")).toContainText("0 meals");
    await expect(kpi(page, "risk").getByRole("heading", { name: "Items at Risk" })).toBeVisible();
    await expect(kpi(page, "risk")).toContainText("of 2 products");

    // Chart: units on the axis, provider named, data table alternative with seven days.
    const chart = page.locator('[data-chart="network-demand"]');
    await expect(chart.locator("svg text").filter({ hasText: "meals per day" })).toHaveCount(1);
    await expect(chart).toContainText("History not available from the API");
    await expect(chart.locator("[data-band]")).toHaveCount(0);
    await chart.getByRole("button", { name: "Show data table" }).click();
    const dataTable = chart.getByRole("table");
    await expect(dataTable.locator("tbody tr")).toHaveCount(7);
    await expect(dataTable.locator("tbody tr").first()).toContainText("165");
    await expect(dataTable.locator("tbody tr").first()).toContainText("35");
    await expect(dataTable.locator("tbody tr").nth(3)).toContainText("Missing");

    // Site table: six beneficiaries plus the hub, labelled as a source.
    await expect(page.locator('[data-site-row][data-role="BENEFICIARY"]')).toHaveCount(6);
    await expect(page.locator('[data-site-row][data-role="HUB"]')).toContainText("Hub · source");
    await expect(siteRow(page, "Riverbend Pantry")).toContainText("Shortfall");
    await expect(siteRow(page, "Riverbend Pantry")).toContainText("10%");
    await expect(siteRow(page, "Riverbend Pantry")).toContainText("40 / 415 meals");
    await expect(siteRow(page, "Riverbend Pantry")).toContainText("375 meals");
    await expect(siteRow(page, "Oak Terrace Pantry")).toContainText("Watch");
    await expect(siteRow(page, "Oak Terrace Pantry")).toContainText("Wed, Nov 4");
    await expect(siteRow(page, "Maple Crossing Pantry")).toContainText("Not evaluated");
    await expect(siteRow(page, "Willow Creek Pantry")).toContainText("Not evaluated");
    await expect(siteRow(page, "Willow Creek Pantry")).not.toContainText("Covered");
    await expect(siteRow(page, "Pine Ridge Pantry")).toContainText(/fallback/i);
    await expect(page.locator("[data-site-table]")).toContainText(/Region and households are not in the data/);

    await expectNoMockupContent(page);
    await expectNoSeriousA11yViolations(page, testInfo, `data explorer dashboard ${width}x${height}`);
    await page.screenshot({ path: testInfo.outputPath(`data-explorer-dashboard-${width}.png`), fullPage: true });

    // Risk flip: independent, focus moves to the new face, hidden face inert, no layout shift.
    const chartBox = await box(chart);
    const tableBox = await box(page.locator("[data-site-table]"));
    const analyticsBox = await box(page.locator('[data-flip="analytics"]'));
    await kpi(page, "risk").getByRole("button", { name: "Show Sites at Risk" }).click();
    await expect(kpi(page, "risk").getByRole("heading", { name: "Sites at Risk" })).toBeFocused();
    await expect(kpi(page, "risk")).toContainText("of 6 beneficiaries");
    await expect(kpi(page, "risk")).toContainText("2 not evaluated");
    await expect(kpi(page, "risk").locator("[aria-live=polite]")).toHaveText("Showing Sites at Risk");
    expect(await kpi(page, "risk").locator('[data-face="front"]').evaluate((element) => (element as HTMLElement).inert)).toBe(true);
    await expect(kpi(page, "risk").locator('[data-face="front"]')).toHaveAttribute("aria-hidden", "true");
    await expect(page.locator('[data-flip="analytics"]').getByRole("heading", { name: "Fill Rate by Region" })).toBeVisible();

    // Analytics flip: per-site fallback on the front, two product rows on the back.
    const analytics = page.locator('[data-flip="analytics"]');
    await expect(analytics).toContainText("Regional grouping unavailable");
    await expect(analytics).toContainText("By site (no regions)");
    await analytics.getByRole("button", { name: "Show Item Risk Overview" }).click();
    await expect(analytics.getByRole("heading", { name: "Item Risk Overview" })).toBeFocused();
    await expect(analytics.locator("[data-item-row]")).toHaveCount(2);
    await expect(analytics.locator("[data-item-row]").filter({ hasText: "Shelf-stable meals" })).toContainText("Mon, Nov 2");
    await expect(analytics.locator("[data-item-row]").filter({ hasText: "Bottled water" })).toContainText("Sun, Nov 8");
    await expect(analytics).toContainText(/display sort/i);
    expect(await analytics.locator('[data-face="front"]').evaluate((element) => (element as HTMLElement).inert)).toBe(true);
    // Risk card kept its own face.
    await expect(kpi(page, "risk").getByRole("heading", { name: "Sites at Risk" })).toBeVisible();
    expect(await box(chart)).toEqual(chartBox);
    expect(await box(page.locator("[data-site-table]"))).toEqual(tableBox);
    expect(await box(analytics)).toEqual(analyticsBox);
    await expectNoSeriousA11yViolations(page, testInfo, `data explorer flipped ${width}x${height}`);
    if (width === 1440) await page.screenshot({ path: testInfo.outputPath(`data-explorer-flipped-${width}.png`), fullPage: true });

    // Product switch changes units everywhere; quantities never combine meals and bottles.
    await chooseProduct(page, /Bottled water/);
    await expect(chart.locator("svg text").filter({ hasText: "bottles per day" })).toHaveCount(1);
    await expect(kpi(page, "fill-rate")).toContainText("97%");
    await expect(kpi(page, "fill-rate")).toContainText("575 of 595 bottles");
    await expect(siteRow(page, "Oak Terrace Pantry")).toContainText("Sun, Nov 8");
    await expect(chart).toContainText("No donation forecast for this product");
    expect(pageErrors).toEqual([]);
  });
}

// ---------------------------------------------------------------- subviews at three widths

for (const viewport of WIDTHS) {
  const [width, height] = viewport;
  test(`Seven-Day Pulse shows 6×7 cells with distinct missing, not evaluated and zero at ${width}x${height}`, async ({ page }, testInfo) => {
    await mockApi(page);
    const pageErrors = await open(page, "/data/pulse", viewport);
    await expect(page.getByRole("navigation", { name: "Data Explorer views" }).getByRole("link", { name: "Seven-Day Pulse" })).toHaveAttribute("aria-current", "page");
    await expect(page.locator("[data-pulse-cell]")).toHaveCount(42);
    const cell = (site: string, day: string) => page.getByRole("button", { name: new RegExp(`^${site}, ${day}`) });
    await expect(cell("Riverbend Pantry", "Mon, Nov 2")).toHaveAttribute("data-cell-state", "shortfall");
    await expect(cell("Cedar Grove Pantry", "Wed, Nov 4")).toHaveAttribute("data-cell-state", "zero");
    await expect(cell("Willow Creek Pantry", "Thu, Nov 5")).toHaveAttribute("data-cell-state", "missing");
    await expect(cell("Maple Crossing Pantry", "Mon, Nov 2")).toHaveAttribute("data-cell-state", "not_evaluated");
    await expect(cell("Willow Creek Pantry", "Thu, Nov 5")).toContainText("Missing");
    await expect(cell("Maple Crossing Pantry", "Mon, Nov 2")).toContainText("Not evaluated");
    await expect(cell("Cedar Grove Pantry", "Wed, Nov 4")).toContainText("0");

    await cell("Riverbend Pantry", "Mon, Nov 2").click();
    const detail = page.locator("[data-pulse-detail]");
    await expect(detail).toContainText("Riverbend Pantry");
    await expect(detail).toContainText("55 meals");
    await expect(detail).toContainText("40 meals");
    await expect(detail).toContainText("15 meals");
    await cell("Willow Creek Pantry", "Thu, Nov 5").click();
    await expect(detail).toContainText("Missing from the projection");
    await expect(detail).not.toContainText("0 meals");
    await expectNoMockupContent(page);
    await expectNoSeriousA11yViolations(page, testInfo, `data explorer pulse ${width}x${height}`);
    await page.screenshot({ path: testInfo.outputPath(`data-explorer-pulse-${width}.png`), fullPage: true });
    expect(pageErrors).toEqual([]);
  });

  test(`Operations Board covers six sites × two products with lot status at ${width}x${height}`, async ({ page }, testInfo) => {
    await mockApi(page);
    const pageErrors = await open(page, "/data/operations", viewport);
    await expect(page.locator('[data-site-card][data-role="BENEFICIARY"]')).toHaveCount(6);
    for (const site of BENEFICIARIES) {
      const card = page.locator("[data-site-card]").filter({ has: page.getByRole("heading", { name: site.name }) });
      await expect(card.locator("[data-product-panel]")).toHaveCount(2);
      await expect(card).toContainText("meals");
      await expect(card).toContainText("bottles");
    }
    const riverbend = page.locator("[data-site-card]").filter({ has: page.getByRole("heading", { name: "Riverbend Pantry" }) });
    await expect(riverbend.locator('[data-product-panel]').filter({ hasText: "Shelf-stable meals" })).toContainText("Held: 1 lot · 10 meals");
    await expect(riverbend.locator('[data-product-panel]').filter({ hasText: "Shelf-stable meals" })).toContainText("Mon, Nov 2");
    const cedar = page.locator("[data-site-card]").filter({ has: page.getByRole("heading", { name: "Cedar Grove Pantry" }) });
    await expect(cedar.locator('[data-product-panel]').filter({ hasText: "Bottled water" })).toContainText("Expired: 1 lot · 12 bottles");
    await expect(page.locator('[data-site-card][data-role="HUB"]')).toContainText("Hub · source");
    await expect(page.getByRole("link", { name: "Inventory & Lots" }).first()).toBeVisible();
    await expectNoSeriousA11yViolations(page, testInfo, `data explorer operations ${width}x${height}`);
    await page.screenshot({ path: testInfo.outputPath(`data-explorer-operations-${width}.png`), fullPage: true });
    expect(pageErrors).toEqual([]);
  });
}

// ---------------------------------------------------------------- honest states

test("visitor (401) sees the labelled SIMULATED fixture, a sign-in notice and no Data input tab", async ({ page }, testInfo) => {
  const { hits } = await mockApi(page, { catalog: fail(401, "PRESENTER_REQUIRED"), summary: fail(401, "PRESENTER_REQUIRED") }, { presenter: false });
  await open(page);
  await expect(page.locator("[data-explorer-source]")).toHaveAttribute("data-explorer-source", "fixture");
  await expect(page.getByText(FIXTURE_LABEL).first()).toBeVisible();
  await expect(page.getByText(VISITOR_PILL, { exact: true })).toBeVisible();
  await expect(notice(page)).toContainText("Sign in for live data");
  await expect(page.getByText(LIVE_PILL, { exact: true })).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: "Data Explorer views" }).getByText(/Data input/)).toHaveCount(0);
  await expect(page.locator("[data-kpi]")).toHaveCount(4);
  await expect(page.locator('[data-site-row][data-role="BENEFICIARY"]')).toHaveCount(6);
  expect(hits).not.toContain("shortages");
  expect(hits).not.toContain("forecast");
  await expectNoMockupContent(page);
  await expectNoSeriousA11yViolations(page, testInfo, "data explorer visitor 1440x900");
  await page.screenshot({ path: testInfo.outputPath("data-explorer-visitor-1440.png"), fullPage: true });
});

test("visitor read access: live reads load; a 401 on the donation forecast only marks donations unavailable", async ({ page }) => {
  await mockApi(page, { forecast: fail(401, "PRESENTER_REQUIRED") }, { presenter: false });
  await open(page);
  await expect(page.locator("[data-explorer-source]")).toHaveAttribute("data-explorer-source", "live");
  await expect(page.getByText(FIXTURE_LABEL)).toHaveCount(0);
  await expect(page.locator('[data-chart="network-demand"]')).toContainText("Donation outlook unavailable for visitors");
  await expect(kpi(page, "fill-rate")).toContainText("41%");
});

test("no forecast: live inventory stays, projections are Not evaluated", async ({ page }, testInfo) => {
  const { hits } = await mockApi(page, { summary: ok(summary({ latest: null })) });
  await open(page);
  expect(hits).not.toContain("shortages");
  await expect(notice(page)).toHaveAttribute("data-explorer-notice", "not_ready");
  await expect(notice(page)).toContainText("No planning-ready forecast yet.");
  await expect(kpi(page, "fill-rate")).toContainText("Not evaluated");
  await expect(kpi(page, "waste")).toContainText("12 bottles");
  await expect(page.locator('[data-site-row][data-role="HUB"]')).toContainText("900 meals");
  for (const site of BENEFICIARIES) await expect(siteRow(page, site.name)).toContainText("Not evaluated");
  await expectNoSeriousA11yViolations(page, testInfo, "data explorer no forecast 1440x900");
});

const NOTICE_409 = [
  ["FORECAST_NOT_PLANNING_READY", "not_ready", "No planning-ready forecast yet."],
  ["FORECAST_HORIZON_ALREADY_STARTED", "stale", "The latest forecast's first day has already passed. Run a new forecast."],
  ["FORECAST_UNIT_OR_CALENDAR_CHANGED", "stale", "A site's unit or calendar changed after this forecast."],
  ["FORECAST_NETWORK_SCOPE_CHANGED", "stale", "Sites or products changed after this forecast."],
  ["FORECAST_INTEGRITY_FAILED", "integrity", "The saved forecast failed its integrity check; statuses are not evaluated."],
  ["DEMAND_FORECAST_UNAVAILABLE", "demand_unavailable", "A demand forecast in the latest run is unavailable, so statuses are not evaluated."],
] as const;

for (const [code, kind, headline] of NOTICE_409) {
  test(`409 ${code} shows its notice and keeps live inventory`, async ({ page }) => {
    await mockApi(page, { shortages: fail(409, code) });
    await open(page);
    await expect(notice(page)).toHaveAttribute("data-explorer-notice", kind);
    await expect(notice(page).locator("strong").first()).toHaveText(headline);
    await expect(notice(page).locator("[data-notice-code]")).toHaveText(code);
    await expect(notice(page)).toContainText(RECORDED_LOCAL);
    await expect(page.getByText(FIXTURE_LABEL)).toHaveCount(0);
    await expect(kpi(page, "waste")).toContainText("12 bottles");
    await expect(kpi(page, "fill-rate")).toContainText("Not evaluated");
    await expect(siteRow(page, "Riverbend Pantry")).toContainText("Not evaluated");
  });
}

test("a fallback forecast names the actual provider and the fallback reason", async ({ page }) => {
  await mockApi(page);
  await open(page);
  const pill = page.locator("[data-fallback-pill]");
  await expect(pill).toContainText("Fallback forecast");
  await expect(pill).toContainText("Moving-average baseline");
  await expect(pill).toContainText("Too little history for the primary method (INSUFFICIENT_DATA)");
  await expect(pill).toContainText("Pine Ridge");
});

test("an uncertainty band appears only for one site with model quantiles", async ({ page }) => {
  await mockApi(page);
  await open(page);
  const chart = page.locator('[data-chart="network-demand"]');
  await expect(chart.locator("[data-band]")).toHaveCount(0);
  await expect(chart).toContainText(/quantiles do not add across sites/i);
  await chart.getByRole("combobox", { name: "Chart scope" }).click();
  await page.getByRole("option", { name: "Riverbend Pantry" }).click();
  await expect(chart.locator("[data-band]")).toHaveCount(1);
  await expect(chart).toContainText("p10–p90 model quantiles, not a calibrated interval");
  await chart.getByRole("combobox", { name: "Chart scope" }).click();
  await page.getByRole("option", { name: "Oak Terrace Pantry" }).click();
  await expect(chart.locator("[data-band]")).toHaveCount(0);
  await expect(chart).toContainText("Point forecast only; no interval");
});

test("a network failure shows an alert with Retry and no data; Retry recovers to live", async ({ page }, testInfo) => {
  const replies: Replies = { summary: "abort" };
  await mockApi(page, replies);
  await open(page, "/data", [1440, 900], { waitReady: false });
  const alert = page.getByRole("alert").filter({ hasText: "Data Explorer could not load" });
  await expect(alert).toBeVisible({ timeout: 15_000 });
  await expect(alert.locator("[data-notice-code]")).toHaveText("NETWORK_ERROR");
  await expect(page.getByText(FIXTURE_LABEL)).toHaveCount(0);
  await expect(page.locator("[data-kpi]")).toHaveCount(0);
  await expectNoSeriousA11yViolations(page, testInfo, "data explorer network failure 1440x900");
  delete replies.summary;
  await alert.getByRole("button", { name: "Retry" }).click();
  await expect(page.locator("[data-explorer-source]")).toHaveAttribute("data-explorer-source", "live");
  await expect(kpi(page, "fill-rate")).toContainText("41%");
});

test("empty inventory says so instead of showing zero", async ({ page }) => {
  await mockApi(page, { summary: ok(summary({ empty: true })) });
  await open(page);
  await expect(page.locator('[data-explorer-notice="empty_inventory"]')).toContainText("No inventory rows in this snapshot");
  await expect(kpi(page, "waste")).not.toContainText("0 meals");
  await expect(page.locator('[data-site-row][data-role="HUB"]')).toContainText("No inventory row");
});

test("loading shows stable skeletons with both flips disabled", async ({ page }) => {
  const { release } = await mockApi(page, { summary: "hold" });
  await open(page, "/data", [1440, 900], { waitReady: false });
  await expect(page.locator("[data-loading-slot]").first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("button", { name: "Show Sites at Risk" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Show Item Risk Overview" })).toBeDisabled();
  release();
  await expect(page.locator("[data-explorer-source]")).toHaveAttribute("data-explorer-source", "live", { timeout: 15_000 });
  await expect(page.locator("[data-loading-slot]")).toHaveCount(0);
});

test("connected: a signed-in presenter reads the live dashboard from the seeded backend", async ({ page }) => {
  test.skip(process.env.PP_RUN_CONNECTED !== "1", "Requires isolated seeded PostgreSQL, API and Linux worker");
  await page.goto("/overview");
  const footer = page.getByRole("button", { name: "Presenter sign in" });
  if (!(await footer.isVisible())) await page.getByRole("button", { name: "Open navigation" }).click();
  await footer.click();
  const dialog = page.getByRole("dialog", { name: "Presenter sign in" });
  await dialog.getByLabel("Username").fill(process.env.PP_E2E_USERNAME ?? "presenter");
  await dialog.getByLabel("Password").fill(process.env.PP_E2E_PASSWORD ?? "pantry-local-demo");
  await Promise.all([page.waitForEvent("load"), dialog.getByRole("button", { name: "Sign in", exact: true }).click()]);
  await page.goto("/data");
  await expect(page.locator("[data-explorer-source]")).toHaveAttribute("data-explorer-source", "live", { timeout: 30_000 });
  await expect(page.getByText(FIXTURE_LABEL)).toHaveCount(0);
  await expect(page.locator("[data-kpi]")).toHaveCount(4);
  await expect(page.locator('[data-site-row][data-role="BENEFICIARY"]')).toHaveCount(6);
});
