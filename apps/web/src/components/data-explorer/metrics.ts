import type { ExplorerSnapshot, Product, Quantity, SeriesProjection, Site, SiteStatus } from "./types";

// Display-only measures over one snapshot. Every measure is per product (one base unit); missing days
// are never counted as zero, and a series with a missing day is never reported as covered.

export const cellKey = (siteId: string, productId: string) => `${siteId}|${productId}`;

export type SeriesTotals = {
  /** Every day present with every value. Only complete series enter fill-rate sums. */
  complete: boolean;
  missingDays: number;
  target: number;
  served: number;
  unmet: number;
  /** Earliest day index with observed unmet > 0 (complete or not). */
  firstDeficit: number | null;
  firstDeficitUnits: number | null;
};

export function seriesTotals(projection: SeriesProjection | undefined): SeriesTotals | null {
  if (!projection || projection.kind !== "projected") return null;
  const totals: SeriesTotals = { complete: true, missingDays: 0, target: 0, served: 0, unmet: 0, firstDeficit: null, firstDeficitUnits: null };
  projection.days.forEach((day, index) => {
    if (!day || day.target === null || day.served === null || day.unmet === null) {
      totals.complete = false;
      totals.missingDays += 1;
      if (day?.unmet && day.unmet > 0 && totals.firstDeficit === null) { totals.firstDeficit = index; totals.firstDeficitUnits = day.unmet; }
      return;
    }
    totals.target += day.target;
    totals.served += day.served;
    totals.unmet += day.unmet;
    if (day.unmet > 0 && totals.firstDeficit === null) { totals.firstDeficit = index; totals.firstDeficitUnits = day.unmet; }
  });
  return totals;
}

/** Status from the first projection day: Shortfall (unmet today), Watch (later), Covered (none, complete). */
export function siteStatus(projection: SeriesProjection | undefined): SiteStatus {
  const totals = seriesTotals(projection);
  if (!totals || projection?.kind !== "projected") return "not_evaluated";
  const first = projection.days[0];
  if (first?.unmet && first.unmet > 0) return "shortfall";
  if (totals.firstDeficit !== null) return "watch";
  return totals.complete ? "covered" : "not_evaluated";
}

export function beneficiaries(snapshot: ExplorerSnapshot) {
  return snapshot.sites.filter((site) => site.role === "BENEFICIARY");
}

export function hubs(snapshot: ExplorerSnapshot) {
  return snapshot.sites.filter((site) => site.role === "HUB");
}

export type FillRate = { served: number; target: number; evaluated: number; total: number };

/** Σserved / Σtarget over complete beneficiary series for one product. */
export function networkFill(snapshot: ExplorerSnapshot, productId: string): FillRate {
  const sites = beneficiaries(snapshot);
  const result: FillRate = { served: 0, target: 0, evaluated: 0, total: sites.length };
  for (const site of sites) {
    const totals = seriesTotals(snapshot.projections[cellKey(site.id, productId)]);
    if (!totals?.complete) continue;
    result.evaluated += 1;
    result.served += totals.served;
    result.target += totals.target;
  }
  return result;
}

export type SitesAtRisk = { atRisk: number; notEvaluated: number; total: number };

/** Beneficiaries with ≥1 projected day of unmet units for the product; the rest that lack a complete series. */
export function sitesAtRisk(snapshot: ExplorerSnapshot, productId: string): SitesAtRisk {
  const sites = beneficiaries(snapshot);
  let atRisk = 0;
  let notEvaluated = 0;
  for (const site of sites) {
    const totals = seriesTotals(snapshot.projections[cellKey(site.id, productId)]);
    if (totals?.firstDeficit !== null && totals?.firstDeficit !== undefined) atRisk += 1;
    else if (!totals?.complete) notEvaluated += 1;
  }
  return { atRisk, notEvaluated, total: sites.length };
}

/** Products with any projected unmet at any beneficiary; the rest not fully evaluated. */
export function itemsAtRisk(snapshot: ExplorerSnapshot) {
  let atRisk = 0;
  let notEvaluated = 0;
  for (const product of snapshot.products) {
    const sites = sitesAtRisk(snapshot, product.id);
    if (sites.atRisk > 0) atRisk += 1;
    else if (sites.notEvaluated > 0) notEvaluated += 1;
  }
  return { atRisk, notEvaluated, total: snapshot.products.length };
}

/** Expired units on hand now for one product across every site; null when unknown. */
export function expiredOnHand(snapshot: ExplorerSnapshot, productId: string): { units: Quantity; lots: number; rows: number } {
  let units: Quantity = 0;
  let lots = 0;
  let rows = 0;
  for (const site of snapshot.sites) {
    const cell = snapshot.inventory[cellKey(site.id, productId)];
    if (!cell) continue;
    rows += 1;
    lots += cell.expired.lots;
    units = units === null || cell.expired.units === null ? null : units + cell.expired.units;
  }
  return { units: rows === 0 ? null : units, lots, rows };
}

export type ItemRisk = { product: Product; firstDeficit: number | null; target: number; served: number; unmet: number; evaluated: number; total: number };

/** One row per product. Sorted by first projected deficit, then name: a display sort only. */
export function itemRisk(snapshot: ExplorerSnapshot): ItemRisk[] {
  return snapshot.products
    .map((product) => {
      const fill = networkFill(snapshot, product.id);
      let firstDeficit: number | null = null;
      let unmet = 0;
      for (const site of beneficiaries(snapshot)) {
        const totals = seriesTotals(snapshot.projections[cellKey(site.id, product.id)]);
        if (!totals) continue;
        if (totals.firstDeficit !== null && (firstDeficit === null || totals.firstDeficit < firstDeficit)) firstDeficit = totals.firstDeficit;
        if (totals.complete) unmet += totals.unmet;
      }
      return { product, firstDeficit, target: fill.target, served: fill.served, unmet, evaluated: fill.evaluated, total: fill.total };
    })
    .sort((a, b) => (a.firstDeficit ?? Infinity) - (b.firstDeficit ?? Infinity) || a.product.name.localeCompare(b.product.name));
}

export type ChartRow = { date: string; demand: Quantity; eligibleEnd: Quantity; donations: Quantity; low: Quantity; high: Quantity };

export type ChartSeries = {
  rows: ChartRow[];
  /** Beneficiaries whose series enter the demand/stock sums, and the ones without a series. */
  included: Site[];
  excluded: Site[];
  donationSites: number;
  band: "network" | "none" | "quantiles" | "unknown";
};

function sumOrNull(values: Quantity[]): Quantity {
  if (values.length === 0) return null;
  let total = 0;
  for (const value of values) {
    if (value === null) return null;
    total += value;
  }
  return total;
}

/**
 * Daily demand forecast and eligible stock at day end, summed only within one product, plus forecast
 * donations. A day missing from any included series makes that day's sum missing, never zero.
 */
export function chartSeries(snapshot: ExplorerSnapshot, productId: string, scope: string): ChartSeries {
  const scoped = scope === "network" ? beneficiaries(snapshot) : beneficiaries(snapshot).filter((site) => site.id === scope);
  const included = scoped.filter((site) => snapshot.projections[cellKey(site.id, productId)]?.kind === "projected");
  const excluded = scoped.filter((site) => !included.includes(site));
  const detail = snapshot.forecastDetail;
  const donationSites = (scope === "network" ? snapshot.sites : scoped).filter((site) => detail.kind === "available" && detail.donations[cellKey(site.id, productId)]);
  const bandData = scope !== "network" && detail.kind === "available" ? detail.bands[cellKey(scope, productId)] : undefined;
  const band: ChartSeries["band"] = scope === "network" ? "network" : detail.kind !== "available" ? "unknown" : bandData ? "quantiles" : "none";

  const rows = snapshot.dates.map((date, index) => {
    const days = included.map((site) => {
      const projection = snapshot.projections[cellKey(site.id, productId)];
      return projection?.kind === "projected" ? projection.days[index] : null;
    });
    const donations = detail.kind === "available" && donationSites.length > 0
      ? sumOrNull(donationSites.map((site) => detail.donations[cellKey(site.id, productId)][index] ?? null))
      : null;
    return {
      date,
      demand: included.length > 0 ? sumOrNull(days.map((day) => day?.target ?? null)) : null,
      eligibleEnd: included.length > 0 ? sumOrNull(days.map((day) => day?.eligibleEnd ?? null)) : null,
      donations,
      low: bandData?.low[index] ?? null,
      high: bandData?.high[index] ?? null,
    };
  });
  return { rows, included, excluded, donationSites: donationSites.length, band };
}

/** Distinct providers across the run's series, with fallbacks listed per site and product. */
export function runMethods(snapshot: ExplorerSnapshot) {
  const providers = new Set<string>();
  const fallbacks: { site: Site; product: Product; provider: string; reason: string | null }[] = [];
  for (const site of beneficiaries(snapshot)) {
    for (const product of snapshot.products) {
      const projection = snapshot.projections[cellKey(site.id, product.id)];
      if (projection?.kind !== "projected" || !projection.method) continue;
      if (projection.method.fallbackUsed) fallbacks.push({ site, product, provider: projection.method.provider, reason: projection.method.fallbackReason });
      else providers.add(projection.method.provider);
    }
  }
  return { providers: [...providers], fallbacks };
}
