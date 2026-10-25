import { OverviewApiError, overviewApi, parseQuantity, type DashboardSummary, type ForecastCatalog, type InventorySnapshot, type ShortageProjection } from "@/lib/overview-api";
import { staticFixtureSnapshot } from "./static-fixture";
import type { ExpiringLots, LiveNotice, OverviewDataSource, OverviewSnapshot, Product, Quantity, Site, SiteProductProjection } from "./types";

// LiveOverviewSource maps the presenter APIs (dashboard summary, shortage projection, forecast catalog)
// onto the OverviewSnapshot view model. Quantities stay per product; nothing is summed across products.

export const LIVE_LABEL = "Live · simulated network";

const STALE_CODES = new Set(["FORECAST_HORIZON_ALREADY_STARTED", "FORECAST_UNIT_OR_CALENDAR_CHANGED", "FORECAST_NETWORK_SCOPE_CHANGED"]);

/** Simple display plural; the base unit itself is kept in accessible text. */
export function pluralize(unit: string) {
  if (/s$/i.test(unit)) return unit;
  if (/[^aeiou]y$/i.test(unit)) return `${unit.slice(0, -1)}ies`;
  return `${unit}s`;
}

function shortName(name: string) {
  return name.replace(/ Pantry$/, "").replace(/ Distribution Hub$/, " Hub");
}

function expiringWithin(row: InventorySnapshot | undefined, horizonEnd: string): ExpiringLots | null {
  if (!row) return null;
  let count = 0;
  let units = 0;
  for (const lot of row.lots) {
    // Usable, dated lots expiring on or before the horizon end; held/excluded lots never count.
    if (!lot.usable || lot.expiry_kind !== "DATED" || !lot.expires_on || lot.expires_on > horizonEnd) continue;
    const quantity = parseQuantity(lot.on_hand_quantity);
    if (quantity === null) return null;
    count += 1;
    units += quantity;
  }
  return { count, units };
}

function noticeReason(notice: LiveNotice) {
  if (notice.kind === "not_ready") return "No planning-ready forecast yet.";
  if (notice.kind === "stale") return `Stale forecast (${notice.code}); run a new forecast.`;
  return `${notice.code}: ${notice.message}`;
}

export function buildLiveSnapshot(summary: DashboardSummary, catalog: ForecastCatalog, shortage: ShortageProjection | null, notice: LiveNotice | null): OverviewSnapshot {
  const products: Product[] = catalog.products.map((product) => ({ id: product.id, name: product.name, unit: product.base_unit, unitPlural: pluralize(product.base_unit) }));
  // Beneficiaries first (catalog order), then hubs, matching the fixture's site list.
  const sites: Site[] = [...catalog.sites.filter((site) => site.role !== "HUB"), ...catalog.sites.filter((site) => site.role === "HUB")]
    .map((site) => ({ id: site.id, name: site.name, shortName: shortName(site.name), role: site.role }));
  const inventory = new Map(summary.inventory.map((row) => [`${row.site_id}|${row.product_id}`, row]));
  const projectionDays = shortage ? [...new Set(shortage.series.flatMap((series) => series.days.map((day) => day.day)))].sort() : [];
  // Local dates come from the shortage days; inventory-only views show the inventory's local date.
  const dates = projectionDays.length > 0 ? projectionDays : [summary.inventory[0]?.local_date ?? summary.observed_at.slice(0, 10)];
  const horizonEnd = dates[dates.length - 1];
  const timezone = catalog.sites[0]?.timezone ?? summary.inventory[0]?.timezone ?? "UTC";

  const projections: Record<string, Record<string, SiteProductProjection>> = {};
  for (const site of sites) {
    projections[site.id] = {};
    for (const product of products) {
      const row = inventory.get(`${site.id}|${product.id}`);
      const eligibleStockNow: Quantity = row ? parseQuantity(row.usable_quantity) : null;
      const expiringLots = expiringWithin(row, horizonEnd);
      let projection: SiteProductProjection;
      if (site.role === "HUB") {
        // The shortage projection covers beneficiaries only: no hub series and no donation outlook.
        projection = { kind: "hub", donationOutlook: null, eligibleStockNow, expiringLots };
      } else if (notice) {
        projection = { kind: "not_evaluated", reason: noticeReason(notice), eligibleStockNow, expiringLots };
      } else {
        const series = shortage?.series.find((item) => item.site_id === site.id && item.product_id === product.id);
        if (!series) {
          projection = { kind: "not_evaluated", reason: "No shortage series for this site and product in the latest forecast.", eligibleStockNow, expiringLots };
        } else if (series.base_unit !== product.unit) {
          projection = { kind: "not_evaluated", reason: `The series unit (${series.base_unit}) does not match the product's base unit (${product.unit}).`, eligibleStockNow, expiringLots };
        } else {
          const byDay = new Map(series.days.map((day) => [day.day, day]));
          const days = dates.map((date) => byDay.get(date));
          const demand = days.map((day) => parseQuantity(day?.demand));
          const served = days.map((day) => parseQuantity(day?.served));
          const unmet = days.map((day) => parseQuantity(day?.unmet));
          if ([...demand, ...served, ...unmet].some((value) => value === null)) {
            projection = { kind: "not_evaluated", reason: "A projected quantity is missing or outside the safe display range.", eligibleStockNow, expiringLots };
          } else {
            projection = {
              kind: "projected",
              targetUnits: demand as number[],
              servedUnits: served as number[],
              unmetUnits: unmet as number[],
              demandOutlook: demand as number[],
              donationOutlook: null,
              eligibleStockNow,
              eligibleStockAtHorizonEnd: parseQuantity(days[days.length - 1]?.eligible_end),
              expiringLots,
              provider: series.actual_provider,
            };
          }
        }
      }
      projections[site.id][product.id] = projection;
    }
  }

  const forecast = summary.latest_forecast;
  return {
    snapshotId: shortage?.forecast_run_id ?? `inventory-${summary.observed_at}`,
    source: {
      kind: "live",
      observedAt: shortage?.observed_at ?? summary.observed_at,
      forecastRunId: forecast?.id ?? null,
      forecastRecordedAt: forecast?.recorded_at ?? null,
      providers: shortage ? [...new Set(shortage.series.map((series) => series.actual_provider))] : [],
      warnings: shortage?.warnings ?? [],
      notice,
    },
    provenance: { classification: "SIMULATED", label: LIVE_LABEL, fixtureId: forecast?.id ?? "none", sourceDataset: "presenter API" },
    timezone,
    dates,
    products,
    sites,
    projections,
  };
}

/** Presenter data only; rejects with OverviewApiError (401/403 for visitors, 5xx or network errors otherwise). */
export const liveOverviewSource: OverviewDataSource = {
  id: "live-presenter",
  async load(signal) {
    const [summary, catalog] = await Promise.all([overviewApi.summary(signal), overviewApi.catalog(signal)]);
    const latest = summary.latest_forecast;
    if (!latest || !latest.planning_ready) return buildLiveSnapshot(summary, catalog, null, { kind: "not_ready", recordedAt: latest?.recorded_at ?? null });
    try {
      const shortage = await overviewApi.shortages(latest.id, signal);
      return buildLiveSnapshot(summary, catalog, shortage, null);
    } catch (error) {
      if (error instanceof OverviewApiError && error.status === 409) {
        if (error.code === "DEMAND_FORECAST_UNAVAILABLE") return buildLiveSnapshot(summary, catalog, null, { kind: "demand_unavailable", code: error.code, message: error.message });
        if (STALE_CODES.has(error.code) || error.code.startsWith("FORECAST_")) return buildLiveSnapshot(summary, catalog, null, { kind: "stale", code: error.code, recordedAt: latest.recorded_at });
      }
      throw error;
    }
  },
};

/**
 * Live data for presenters; the labelled static fixture otherwise. 401/403 → visitor fallback; any other
 * failure → fixture with an "unavailable" reason so the screen can offer Retry. Never mixes the two.
 */
export const liveWithFallbackSource: OverviewDataSource = {
  id: "live-with-fixture-fallback",
  async load(signal) {
    try {
      return await liveOverviewSource.load(signal);
    } catch (error) {
      if (signal.aborted || (error instanceof DOMException && error.name === "AbortError")) throw error;
      const status = error instanceof OverviewApiError ? error.status : 0;
      const code = error instanceof OverviewApiError ? error.code : "NETWORK_ERROR";
      return { ...staticFixtureSnapshot, fallback: status === 401 || status === 403 ? { kind: "visitor", status } : { kind: "unavailable", code, status } };
    }
  },
};
