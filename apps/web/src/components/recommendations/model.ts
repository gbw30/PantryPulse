import type { Schema } from "@/lib/planning-api";

// Presentation of a saved, independently verified comparison. Nothing here computes eligibility,
// feasibility or benefit: values are read from the saved result, and the only arithmetic is a sum of
// one product's own units (never across products).

export type Method = Schema["AllocationMethod"];
export type MethodOutcome = Schema["MethodOutcome"];
export type Assignment = Schema["TransferAssignment"];
export type GoalMetric = Schema["GoalMetric"];
export type Rational = Schema["Rational"];

export const METHOD_LABEL: Record<Method, string> = { CLASSICAL_GP: "Classical GP", EGP_PI_INSPIRED: "EGP-PI-inspired" };

export const TAB_KEYS = ["action-plan", "sites", "network", "fairness"] as const;
export type TabKey = (typeof TAB_KEYS)[number];
export const TAB_LABEL: Record<TabKey, string> = {
  "action-plan": "Action Plan", sites: "Site Recommendations", network: "Network Optimization", fairness: "Impact & Fairness",
};
export const isTabKey = (value: string | null | undefined): value is TabKey => TAB_KEYS.includes(value as TabKey);

/** Everything one saved comparison needs, read once and frozen. */
export type Loaded = {
  comparison: Schema["SavedComparison"];
  scenario: Schema["ScenarioResult"];
  /** Saved plan records (ids + result_hash) by method; null when the read failed. */
  plans: Schema["PlanResult"][] | null;
  plansError: string | null;
  productNames: Map<string, string>;
};

export type ProductInfo = { id: string; unit: string; name: string };

const PROVIDER_LABEL: Record<string, string> = {
  SEASONAL_NAIVE: "Seasonal-naive baseline", MOVING_AVERAGE: "Moving-average baseline", CHRONOS2: "Chronos-2 model",
};
export const providerLabel = (provider: string) => PROVIDER_LABEL[provider] ?? provider;

export const shortId = (value: string) => value.slice(0, 8);

export function units(count: number, unit: string) {
  const plural = count === 1 || unit.endsWith("s") ? unit : `${unit}s`;
  return `${count.toLocaleString("en-US")} ${plural}`;
}

const DAY = new Intl.DateTimeFormat("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" });
/** A local calendar date (YYYY-MM-DD) as "Tue, Nov 3"; dates carry no time zone of their own. */
export function formatDay(day: string) {
  return DAY.format(new Date(`${day}T00:00:00Z`));
}

export function formatInstant(iso: string, timeZone = "UTC") {
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone, timeZoneName: "short" }).format(new Date(iso));
}

/** A rational as a decimal with at most four places; the exact fraction goes in the title. */
export function decimal(value: Rational) {
  if (value.denominator === 0) return "N/A";
  return String(Number((value.numerator / value.denominator).toFixed(4)));
}
export const fraction = (value: Rational) => `${value.numerator}/${value.denominator}`;

export function nativeStatusLabel(status: string | null) {
  switch (status) {
    case "OPTIMAL": return "Optimal";
    case "FEASIBLE": return "Feasible, not proven optimal";
    case "INFEASIBLE": return "Infeasible";
    case "UNKNOWN": return "Unknown, no plan";
    case "MODEL_INVALID": return "Model invalid, no plan";
    case null: return "No solver status";
    default: return status;
  }
}

export function outcomeLabel(outcome: MethodOutcome["outcome"]) {
  return { VERIFIED: "Verified", FAILED: "Failed", TIMED_OUT: "Timed out", CANCELLED: "Cancelled", INTERRUPTED: "Interrupted" }[outcome];
}

export function replayLabel(method: MethodOutcome) {
  if (!method.verification) return "not run";
  return method.verification.passed ? "passed" : "failed";
}

/** A plan the screen may list: verified outcome, passed independent replay, OPTIMAL or FEASIBLE, with a candidate. */
export function isUsable(method: MethodOutcome) {
  return method.outcome === "VERIFIED" && method.verification?.passed === true && method.verification.metrics !== null
    && (method.native_status === "OPTIMAL" || method.native_status === "FEASIBLE") && method.candidate !== null;
}

/** Q-54-2: the first usable method in API order; otherwise the first method so its failure is visible. */
export function defaultMethod(methods: MethodOutcome[]): Method | null {
  return (methods.find(isUsable) ?? methods[0])?.method ?? null;
}

export const transferModeLabel = (mode: Schema["TransferMode"]) => (mode === "HUB_ONLY" ? "Hub only" : "Hub and pantry");

export function products(loaded: Loaded): ProductInfo[] {
  return loaded.scenario.payload.package.products.map((product) => ({
    id: product.id, unit: product.unit, name: loaded.productNames.get(product.id) ?? `Product ${shortId(product.id)}`,
  }));
}

export function productInfo(loaded: Loaded, productId: string): ProductInfo {
  return products(loaded).find((product) => product.id === productId) ?? { id: productId, unit: "unit", name: `Product ${shortId(productId)}` };
}

export function siteName(loaded: Loaded, siteId: string) {
  return loaded.scenario.payload.package.sites.find((site) => site.id === siteId)?.name ?? `Site ${shortId(siteId)}`;
}

export function siteRole(loaded: Loaded, siteId: string) {
  return loaded.scenario.payload.package.sites.find((site) => site.id === siteId)?.role ?? null;
}

export function forecastProviders(loaded: Loaded) {
  return [...new Set(loaded.scenario.payload.demand.map((series) => series.actual_provider))];
}

export function planRecord(loaded: Loaded, method: Method) {
  return loaded.plans?.find((plan) => plan.method === method) ?? null;
}

export type ActionRow = {
  key: string;
  assignment: Assignment;
  sourceName: string;
  destinationName: string;
  sourceIsHub: boolean;
  product: ProductInfo;
  /** First day with unmet > 0 at the destination for this product, with this plan applied; null = none in window. */
  firstDeficit: string | null;
  etaDays: number | null;
  reserveFloors: number[] | null;
};

export const rowKey = (assignment: Assignment) => `${assignment.route_id}|${assignment.original_lot_id}|${assignment.departure}`;

export function firstDeficit(method: MethodOutcome, siteId: string, productId: string) {
  const days = method.verification?.projection?.days ?? [];
  return days.filter((day) => day.site_id === siteId && day.product_id === productId && day.unmet > 0).map((day) => day.day).sort()[0] ?? null;
}

export function actionRows(loaded: Loaded, method: MethodOutcome): ActionRow[] {
  const pkg = loaded.scenario.payload.package;
  return (method.candidate?.assignments ?? []).map((assignment) => ({
    key: rowKey(assignment),
    assignment,
    sourceName: siteName(loaded, assignment.source_id),
    destinationName: siteName(loaded, assignment.destination_id),
    sourceIsHub: siteRole(loaded, assignment.source_id) === "HUB",
    product: productInfo(loaded, assignment.product_id),
    firstDeficit: firstDeficit(method, assignment.destination_id, assignment.product_id),
    etaDays: pkg.routes.find((route) => route.id === assignment.route_id)?.eta_days ?? null,
    reserveFloors: pkg.reserves.find((reserve) => reserve.site_id === assignment.source_id && reserve.product_id === assignment.product_id)?.floors ?? null,
  }));
}

export type SortKey = "deficit" | "arrival" | "destination" | "product";
export const SORT_LABEL: Record<SortKey, string> = { deficit: "First deficit date", arrival: "Arrival date", destination: "Destination site", product: "Product" };

export function sortRows(rows: ActionRow[], sort: SortKey) {
  const value = (row: ActionRow) => {
    if (sort === "deficit") return row.firstDeficit ?? "9999-12-31";
    if (sort === "arrival") return row.assignment.arrival;
    if (sort === "destination") return row.destinationName;
    return row.product.name;
  };
  return rows.map((row, index) => ({ row, index })).sort((a, b) => value(a.row).localeCompare(value(b.row)) || a.index - b.index).map(({ row }) => row);
}

export const transferLabel = (row: ActionRow) => `${row.sourceName} → ${row.destinationName} · ${units(row.assignment.units, row.assignment.unit)}`;

export type ProductImpact = {
  product: ProductInfo;
  target: number;
  unmetBefore: number | null; unmetAfter: number;
  sitesShortBefore: number | null; sitesShortAfter: number;
  servedBefore: number | null; servedAfter: number;
  expiredBefore: number | null; expiredAfter: number | null;
};

function goalTotals(goals: GoalMetric[], productId: string) {
  const rows = goals.filter((goal) => goal.product_id === productId);
  return {
    target: rows.reduce((sum, goal) => sum + goal.target, 0),
    unmet: rows.reduce((sum, goal) => sum + goal.unmet, 0),
    served: rows.reduce((sum, goal) => sum + goal.fulfilled, 0),
    sitesShort: new Set(rows.filter((goal) => goal.unmet > 0).map((goal) => goal.site_id)).size,
  };
}

const wasteFor = (metrics: Schema["Metrics"] | null | undefined, productId: string) =>
  metrics?.waste_by_product.find(([id]) => id === productId)?.[1] ?? null;

/** Whole plan vs the no-transfer baseline of the same frozen scenario, per product (V5 OPEN-02: not per transfer). */
export function planImpact(loaded: Loaded, method: MethodOutcome): ProductImpact[] {
  const after = method.verification?.metrics;
  const baseline = loaded.comparison.result.baseline_metrics ?? null;
  if (!after) return [];
  return products(loaded).map((product) => {
    const now = goalTotals(after.goals, product.id);
    const before = baseline ? goalTotals(baseline.goals, product.id) : null;
    return {
      product, target: now.target,
      unmetBefore: before?.unmet ?? null, unmetAfter: now.unmet,
      sitesShortBefore: before?.sitesShort ?? null, sitesShortAfter: now.sitesShort,
      servedBefore: before?.served ?? null, servedAfter: now.served,
      expiredBefore: baseline ? wasteFor(baseline, product.id) : null, expiredAfter: wasteFor(after, product.id),
    };
  });
}

export type Remaining = { siteId: string; siteName: string; product: ProductInfo; unmet: number; target: number };

export function remainingNeed(loaded: Loaded, method: MethodOutcome): Remaining[] {
  return (method.verification?.metrics?.goals ?? []).filter((goal) => goal.unmet > 0).map((goal) => ({
    siteId: goal.site_id, siteName: siteName(loaded, goal.site_id), product: productInfo(loaded, goal.product_id), unmet: goal.unmet, target: goal.target,
  }));
}
