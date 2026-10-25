import type { Schema } from "@/lib/planning-api";

// Pure derivations over saved, server-computed comparison results. Nothing here computes a plan:
// it only reads verified metrics, joins the two methods on the same frozen scenario and formats them.

export type Method = Schema["AllocationMethod"];
export type MethodOutcome = Schema["MethodOutcome"];
export type Metrics = Schema["Metrics"];
export type Goal = Schema["GoalMetric"];
export type Rational = Schema["Rational"];

export const METHODS: Method[] = ["CLASSICAL_GP", "EGP_PI_INSPIRED"];
export const METHOD_LABEL: Record<Method, string> = { CLASSICAL_GP: "Classical GP", EGP_PI_INSPIRED: "EGP-PI-inspired" };
export const MODE_LABEL: Record<Schema["TransferMode"], string> = { HUB_ONLY: "Hub to pantry only", HUB_AND_PANTRY: "Hub and pantry-to-pantry" };

export type ProductInfo = { id: string; name: string; unit: string };
export type SiteInfo = { id: string; name: string };

const NO_ALLOCATION = new Set(["UNKNOWN", "MODEL_INVALID", "INFEASIBLE"]);

/** Metrics are shown only for a method the independent replay verified with a real solved status. */
export function usableMetrics(outcome: MethodOutcome | undefined): Metrics | null {
  if (!outcome || outcome.outcome !== "VERIFIED" || !outcome.verification?.passed || !outcome.verification.metrics) return null;
  if (outcome.native_status && NO_ALLOCATION.has(outcome.native_status)) return null;
  return outcome.verification.metrics;
}

export function methodOutcome(comparison: Schema["SavedComparison"] | null, method: Method) {
  return comparison?.result.methods.find((m) => m.method === method);
}

export const ratio = (value: Rational | null | undefined) => (value && value.denominator !== 0 ? value.numerator / value.denominator : null);
export const pct = (value: number | null) => (value === null ? "N/A" : `${(value * 100).toFixed(1)}%`);
export const decimal = (value: number | null, digits = 3) => (value === null ? "N/A" : value.toFixed(digits));
export const count = (value: number) => value.toLocaleString("en-US");
/** Units stay attached to every quantity; base units are singular nouns ("meal", "bottle"). */
export const units = (value: number, unit: string) => `${count(value)} ${value === 1 ? unit : `${unit}s`}`;
export const plural = (unit: string) => `${unit}s`;

/** Σ fulfilled / Σ target over positive-target goals of one product; null when nothing was targeted. */
export function coverage(metrics: Metrics, productId: string): number | null {
  const goals = metrics.goals.filter((g) => g.product_id === productId && g.target > 0);
  const target = goals.reduce((n, g) => n + g.target, 0);
  return target === 0 ? null : goals.reduce((n, g) => n + g.fulfilled, 0) / target;
}

export const unmet = (metrics: Metrics, productId: string) => metrics.goals.filter((g) => g.product_id === productId).reduce((n, g) => n + g.unmet, 0);

export function flagged(metrics: Metrics, productId: string) {
  const group = metrics.groups.find((g) => g.product_id === productId);
  if (group) return { ap: group.ap_count, rp: group.rp_count, size: group.size };
  const goals = metrics.goals.filter((g) => g.product_id === productId && g.target > 0);
  return { ap: goals.filter((g) => g.ap).length, rp: goals.filter((g) => g.rp).length, size: goals.length };
}

export const expired = (metrics: Metrics, productId: string) => metrics.waste_by_product.find(([id]) => id === productId)?.[1] ?? null;

export type GoalRow = { key: string; siteId: string; productId: string; baseline?: Goal; classical?: Goal; egp?: Goal };
export const goalAnchor = (siteId: string, productId: string) => `goal-${siteId}-${productId}`;

/** Join baseline and both methods' goals by site × product, in network site order then product order. */
export function joinGoals(sites: SiteInfo[], products: ProductInfo[], baseline: Metrics | null, classical: Metrics | null, egp: Metrics | null): GoalRow[] {
  const rows = new Map<string, GoalRow>();
  const put = (goals: Goal[] | undefined, field: "baseline" | "classical" | "egp") => {
    for (const goal of goals ?? []) {
      const key = `${goal.site_id}|${goal.product_id}`;
      const row = rows.get(key) ?? { key, siteId: goal.site_id, productId: goal.product_id };
      row[field] = goal;
      rows.set(key, row);
    }
  };
  put(baseline?.goals, "baseline"); put(classical?.goals, "classical"); put(egp?.goals, "egp");
  const siteOrder = (id: string) => { const i = sites.findIndex((s) => s.id === id); return i < 0 ? sites.length : i; };
  const productOrder = (id: string) => { const i = products.findIndex((p) => p.id === id); return i < 0 ? products.length : i; };
  return [...rows.values()].sort((a, b) => siteOrder(a.siteId) - siteOrder(b.siteId) || productOrder(a.productId) - productOrder(b.productId));
}

export type TransferChange = {
  key: string; kind: "added" | "removed" | "changed" | "same";
  sourceId: string; destinationId: string; productId: string; unit: string; lotId: string; departure: string; arrival: string;
  classical: number | null; egp: number | null;
};

/** Diff Classical → EGP-PI-inspired transfers by source, destination, product, lot and dates. */
export function diffAssignments(classical: Schema["TransferAssignment"][], egp: Schema["TransferAssignment"][]): TransferChange[] {
  const rows = new Map<string, TransferChange>();
  const add = (list: Schema["TransferAssignment"][], field: "classical" | "egp") => {
    for (const a of list) {
      const key = [a.source_id, a.destination_id, a.product_id, a.original_lot_id, a.departure, a.arrival].join("|");
      const row = rows.get(key) ?? { key, kind: "same", sourceId: a.source_id, destinationId: a.destination_id, productId: a.product_id,
        unit: a.unit, lotId: a.original_lot_id, departure: a.departure, arrival: a.arrival, classical: null, egp: null };
      row[field] = (row[field] ?? 0) + a.units;
      rows.set(key, row);
    }
  };
  add(classical, "classical"); add(egp, "egp");
  const order = { changed: 0, added: 1, removed: 2, same: 3 };
  return [...rows.values()].map((row) => ({ ...row,
    kind: row.classical === null ? "added" : row.egp === null ? "removed" : row.classical === row.egp ? "same" : "changed" } as TransferChange))
    .sort((a, b) => order[a.kind] - order[b.kind]);
}

export type Tradeoff = { id: string; text: string; anchor?: string; linkText?: string };

/**
 * Deterministic trade-offs from the two verified methods on one frozen scenario: the largest
 * same-product per-site service difference in each direction, residual unmet, AP/RP and cost/expiry.
 */
export function tradeoffs(rows: GoalRow[], sites: SiteInfo[], products: ProductInfo[], classical: Metrics, egp: Metrics): Tradeoff[] {
  const site = (id: string) => sites.find((s) => s.id === id)?.name ?? id.slice(0, 8);
  const product = (id: string) => products.find((p) => p.id === id);
  const diffs = rows.flatMap((row) => {
    const c = ratio(row.classical?.service_ratio), e = ratio(row.egp?.service_ratio);
    return c === null || e === null || c === e ? [] : [{ row, c, e, d: e - c }];
  });
  const result: Tradeoff[] = [];
  const describe = (item: (typeof diffs)[number], winner: string) => {
    const p = product(item.row.productId);
    result.push({ id: `${winner}-${item.row.key}`, anchor: goalAnchor(item.row.siteId, item.row.productId),
      linkText: `${site(item.row.siteId)} · ${p?.name ?? "product"}`,
      text: `: ${pct(item.e)} served under EGP-PI-inspired vs ${pct(item.c)} under Classical GP (${item.d > 0 ? "+" : "−"}${Math.abs(item.d * 100).toFixed(1)} pts) on the same frozen inputs.` });
  };
  const gain = diffs.filter((x) => x.d > 0).sort((a, b) => b.d - a.d)[0];
  const loss = diffs.filter((x) => x.d < 0).sort((a, b) => a.d - b.d)[0];
  if (gain) describe(gain, "egp");
  if (loss) describe(loss, "classical");
  if (!gain && !loss) result.push({ id: "same", text: "Both methods give every site the same service ratio on these frozen inputs." });
  result.push({ id: "unmet", text: `Unmet after each method (Classical GP / EGP-PI-inspired): ${products.map((p) =>
    `${p.name} ${units(unmet(classical, p.id), p.unit)} / ${units(unmet(egp, p.id), p.unit)}`).join("; ")}.` });
  result.push({ id: "flags", text: `AP / RP flagged goals (Classical GP → EGP-PI-inspired): ${products.map((p) => {
    const c = flagged(classical, p.id), e = flagged(egp, p.id);
    return `${p.name} AP ${c.ap} → ${e.ap}, RP ${c.rp} → ${e.rp} of ${e.size}`;
  }).join("; ")}. Simulated cost points ${count(classical.cost_minor)} → ${count(egp.cost_minor)}.` });
  return result.slice(0, 4);
}

export type MultiplierCheck = string | null;
/** Mirrors the server's DemandModifier rule (or_inputs.py): 0 ≤ multiplier ≤ 3 with at most four decimals. */
export function checkMultiplier(text: string): MultiplierCheck {
  const value = text.trim();
  if (!/^\d+(?:\.\d+)?$/.test(value)) return "Enter a multiplier from 0 to 3.";
  if (Number(value) > 3) return "Use a multiplier from 0 to 3.";
  if ((value.split(".")[1] ?? "").length > 4) return "Use at most 4 decimal places.";
  return null;
}

export function solverStatusText(outcome: MethodOutcome | undefined) {
  if (!outcome) return "Not run";
  const status = outcome.native_status;
  if (outcome.outcome !== "VERIFIED") return `${outcome.outcome.replaceAll("_", " ").toLowerCase()}${outcome.error_code ? ` · ${outcome.error_code}` : ""}`;
  if (status === "OPTIMAL") return "Optimal (native status)";
  if (status === "FEASIBLE") return "Feasible, not proven optimal";
  if (status && NO_ALLOCATION.has(status)) return `${status}: no allocation shown`;
  return status ?? "No native status";
}

export const shortId = (value: string | null | undefined) => (value ? value.slice(0, 8) : "—");
export const when = (iso: string) => new Date(iso).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
