import { expect, test, type Page, type Route } from "@playwright/test";
import type { components } from "../../../../packages/contracts/src/schema";
import { expectNoSeriousA11yViolations } from "./a11y";

// Scenario Lab (PP-55) against a mocked same-origin API. Every fixture is typed against the generated
// contract; names and numbers are fictional and deliberately differ from the design mockup.

type Schemas = components["schemas"];
type State = Schemas["AttemptState"];

const BASE = `http://127.0.0.1:${process.env.PLAYWRIGHT_PORT ?? "3000"}`;
const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const HUB = id(1);
const HARBOR = id(2), LAKESIDE = id(3), MILL = id(4), ORCHARD = id(5), QUARRY = id(6), STATION = id(7);
const MEAL = id(101), WATER = id(102);
const FORECAST = id(201), ASSUMPTIONS = id(211), SCENARIO = id(221), OLD_SCENARIO = id(222);
const JOB = id(301), OLD_JOB = id(302), RETRY_JOB = id(303);
const SOURCE = id(401);
const ORG = id(501);
const TZ = "America/New_York";
const REVISION = "a".repeat(64);
const OP_HASH = "b".repeat(64);
const POLICY_HASH = "c".repeat(64);
const FIRST_DAY = "2026-11-03";

const SITES = [
  { id: HUB, name: "Central Hub", role: "HUB", timezone: TZ },
  { id: HARBOR, name: "Harbor Pantry", role: "BENEFICIARY", timezone: TZ },
  { id: LAKESIDE, name: "Lakeside Pantry", role: "BENEFICIARY", timezone: TZ },
  { id: MILL, name: "Mill Street Pantry", role: "BENEFICIARY", timezone: TZ },
  { id: ORCHARD, name: "Orchard Pantry", role: "BENEFICIARY", timezone: TZ },
  { id: QUARRY, name: "Quarry Pantry", role: "BENEFICIARY", timezone: TZ },
  { id: STATION, name: "Station Pantry", role: "BENEFICIARY", timezone: TZ },
] satisfies Schemas["SiteSummary"][];
const BENEFICIARIES = SITES.filter((s) => s.role === "BENEFICIARY");
const PRODUCTS = [{ id: MEAL, name: "Shelf-stable meals", base_unit: "meal" }, { id: WATER, name: "Bottled water", base_unit: "bottle" }] satisfies Schemas["ProductSummary"][];
const MOCKUP_ONLY = ["S-014", "86%", "2.6M", "$1.1M", "Equity Score", "Alex Chen", "Riverbend", "Maple Crossing"];

const network = { sites: SITES, products: PRODUCTS, sources: [{ id: SOURCE, name: "fictional-demo-history", classification: "SIMULATED" }] } satisfies Schemas["ForecastCatalog"];

const methodology = {
  methods: ["CLASSICAL_GP", "EGP_PI_INSPIRED"], transfer_modes: ["HUB_ONLY", "HUB_AND_PANTRY"], default_transfer_mode: null,
  decision_ids: [], expiry: "FEFO", search_seconds: { default: 120, maximum: 300 }, donor_protection_days: 3,
  planning_window_days: [1, 2, 3], stock_effect: "NONE_SIMULATION_ONLY", limitations: ["Vulnerability attributes are simulated."],
};

const catalog = (extra: Partial<Schemas["PlanningCatalog"]> = {}) => ({
  assumptions: [{ id: ASSUMPTIONS, label: "Simulated research preset", recorded_at: "2026-11-02T12:00:00Z" }],
  forecasts: [{ id: FORECAST, label: "d".repeat(64), recorded_at: "2026-11-02T12:05:00Z" }],
  scenarios: [], comparisons: [], next_before: null, next_before_id: null, source_revision: REVISION, ...extra,
}) satisfies Schemas["PlanningCatalog"];

const residual = (original: number) => ({ fixed_used: 0, original, residual: original, source_revision: "r1" }) satisfies Schemas["ResidualCapacity"];
const policy = {
  ap_cap_bp: 5000, ap_threshold: 3000, beta_percent: 50, coefficients: [], decision_ids: [], epsilon_cost_bp: 10, epsilon_waste_bp: 10,
  gamma_ap_percent: 50, gamma_rp_percent: 50, lambda_percent: 100, purpose: "PRIMARY", rp_cap_bp: 5000, rp_threshold: 1000,
  schema_version: "or-policy-v1", version: "simulated-policy-v1",
} satisfies Schemas["ORPolicy"];
const assumptionsPayload = {
  capacities: { cost_budget_minor: null, global_handling: residual(1000), sites: [] }, classification: "SIMULATED", handling: [],
  policy, reserves: [], routes: [], schema_version: "planning-assumptions-v1", vulnerability_attributes: [],
} satisfies Schemas["AssumptionsPayload"];
const assumptions = { id: ASSUMPTIONS, name: "Simulated research preset", parent_id: null, content_hash: "e".repeat(64), recorded_at: "2026-11-02T12:00:00Z", payload: assumptionsPayload } satisfies Schemas["AssumptionsResult"];

function scenario(identity = SCENARIO, mode: Schemas["TransferMode"] = "HUB_AND_PANTRY", recorded = "2026-11-02T13:00:00Z"): Schemas["ScenarioResult"] {
  return {
    id: identity, parent_id: null, forecast_run_id: FORECAST, assumptions_id: ASSUMPTIONS, recorded_at: recorded, stale: false, historical: false,
    payload: {
      cost_reference: 100, decision_ids: [], demand: [], intent: "CURRENT", loading_order: [], modifiers: [], operational_hash: OP_HASH,
      planning_days: 2, policy, policy_hash: POLICY_HASH, schema_version: "or-scenario-v2", transfer_mode: mode, waste_references: [],
      package: {
        capacities: assumptionsPayload.capacities, confirmed_arrivals: [], dataset_id: id(601), decision_ids: [], first_planning_date: FIRST_DAY,
        forecasts: BENEFICIARIES.flatMap((site) => PRODUCTS.map((product, n) => ({
          actual_provider: "SEASONAL_NAIVE", basis: "REQUESTED", committed: true, cutoff: "2026-11-02", days: [], estimate_kind: "POINT",
          generated_at: "2026-11-02T12:05:00Z", id: id(700 + n), interval_method: "NONE", numeric_conversion: "EXACT_LITERAL", organization_id: ORG,
          planning_ready: true, product_id: product.id, run_id: FORECAST, site_id: site.id, source_classification: "SIMULATED", source_id: SOURCE,
          source_revision: "s1", timezone: TZ, unit: product.base_unit,
        } satisfies Schemas["ForecastSeries"]))),
        inventory: [], operational_timezone: TZ, organization_id: ORG,
        products: PRODUCTS.map((p) => ({ id: p.id, unit: p.base_unit, handling_coefficient: 1, source_revision: "p1" })),
        provenance_warnings: ["Fictional simulated network."], reserves: [], routes: [], schema_version: "or-input-v2",
        sites: SITES.map((s) => ({ id: s.id, name: s.name, role: s.role, organization_id: ORG, timezone: TZ, source_revision: "s1" })),
        snapshot_as_of: "2026-11-02T13:00:00Z",
        source_coverage: { excluded_series: [], forecast_handoff_hash: null, partial_scope: false, required_complete: true },
        source_kind: "SIMULATED", source_manifest_hash: "f".repeat(64), source_refs: [], source_revision_token: REVISION, vulnerability_attributes: [],
      },
    },
  };
}

const r = (numerator: number, denominator = 1) => ({ numerator, denominator });
// [site, product, target, fulfilled, ap, rp]. Quarry water has a zero target (service ratio null → N/A).
type Row = [string, string, number, number, boolean, boolean];
const BASELINE_ROWS: Row[] = [
  [HARBOR, MEAL, 40, 40, false, false], [HARBOR, WATER, 30, 30, false, false],
  [LAKESIDE, MEAL, 60, 20, true, true], [LAKESIDE, WATER, 24, 24, false, false],
  [MILL, MEAL, 80, 50, true, false], [MILL, WATER, 18, 18, false, false],
  [ORCHARD, MEAL, 35, 35, false, false], [ORCHARD, WATER, 22, 22, false, false],
  [QUARRY, MEAL, 28, 28, false, false], [QUARRY, WATER, 0, 0, false, false],
  [STATION, MEAL, 45, 45, false, false], [STATION, WATER, 26, 26, false, false],
];
// Classical serves Mill Street fully; EGP-PI-inspired moves part of that to Lakeside (AP cleared there).
const CLASSICAL_ROWS: Row[] = BASELINE_ROWS.map((row) => row[0] === MILL && row[1] === MEAL ? [MILL, MEAL, 80, 80, false, false]
  : row[0] === LAKESIDE && row[1] === MEAL ? [LAKESIDE, MEAL, 60, 30, true, true] : row);
const EGP_ROWS: Row[] = BASELINE_ROWS.map((row) => row[0] === MILL && row[1] === MEAL ? [MILL, MEAL, 80, 65, false, false]
  : row[0] === LAKESIDE && row[1] === MEAL ? [LAKESIDE, MEAL, 60, 45, false, false] : row);

function metrics(rows: Row[], cost: number, waste: number): Schemas["Metrics"] {
  const goals = rows.map(([site, product, target, fulfilled, ap, rp]) => ({
    site_id: site, product_id: product, target, fulfilled, unmet: target - fulfilled, ap, rp, exact_ap: ap, exact_rp: rp, q: 1, q0: 1,
    service_ratio: target === 0 ? null : r(fulfilled, target), deficit: r(target - fulfilled, Math.max(target, 1)),
    vulnerability: r(site === LAKESIDE ? 3 : 1, 2), weighted_deficit: r((target - fulfilled) * (site === LAKESIDE ? 3 : 1), Math.max(target, 1) * 2),
  })) satisfies Schemas["GoalMetric"][];
  const groups = PRODUCTS.map((p) => ({
    product_id: p.id, size: goals.filter((g) => g.product_id === p.id && g.target > 0).length,
    ap_count: goals.filter((g) => g.product_id === p.id && g.ap).length, rp_count: goals.filter((g) => g.product_id === p.id && g.rp).length,
    ap_excess_numerator: 0, rp_excess_numerator: 0,
  })) satisfies Schemas["GroupMetric"][];
  return { W: r(1), W0: r(1), Z: r(1), Z0: r(1), ap_excess: r(0), classical_objective: r(7, 3), research_objective: r(5, 3), rp_excess: r(0),
    cost_minor: cost, goals, groups, q_cost: 1, q_waste_by_product: [], warnings: [], waste_by_product: [[MEAL, waste], [WATER, 0]] };
}

const assignment = (destination: string, units: number, lot: number) => ({
  arrival: "2026-11-03", departure: "2026-11-03", cost_minor: units, destination_id: destination, expires_on: "2026-11-20",
  original_lot_id: id(900 + lot), product_id: MEAL, route_id: id(800 + lot), source_id: HUB, source_revision: "l1", unit: "meal", units,
}) satisfies Schemas["TransferAssignment"];

function method(kind: Schemas["AllocationMethod"], opts: { failed?: string; nativeStatus?: string } = {}): Schemas["MethodOutcome"] {
  const rows = kind === "CLASSICAL_GP" ? CLASSICAL_ROWS : EGP_ROWS;
  const assignments = kind === "CLASSICAL_GP" ? [assignment(MILL, 30, 1), assignment(LAKESIDE, 10, 2)] : [assignment(MILL, 15, 1), assignment(LAKESIDE, 25, 2)];
  const verified = !opts.failed;
  return {
    method: kind, outcome: verified ? "VERIFIED" : "FAILED", error_code: opts.failed ?? null, native_status: verified ? (opts.nativeStatus ?? "OPTIMAL") : null,
    candidate: verified ? { assignments, route_quantities: [] } : null, decision_ids: [], gap: verified ? 0 : null, historical: false,
    native_bound: verified ? 1.5 : null, objective: verified ? r(3, 2) : null, operational_hash: OP_HASH, policy_hash: POLICY_HASH,
    schema_version: "or-method-result-v2", search_seconds: 4.2, total_seconds: 5.1, settings_hash: "9".repeat(64), transfer_mode: "HUB_AND_PANTRY",
    termination_reason: verified ? "OPTIMAL" : null, warnings: [],
    verification: verified ? { candidate_hash: "8".repeat(64), metrics: metrics(rows, kind === "CLASSICAL_GP" ? 640 : 655, kind === "CLASSICAL_GP" ? 3 : 2),
      operational_hash: OP_HASH, passed: true, projection: null, schema_version: "or-verification-v2", verifier_version: "independent-replay-v2", violations: [] } : null,
  };
}

function comparison(identity = JOB, opts: { partial?: boolean; recorded?: string; scenarioId?: string } = {}): Schemas["SavedComparison"] {
  return {
    id: identity, scenario_id: opts.scenarioId ?? SCENARIO, recorded_at: opts.recorded ?? "2026-11-02T13:10:00Z", stale: false, historical: false,
    settings: { search_milliseconds: 120000 },
    result: {
      baseline_metrics: metrics(BASELINE_ROWS, 0, 4), common_differences: { changed_routes: 2, shared_feasible_region: "IDENTICAL" }, historical: false,
      methods: [method("CLASSICAL_GP"), method("EGP_PI_INSPIRED", opts.partial ? { failed: "SOLVER_TIMEOUT" } : {})],
      operational_hash: OP_HASH, outcome: opts.partial ? "PARTIAL" : "SUCCEEDED", schema_version: "or-comparison-v2", transfer_mode: "HUB_AND_PANTRY", warnings: [],
    },
  };
}

const job = (identity: string, state: State, reason: string | null = null) => ({
  job_id: identity, current_attempt_id: id(1001), state,
  attempts: [{ attempt_id: id(1001), state, reason_code: reason, enqueued_at: "2026-11-02T13:05:00Z", started_at: null, completed_at: null }],
}) satisfies Schemas["ForecastJob"];
const accepted = (identity: string) => ({ job_id: identity, attempt_id: id(1001), replayed: false, state: "QUEUED", result_url: `/api/v1/comparisons/${identity}`, status_url: `/api/v1/jobs/${identity}` }) satisfies Schemas["ForecastAccepted"];
const envelope = (code: string) => ({ error: { code, message: code.toLowerCase().replaceAll("_", " "), details: {} }, request_id: id(999) });

type Reply = { status: number; body: unknown };
type Options = {
  presenter?: boolean;
  catalog?: Schemas["PlanningCatalog"];
  freeze?: Reply;
  compare?: Reply;
  jobStates?: Record<string, { state: State; reason?: string }[]>;
  comparisons?: Record<string, Schemas["SavedComparison"]>;
  initial?: Reply;
};

async function mockApi(page: Page, options: Options = {}) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const polls: Record<string, number> = {};
  const scenarios: Record<string, Schemas["ScenarioResult"]> = { [SCENARIO]: scenario(), [OLD_SCENARIO]: scenario(OLD_SCENARIO, "HUB_ONLY", "2026-11-01T09:00:00Z") };
  const comparisons = options.comparisons ?? { [JOB]: comparison() };
  if (options.presenter !== false) await page.context().addCookies([{ name: "pp_csrf", value: "token", url: BASE }]);
  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1/", "");
    const method = request.method();
    const body = method === "POST" ? request.postDataJSON() : null;
    calls.push({ method, path, body });
    const reply = (status: number, value: unknown) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(value) });
    if (options.presenter === false) return reply(401, envelope("PRESENTER_REQUIRED"));
    if (path === "allocation-methodology") return reply(200, methodology);
    if (options.initial && (path === "planning-catalog" || path === "forecast-catalog")) return reply(options.initial.status, options.initial.body);
    if (path === "planning-catalog") return reply(200, options.catalog ?? catalog());
    if (path === "forecast-catalog") return reply(200, network);
    if (path === `planning-assumptions/${ASSUMPTIONS}`) return reply(200, assumptions);
    if (path === "scenarios" && method === "POST") return options.freeze ? reply(options.freeze.status, options.freeze.body) : reply(201, scenarios[SCENARIO]);
    if (path.endsWith("/compare-methods")) return options.compare ? reply(options.compare.status, options.compare.body) : reply(202, accepted(JOB));
    const scenarioMatch = path.match(/^scenarios\/([0-9a-f-]+)$/);
    if (scenarioMatch) return reply(200, scenarios[scenarioMatch[1]]);
    const jobMatch = path.match(/^jobs\/([0-9a-f-]+)(\/cancel|\/retry)?$/);
    if (jobMatch) {
      const [, jobId, action] = jobMatch;
      if (action === "/retry") return reply(202, accepted(RETRY_JOB));
      if (action === "/cancel") return reply(202, { job_id: jobId, attempt_id: id(1001), completed: false, replayed: false, state: "STOPPING" });
      const sequence = options.jobStates?.[jobId] ?? [{ state: "QUEUED" }, { state: "RUNNING" }, { state: "SUCCEEDED" }];
      const n = polls[jobId] = (polls[jobId] ?? -1) + 1;
      const step = sequence[Math.min(n, sequence.length - 1)];
      return reply(200, job(jobId, step.state, step.reason ?? null));
    }
    const comparisonMatch = path.match(/^comparisons\/([0-9a-f-]+)$/);
    if (comparisonMatch) return comparisons[comparisonMatch[1]] ? reply(200, comparisons[comparisonMatch[1]]) : reply(404, envelope("NOT_FOUND"));
    return reply(404, envelope("NOT_FOUND"));
  });
  return calls;
}

async function open(page: Page, width: number, height: number, query = "") {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width, height });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`/scenarios${query}`);
  await expect(page.getByRole("heading", { level: 1, name: "Scenario Lab" })).toBeVisible();
  return errors;
}

const step = (page: Page, n: number) => page.getByRole("group", { name: new RegExp(`^Step ${n} of 4`) });
const mobile = (width: number) => width < 768;
async function showStep(page: Page, width: number, n: number) {
  if (!mobile(width)) return;
  await expect(page.locator("[data-current-step]")).toBeVisible();
  for (let i = 0; i < 4 && !(await step(page, n).isVisible()); i += 1) {
    const current = Number((await page.locator("[data-current-step]").getAttribute("data-current-step")) ?? "1");
    await page.getByRole("button", { name: current < n ? "Next step" : "Previous step" }).click();
  }
  await expect(step(page, n)).toBeVisible();
}

async function expectComparisonResults(page: Page) {
  const results = page.getByRole("region", { name: "Scenario results" });
  await expect(results.getByText("Classical GP").first()).toBeVisible();
  await expect(results.getByText("EGP-PI-inspired").first()).toBeVisible();
  // Service coverage per product, both methods, with units; never one combined meal+bottle figure.
  await expect(results.getByText(/meals/).first()).toBeVisible();
  await expect(results.getByText(/bottles/).first()).toBeVisible();
  // Fill rate by site: six beneficiaries, N/A for the zero-target goal.
  const fill = page.getByRole("table", { name: /Projected fill rate by site/ });
  await expect(fill.locator("tbody tr")).toHaveCount(6);
  await page.getByRole("combobox", { name: "Fill-rate product" }).click();
  await page.getByRole("option", { name: /Bottled water/ }).click();
  await expect(fill.getByRole("row", { name: /Quarry Pantry/ })).toContainText("N/A");
  // The per-goal method difference: one institution × product, side by side, with AP/RP.
  const goals = page.getByRole("table", { name: /Goals by site and product/ });
  const lakeside = goals.locator(`[id="goal-${LAKESIDE}-${MEAL}"]`);
  await expect(lakeside).toContainText("Lakeside Pantry");
  await expect(lakeside).toContainText("30");
  await expect(lakeside).toContainText("45");
  await expect(lakeside.locator("[data-flag='ap-classical']")).toHaveText("AP");
  await expect(lakeside.locator("[data-flag='ap-egp']")).toHaveText("—");
  // Key trade-off links to that row.
  const tradeoffs = page.getByRole("region", { name: "Key trade-offs" });
  const link = tradeoffs.getByRole("link", { name: /Lakeside Pantry/ }).first();
  await expect(link).toHaveAttribute("href", `#goal-${LAKESIDE}-${MEAL}`);
  // Transfer diff and the reported common differences.
  const diff = page.getByRole("table", { name: /Transfer changes between methods/ });
  await expect(diff.getByRole("row", { name: /Mill Street Pantry/ })).toContainText("30 → 15 meals");
  await expect(page.getByRole("list", { name: "Common differences as reported" })).toContainText("shared_feasible_region");
  for (const text of ["household", "$", "equity score", ...MOCKUP_ONLY]) await expect(page.getByText(text, { exact: false })).toHaveCount(0);
}

for (const [width, height] of [[1440, 900], [1280, 720], [390, 844]]) {
  test(`presenter freezes and compares once, the job resolves and survives reload at ${width}x${height}`, async ({ page }, testInfo) => {
    test.setTimeout(90_000);
    const calls = await mockApi(page);
    const errors = await open(page, width, height);
    await showStep(page, width, 1);
    await expect(step(page, 1)).toContainText("Shelf-stable meals");
    await expectNoSeriousA11yViolations(page, testInfo, `step 1 ${width}x${height}`);

    await showStep(page, width, 2);
    const radios = step(page, 2).getByRole("radio");
    await expect(radios).toHaveCount(2);
    for (const radio of await radios.all()) await expect(radio).not.toBeChecked();
    await expect(step(page, 2)).toContainText("Incomplete");
    await showStep(page, width, 4);
    await expect(page.getByRole("button", { name: "Create frozen scenario" })).toBeDisabled();
    await expectNoSeriousA11yViolations(page, testInfo, `step 4 empty ${width}x${height}`);

    await showStep(page, width, 2);
    await step(page, 2).getByRole("radio", { name: /Hub and pantry-to-pantry/ }).check();
    await expect(page.getByText("Draft changes — not computed")).toBeVisible();
    await showStep(page, width, 3);
    await expectNoSeriousA11yViolations(page, testInfo, `step 3 ${width}x${height}`);
    await showStep(page, width, 4);
    const freeze = page.getByRole("button", { name: "Create frozen scenario" });
    await freeze.dblclick();
    await expect(page.getByText(`Frozen scenario ${SCENARIO.slice(0, 8)}`).first()).toBeVisible();
    const freezes = calls.filter((c) => c.method === "POST" && c.path === "scenarios");
    expect(freezes).toHaveLength(1);
    const body = freezes[0].body as Schemas["ScenarioRequest"];
    expect(body).toMatchObject({ forecast_run_id: FORECAST, assumptions_id: ASSUMPTIONS, expected_source_revision: REVISION, transfer_mode: "HUB_AND_PANTRY", planning_days: 1 });
    expect(body.modifiers).toHaveLength(14);
    expect(body.modifiers.filter((m) => m.site_id === HUB)).toEqual(PRODUCTS.map((p) => ({
      site_id: HUB, product_id: p.id, mode: "CENTRAL", multiplier: "1", buffer_fraction: null,
    })));
    expect(body.modifiers.every((m) => m.mode === "CENTRAL" && m.multiplier === "1" && m.buffer_fraction === null)).toBe(true);

    await page.getByRole("button", { name: "Compare methods" }).dblclick();
    const compares = calls.filter((c) => c.method === "POST" && c.path.endsWith("/compare-methods"));
    expect(compares).toHaveLength(1);
    expect(compares[0].path).toBe(`scenarios/${SCENARIO}/compare-methods`);
    expect(compares[0].body).toEqual({ expected_scenario_hash: OP_HASH, search_seconds: 120 });
    const status = page.locator("[data-job-state]");
    await expect(status).toHaveAttribute("data-job-state", /QUEUED|RUNNING/);
    await expect(page.getByRole("region", { name: "Scenario results" }).getByText(/No verified comparison/)).toBeVisible();
    await expect(status).toHaveAttribute("data-job-state", "SUCCEEDED", { timeout: 15_000 });
    expect(new URL(page.url()).searchParams.get("job")).toBe(JOB);
    await expectComparisonResults(page);
    await expectNoSeriousA11yViolations(page, testInfo, `results ${width}x${height}`);
    await page.screenshot({ path: testInfo.outputPath(`scenario-lab-${width}.png`), fullPage: true });

    await page.reload();
    await expect(page.locator("[data-job-state]")).toHaveAttribute("data-job-state", "SUCCEEDED", { timeout: 15_000 });
    await expect(page.getByRole("table", { name: /Goals by site and product/ })).toBeVisible();
    expect(errors).toEqual([]);
  });
}

test("multiplier above 3 or with five decimals blocks freezing with a field message", async ({ page }, testInfo) => {
  await mockApi(page);
  await open(page, 1440, 900);
  await step(page, 2).getByRole("radio", { name: /Hub to pantry only/ }).check();
  const input = page.getByLabel("Lakeside Pantry · Shelf-stable meals demand multiplier");
  const freeze = page.getByRole("button", { name: "Create frozen scenario" });
  await expect(freeze).toBeEnabled();
  await input.fill("3.5");
  await expect(input).toHaveAttribute("aria-invalid", "true");
  await expect(input).toBeFocused();
  await expect(step(page, 3)).toContainText("Use a multiplier from 0 to 3");
  await expect(freeze).toBeDisabled();
  await input.fill("1.23456");
  await expect(step(page, 3)).toContainText("Use at most 4 decimal places");
  await expect(freeze).toBeDisabled();
  await expectNoSeriousA11yViolations(page, testInfo, "invalid multiplier");
  await input.fill("1.25");
  await expect(input).not.toHaveAttribute("aria-invalid", "true");
  await expect(freeze).toBeEnabled();
});

test("a failed job shows Retry and keeps the previous verified result with its time", async ({ page }) => {
  test.setTimeout(60_000);
  const calls = await mockApi(page, {
    catalog: catalog({ comparisons: [{ id: OLD_JOB, label: "SUCCEEDED", recorded_at: "2026-11-01T09:30:00Z" }] }),
    comparisons: { [OLD_JOB]: comparison(OLD_JOB, { recorded: "2026-11-01T09:30:00Z" }) },
    jobStates: { [JOB]: [{ state: "RUNNING" }, { state: "FAILED", reason: "WORKER_CRASHED" }] },
  });
  await open(page, 1440, 900, `?comparison=${OLD_JOB}`);
  await expect(page.getByRole("table", { name: /Goals by site and product/ })).toBeVisible();
  await step(page, 2).getByRole("radio", { name: /Hub and pantry-to-pantry/ }).check();
  await page.getByRole("button", { name: "Create frozen scenario" }).click();
  await page.getByRole("button", { name: "Compare methods" }).click();
  const status = page.locator("[data-job-state]");
  await expect(status).toHaveAttribute("data-job-state", "FAILED", { timeout: 15_000 });
  await expect(status).toContainText("WORKER_CRASHED");
  await expect(page.getByText(/Showing the previous verified result saved/)).toBeVisible();
  await expect(page.getByRole("table", { name: /Goals by site and product/ })).toBeVisible();
  await page.getByRole("button", { name: "Retry" }).click();
  expect(calls.filter((c) => c.method === "POST" && c.path === `jobs/${JOB}/retry`)).toHaveLength(1);
  await expect(page).toHaveURL(new RegExp(`job=${RETRY_JOB}`));
});

test("PARTIAL shows the failed method's error and only the other method's results", async ({ page }, testInfo) => {
  await mockApi(page, { comparisons: { [JOB]: comparison(JOB, { partial: true }) } });
  await open(page, 1440, 900, `?comparison=${JOB}`);
  const results = page.getByRole("region", { name: "Scenario results" });
  await expect(results.getByText("Partially available")).toBeVisible();
  await expect(results.getByText("SOLVER_TIMEOUT").first()).toBeVisible();
  await expect(page.getByRole("region", { name: "Key trade-offs" })).toContainText("Trade-offs need both methods verified");
  const goals = page.getByRole("table", { name: /Goals by site and product/ });
  await expect(goals.locator(`[id="goal-${LAKESIDE}-${MEAL}"] [data-flag='ap-egp']`)).toHaveText("Not verified");
  await expectNoSeriousA11yViolations(page, testInfo, "partial");
});

test("stale sources (409) on freeze and a moved scenario hash (409) on compare explain themselves", async ({ page }) => {
  await mockApi(page, { freeze: { status: 409, body: envelope("STALE_PLANNING_SOURCE") } });
  await open(page, 1440, 900);
  await step(page, 2).getByRole("radio", { name: /Hub to pantry only/ }).check();
  await page.getByRole("button", { name: "Create frozen scenario" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Sources changed; refresh and freeze again" })).toBeVisible();
});

test("compare 409 SCENARIO_REVISION_MISMATCH asks for a new frozen scenario", async ({ page }) => {
  await mockApi(page, { compare: { status: 409, body: envelope("SCENARIO_REVISION_MISMATCH") } });
  await open(page, 1440, 900);
  await step(page, 2).getByRole("radio", { name: /Hub to pantry only/ }).check();
  await page.getByRole("button", { name: "Create frozen scenario" }).click();
  await page.getByRole("button", { name: "Compare methods" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "This scenario changed since it was frozen" })).toBeVisible();
});

test("503 on load shows the unavailable state with Retry", async ({ page }) => {
  await mockApi(page, { initial: { status: 503, body: envelope("PLANNING_UNAVAILABLE") } });
  await open(page, 1440, 900);
  await expect(page.getByRole("alert").filter({ hasText: "The planning service is unavailable" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});

for (const [width, height] of [[1440, 900], [390, 844]]) {
  test(`visitor sees a read-only explanation with no enabled controls or fixture results at ${width}x${height}`, async ({ page }, testInfo) => {
    await mockApi(page, { presenter: false });
    await open(page, width, height);
    await expect(page.getByText(/Sign in as presenter from the sidebar/)).toBeVisible();
    await showStep(page, width, 2);
    for (const radio of await page.getByRole("radio").all()) await expect(radio).toBeDisabled();
    await showStep(page, width, 4);
    await expect(page.getByRole("button", { name: "Create frozen scenario" })).toBeDisabled();
    await expect(page.getByRole("table", { name: /Goals by site and product/ })).toHaveCount(0);
    for (const text of MOCKUP_ONLY) await expect(page.getByText(text, { exact: false })).toHaveCount(0);
    await expectNoSeriousA11yViolations(page, testInfo, `visitor ${width}x${height}`);
    await page.screenshot({ path: testInfo.outputPath(`scenario-lab-visitor-${width}.png`), fullPage: true });
  });
}

test("connected: freeze → compare → verified results end to end", async ({ page }) => {
  test.skip(process.env.PP_RUN_CONNECTED !== "1", "Requires isolated seeded PostgreSQL, API and Linux worker");
  test.setTimeout(600_000);
  await page.goto("/overview");
  await page.getByRole("button", { name: "Presenter sign in" }).click();
  const dialog = page.getByRole("dialog", { name: "Presenter sign in" });
  await dialog.getByLabel("Username").fill(process.env.PP_E2E_USERNAME ?? "presenter");
  await dialog.getByLabel("Password").fill(process.env.PP_E2E_PASSWORD ?? "pantry-local-demo");
  await Promise.all([page.waitForEvent("load"), dialog.getByRole("button", { name: "Sign in", exact: true }).click()]);
  await expect(page.getByText("Presenter session · simulated demo")).toBeVisible();
  await page.goto("/scenarios");
  await page.getByRole("button", { name: "Generate forecast", exact: true }).click();
  await expect(page.locator("[data-job-state]")).toHaveAttribute("data-job-state", "SUCCEEDED", { timeout: 90_000 });
  await step(page, 2).getByRole("radio", { name: /Hub and pantry-to-pantry/ }).check();
  await page.getByRole("button", { name: "Create frozen scenario" }).click();
  await page.getByLabel("Search seconds per method").fill("1");
  const submitting = page.waitForResponse((response) => /\/scenarios\/[^/]+\/compare-methods$/.test(new URL(response.url()).pathname) && response.request().method() === "POST");
  await page.getByRole("button", { name: "Compare methods" }).click();
  const accepted = await submitting;
  expect(accepted.status()).toBe(202);
  const comparisonId = (await accepted.json()).job_id as string;
  await expect(page.locator("[data-job-state]")).toContainText(comparisonId.slice(0, 8));
  await expect(page.locator("[data-job-state]")).toHaveAttribute("data-job-state", "SUCCEEDED", { timeout: 540_000 });
  await expect(page.getByRole("table", { name: /Goals by site and product/ })).toBeVisible();
});
