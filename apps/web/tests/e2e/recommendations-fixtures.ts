import type { Page, Route } from "@playwright/test";
import type { components } from "../../../../packages/contracts/src/schema";

// Mocked presenter API for the Recommendations screen (PP-54). Values are typed against the generated
// contract. Every name and number here is test data for a fictional, SIMULATED network; none of it is
// mockup content (docs/design/reference/recommendations.md).

export type Schemas = components["schemas"];
export const BASE = `http://127.0.0.1:${process.env.PLAYWRIGHT_PORT ?? "3000"}`;

export const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
export const HUB = id(1);
export const RIVERBEND = id(2), OAK = id(3), CEDAR = id(4), MAPLE = id(5), WILLOW = id(6), PINE = id(7);
export const MEAL = id(101), WATER = id(102);
export const SCENARIO = id(201), SCENARIO_B = id(202);
export const COMPARISON = id(301), COMPARISON_B = id(302);
export const PLAN_CLASSICAL = id(401), PLAN_EGP = id(402);
export const LOT_HUB_MEAL = id(501), LOT_HUB_MEAL_2 = id(502), LOT_HUB_WATER = id(503);
export const ROUTE_RIVERBEND = id(601), ROUTE_OAK = id(602);
export const HASH_CLASSICAL = "c".repeat(64), HASH_EGP = "e".repeat(64);
const TZ = "America/New_York";
export const DAYS = ["2026-11-02", "2026-11-03", "2026-11-04"];

const SITE_NAMES: [string, string, "HUB" | "BENEFICIARY"][] = [
  [HUB, "Gator Distribution Hub", "HUB"], [RIVERBEND, "Riverbend Pantry", "BENEFICIARY"], [OAK, "Oak Terrace Pantry", "BENEFICIARY"],
  [CEDAR, "Cedar Grove Pantry", "BENEFICIARY"], [MAPLE, "Maple Crossing Pantry", "BENEFICIARY"], [WILLOW, "Willow Creek Pantry", "BENEFICIARY"],
  [PINE, "Pine Ridge Pantry", "BENEFICIARY"],
];
export const BENEFICIARIES = SITE_NAMES.filter(([, , role]) => role === "BENEFICIARY").map(([siteId]) => siteId);

const R = (numerator: number, denominator = 1): Schemas["Rational"] => ({ numerator, denominator });

/** One goal row: unmet = target − fulfilled. service_ratio is null when the target is zero. */
function goal(siteId: string, productId: string, target: number, fulfilled: number, flags: { ap?: boolean; rp?: boolean } = {}): Schemas["GoalMetric"] {
  const unmet = target - fulfilled;
  return {
    site_id: siteId, product_id: productId, target, fulfilled, unmet, q: 1, q0: 1,
    ap: flags.ap ?? false, rp: flags.rp ?? false, exact_ap: flags.ap ?? false, exact_rp: flags.rp ?? false,
    deficit: target === 0 ? R(0) : R(unmet, target), service_ratio: target === 0 ? null : R(fulfilled, target),
    vulnerability: R(1, 3), weighted_deficit: target === 0 ? R(0) : R(unmet, target * 3),
  };
}

type GoalSpec = Partial<Record<string, [number, number]>>; // siteId → [meal fulfilled, water fulfilled]

/** Meal targets 100 per beneficiary; water targets 50 except Pine Ridge (no water demand → N/A ratio). */
function goals(fulfilled: GoalSpec, flagged: string[] = []): Schemas["GoalMetric"][] {
  return BENEFICIARIES.flatMap((siteId) => {
    const [meal, water] = fulfilled[siteId] ?? [100, siteId === PINE ? 0 : 50];
    const flag = flagged.includes(siteId) ? { ap: true, rp: siteId === RIVERBEND } : {};
    return [goal(siteId, MEAL, 100, meal, flag), goal(siteId, WATER, siteId === PINE ? 0 : 50, water)];
  });
}

function metrics(goalRows: Schemas["GoalMetric"][], waste: [number, number], cost: number): Schemas["Metrics"] {
  const group = (productId: string): Schemas["GroupMetric"] => ({
    product_id: productId, size: 6, ap_count: goalRows.filter((g) => g.product_id === productId && g.ap).length,
    rp_count: goalRows.filter((g) => g.product_id === productId && g.rp).length, ap_excess_numerator: 0, rp_excess_numerator: 0,
  });
  return {
    W: R(0), W0: R(0), Z: R(0), Z0: R(0), ap_excess: R(0), rp_excess: R(0), classical_objective: R(0), research_objective: R(0),
    cost_minor: cost, q_cost: cost, goals: goalRows, groups: [group(MEAL), group(WATER)],
    q_waste_by_product: [[MEAL, waste[0]], [WATER, waste[1]]], waste_by_product: [[MEAL, waste[0]], [WATER, waste[1]]], warnings: [],
  };
}

// Baseline (no transfers): Riverbend short 60 meals and 10 bottles, Oak Terrace short 30 meals.
export const BASELINE_GOALS = goals({ [RIVERBEND]: [40, 40], [OAK]: [70, 50] }, [RIVERBEND, OAK]);
// Classical plan: Riverbend still short 20 meals and 10 bottles; Oak Terrace covered.
const CLASSICAL_GOALS = goals({ [RIVERBEND]: [80, 40] }, [RIVERBEND]);
// EGP-PI-inspired plan: Riverbend short 10 meals, Oak Terrace short 10 meals, water covered.
const EGP_GOALS = goals({ [RIVERBEND]: [90, 50], [OAK]: [90, 50] }, [RIVERBEND, OAK]);

function assignment(destination: string, productId: string, units: number, lot: string, overrides: Partial<Schemas["TransferAssignment"]> = {}): Schemas["TransferAssignment"] {
  return {
    source_id: HUB, destination_id: destination, product_id: productId, units, unit: productId === MEAL ? "meal" : "bottle",
    route_id: destination === RIVERBEND ? ROUTE_RIVERBEND : ROUTE_OAK, original_lot_id: lot, departure: DAYS[0], arrival: DAYS[1],
    expires_on: productId === MEAL ? "2026-11-20" : null, cost_minor: units * 10, source_revision: "7", ...overrides,
  };
}

export const CLASSICAL_ASSIGNMENTS = [assignment(RIVERBEND, MEAL, 40, LOT_HUB_MEAL), assignment(OAK, MEAL, 30, LOT_HUB_MEAL_2)];
export const EGP_ASSIGNMENTS = [
  assignment(RIVERBEND, MEAL, 50, LOT_HUB_MEAL), assignment(OAK, MEAL, 20, LOT_HUB_MEAL_2), assignment(RIVERBEND, WATER, 10, LOT_HUB_WATER),
];

/** Projection days with the plan applied; only the rows the screen reads. */
function projection(unmetBySite: Record<string, [string, number][]>): Schemas["ProjectionReport"] {
  const days: Schemas["ProjectionDay"][] = BENEFICIARIES.flatMap((siteId) => [MEAL, WATER].flatMap((productId) => DAYS.map((day) => {
    const unmet = productId === MEAL ? (unmetBySite[siteId]?.find(([d]) => d === day)?.[1] ?? 0) : 0;
    return { site_id: siteId, product_id: productId, day, demand: 30, served: 30 - Math.min(30, unmet), unmet, on_hand: 0, received: 0, expired: 0 };
  })));
  return { schema_version: "or-projection-v2", days, blocked_units: [], exclusions: [], lots: [], transit: [] };
}

type MethodOptions = {
  outcome?: Schemas["MethodOutcome"]["outcome"]; nativeStatus?: string | null; errorCode?: string | null;
  assignments?: Schemas["TransferAssignment"][]; passed?: boolean;
};

export function method(name: Schemas["AllocationMethod"], options: MethodOptions = {}): Schemas["MethodOutcome"] {
  const verified = (options.outcome ?? "VERIFIED") === "VERIFIED";
  const classical = name === "CLASSICAL_GP";
  const assignments = options.assignments ?? (classical ? CLASSICAL_ASSIGNMENTS : EGP_ASSIGNMENTS);
  const goalRows = classical ? CLASSICAL_GOALS : EGP_GOALS;
  return {
    method: name, outcome: options.outcome ?? "VERIFIED", native_status: options.nativeStatus === undefined ? (verified ? "OPTIMAL" : null) : options.nativeStatus,
    error_code: options.errorCode ?? null, schema_version: "or-method-result-v2", transfer_mode: "HUB_ONLY", historical: false,
    decision_ids: ["BD-07"], objective: verified ? R(3, 7) : null, operational_hash: "a".repeat(64), policy_hash: "b".repeat(64),
    settings_hash: classical ? "1".repeat(64) : "2".repeat(64), search_seconds: 12, total_seconds: 14, warnings: [],
    candidate: verified ? { assignments, route_quantities: [] } : null,
    verification: verified ? {
      schema_version: "or-verification-v2", verifier_version: "independent-replay-v2", passed: options.passed ?? true, violations: [],
      candidate_hash: "d".repeat(64), operational_hash: "a".repeat(64),
      metrics: metrics(goalRows, classical ? [5, 0] : [3, 0], assignments.reduce((sum, a) => sum + a.cost_minor, 0)),
      projection: projection(classical ? { [RIVERBEND]: [[DAYS[2], 20]] } : { [RIVERBEND]: [[DAYS[2], 10]], [OAK]: [[DAYS[2], 10]] }),
    } : null,
  };
}

type ComparisonOptions = { outcome?: Schemas["ComparisonResult"]["outcome"]; methods?: Schemas["MethodOutcome"][]; stale?: boolean; historical?: boolean; scenarioId?: string; idValue?: string };

export function comparison(options: ComparisonOptions = {}): Schemas["SavedComparison"] {
  return {
    id: options.idValue ?? COMPARISON, scenario_id: options.scenarioId ?? SCENARIO, recorded_at: "2026-11-02T13:05:00Z", settings: { search_seconds: 120 },
    stale: options.stale ?? false, historical: options.historical ?? false,
    result: {
      schema_version: "or-comparison-v2", outcome: options.outcome ?? "SUCCEEDED", transfer_mode: "HUB_ONLY", historical: false,
      operational_hash: "a".repeat(64), common_differences: {}, warnings: [],
      methods: options.methods ?? [method("CLASSICAL_GP"), method("EGP_PI_INSPIRED")],
      baseline_metrics: metrics(BASELINE_GOALS, [12, 0], 0),
    },
  };
}

export function scenario(scenarioId = SCENARIO, planningDays = 3): Schemas["ScenarioResult"] {
  const site = ([siteId, name, role]: [string, string, "HUB" | "BENEFICIARY"]): Schemas["Site"] =>
    ({ id: siteId, name, role, timezone: TZ, organization_id: id(900), source_revision: "7" });
  const capacity = (n: number): Schemas["ResidualCapacity"] => ({ original: n, fixed_used: 0, residual: n, source_revision: "7" });
  return {
    id: scenarioId, assumptions_id: id(700), forecast_run_id: id(800), parent_id: null, recorded_at: "2026-11-02T12:40:00Z", stale: false, historical: false,
    payload: {
      schema_version: "or-scenario-v2", intent: "CURRENT", transfer_mode: "HUB_ONLY", planning_days: planningDays, cost_reference: 1000,
      decision_ids: [], loading_order: [], modifiers: [], operational_hash: "a".repeat(64), policy_hash: "b".repeat(64), waste_references: [],
      demand: BENEFICIARIES.flatMap((siteId) => [MEAL, WATER].map((productId) => ({
        site_id: siteId, product_id: productId, unit: productId === MEAL ? "meal" : "bottle", actual_provider: "SEASONAL_NAIVE", basis: "CENTRAL",
        forecast_result_id: id(810), numeric_conversion: "EXACT_LITERAL" as const, days: [],
      }))),
      policy: {
        schema_version: "or-policy-v1", version: "demo-policy-v1", purpose: "PRIMARY", ap_threshold: 30, rp_threshold: 20, ap_cap_bp: 0, rp_cap_bp: 0,
        beta_percent: 50, gamma_ap_percent: 50, gamma_rp_percent: 50, lambda_percent: 50, epsilon_cost_bp: 0, epsilon_waste_bp: 0, coefficients: [], decision_ids: [],
      },
      package: {
        schema_version: "or-input-v2", source_kind: "SIMULATED", dataset_id: id(901), organization_id: id(900), first_planning_date: DAYS[0],
        operational_timezone: TZ, snapshot_as_of: "2026-11-02T12:30:00Z", source_manifest_hash: "f".repeat(64), source_revision_token: "rev-7",
        decision_ids: [], provenance_warnings: [], source_refs: [], forecasts: [], confirmed_arrivals: [], inventory: [], vulnerability_attributes: [],
        source_coverage: { excluded_series: [], forecast_handoff_hash: null, partial_scope: false, required_complete: true },
        sites: SITE_NAMES.map(site),
        products: [{ id: MEAL, unit: "meal", handling_coefficient: 1, source_revision: "7" }, { id: WATER, unit: "bottle", handling_coefficient: 1, source_revision: "7" }],
        reserves: [{ site_id: HUB, product_id: MEAL, floors: [25, 25, 25] }, { site_id: HUB, product_id: WATER, floors: [10, 10, 10] }],
        routes: [ROUTE_RIVERBEND, ROUTE_OAK].map((routeId) => ({
          id: routeId, source_id: HUB, destination_id: routeId === ROUTE_RIVERBEND ? RIVERBEND : OAK, enabled: true, eta_days: 1,
          cost_unit: "simulated cost point", costs: [], capacity: capacity(200),
        })),
        capacities: { cost_budget_minor: null, global_handling: capacity(500), sites: [] },
      },
    },
  };
}

export function allocationResults(methods = ["CLASSICAL_GP", "EGP_PI_INSPIRED"] as Schemas["AllocationMethod"][], comparisonId = COMPARISON): Schemas["AllocationResults"] {
  return {
    comparison_id: comparisonId, state: "SUCCEEDED",
    plans: methods.map((name) => ({
      id: name === "CLASSICAL_GP" ? PLAN_CLASSICAL : PLAN_EGP, job_id: comparisonId, attempt_id: id(950), comparison_id: comparisonId, method: name,
      recorded_at: "2026-11-02T13:05:00Z", result: method(name), result_hash: name === "CLASSICAL_GP" ? HASH_CLASSICAL : HASH_EGP,
      scenario_id: SCENARIO, settings: {}, stale: false, historical: false,
    })),
  };
}

export const CATALOG: Schemas["PlanningCatalog"] = {
  source_revision: "rev-7", next_before: null, next_before_id: null, assumptions: [], forecasts: [], scenarios: [],
  comparisons: [
    { id: COMPARISON, label: "SUCCEEDED", recorded_at: "2026-11-02T13:05:00Z" },
    { id: COMPARISON_B, label: "PARTIAL", recorded_at: "2026-11-01T18:20:00Z" },
  ],
};

export const FORECAST_CATALOG: Schemas["ForecastCatalog"] = {
  sites: SITE_NAMES.map(([siteId, name, role]) => ({ id: siteId, name, role, timezone: TZ })),
  products: [{ id: MEAL, name: "Shelf-stable meals", base_unit: "meal" }, { id: WATER, name: "Bottled water", base_unit: "bottle" }],
  sources: [],
};

export type Reply = { status: number; body: unknown; delayMs?: number } | "abort";
export const ok = (body: unknown): Reply => ({ status: 200, body });
export const fail = (status: number, code: string): Reply => ({
  status, body: { error: { code, message: code.toLowerCase().replaceAll("_", " "), details: {} }, request_id: id(999) } satisfies Schemas["ErrorEnvelope"],
});

export type Replies = {
  catalog?: Reply; forecastCatalog?: Reply; comparisons?: Record<string, Reply>; results?: Record<string, Reply>;
  scenarios?: Record<string, Reply>; review?: Reply[];
};

export type Hits = { paths: string[]; reviews: { planId: string; body: Schemas["ReviewRequest"]; key: string | null }[] };

async function send(route: Route, reply: Reply) {
  if (reply === "abort") return route.abort("connectionrefused");
  if (reply.delayMs) await new Promise((resolve) => setTimeout(resolve, reply.delayMs));
  return route.fulfill({ status: reply.status, contentType: "application/json", body: JSON.stringify(reply.body) }).catch(() => undefined);
}

/** Presenter session (pp_csrf cookie + 200 probe) unless `visitor`; replies are read at request time so tests can change them. */
export async function mockApi(page: Page, replies: Replies = {}, { visitor = false } = {}): Promise<Hits> {
  const hits: Hits = { paths: [], reviews: [] };
  if (!visitor) await page.context().addCookies([{ name: "pp_csrf", value: "token", url: BASE }]);
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1/", "");
    hits.paths.push(path);
    if (visitor) return send(route, fail(401, "PRESENTER_REQUIRED"));
    if (path === "allocation-methodology") return send(route, ok({ methods: ["CLASSICAL_GP", "EGP_PI_INSPIRED"], transfer_modes: [], default_transfer_mode: null }));
    if (path === "planning-catalog") return send(route, replies.catalog ?? ok(CATALOG));
    if (path === "forecast-catalog") return send(route, replies.forecastCatalog ?? ok(FORECAST_CATALOG));
    let match = /^comparisons\/([^/]+)$/.exec(path);
    if (match) return send(route, replies.comparisons?.[match[1]] ?? ok(comparison({ idValue: match[1] })));
    match = /^allocation-jobs\/([^/]+)\/results$/.exec(path);
    if (match) return send(route, replies.results?.[match[1]] ?? ok(allocationResults(undefined, match[1])));
    match = /^scenarios\/([^/]+)$/.exec(path);
    if (match) return send(route, replies.scenarios?.[match[1]] ?? ok(scenario(match[1])));
    match = /^plans\/([^/]+)\/review$/.exec(path);
    if (match && route.request().method() === "POST") {
      hits.reviews.push({ planId: match[1], body: route.request().postDataJSON(), key: route.request().headers()["idempotency-key"] ?? null });
      const reply = replies.review?.[hits.reviews.length - 1] ?? replies.review?.at(-1) ?? { status: 201, body: { id: id(990), action: "REVIEWED" } };
      return send(route, reply);
    }
    return send(route, fail(404, "NOT_FOUND"));
  });
  return hits;
}
