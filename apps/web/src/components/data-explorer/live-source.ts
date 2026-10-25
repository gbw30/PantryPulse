import { OverviewApiError, overviewApi, parseQuantity, type DashboardSummary, type ForecastCatalog, type InventorySnapshot, type ShortageProjection } from "@/lib/overview-api";
import { ApiError, planningApi, type Schema } from "@/lib/planning-api";
import { fixtureSnapshot } from "./fixture";
import { isStaleCode, noticeReason, pluralize, shortName } from "./format";
import { cellKey } from "./metrics";
import type { Band, ExplorerDataSource, ExplorerNotice, ExplorerSnapshot, ForecastDetail, InventoryCell, LotTally, Product, Quantity, SeriesProjection, Site } from "./types";

// Maps the read APIs onto the Data Explorer view model. Each read is handled on its own:
// catalog/summary 401|403 → the labelled fixture; shortages failures → a notice over live inventory;
// the forecast read (donations, quantiles) failing → only that detail is unavailable.

const isAbort = (error: unknown) => error instanceof DOMException && error.name === "AbortError";

function abortIfNeeded(signal: AbortSignal) {
  if (signal.aborted) throw new DOMException("Aborted", "AbortError");
}

function statusOf(error: unknown) {
  if (error instanceof OverviewApiError) return { status: error.status, code: error.code };
  if (error instanceof ApiError) return { status: error.status, code: error.code };
  return { status: 0, code: "NETWORK_ERROR" };
}

function tally(lots: InventorySnapshot["lots"]): LotTally {
  let units: Quantity = 0;
  for (const lot of lots) {
    const quantity = parseQuantity(lot.on_hand_quantity);
    units = units === null || quantity === null ? null : units + quantity;
  }
  return { lots: lots.length, units };
}

export function inventoryCell(row: InventorySnapshot): InventoryCell {
  return {
    usable: parseQuantity(row.usable_quantity),
    onHand: parseQuantity(row.on_hand_quantity),
    eligible: tally(row.lots.filter((lot) => lot.usable)),
    held: tally(row.lots.filter((lot) => !lot.usable && lot.exclusion_reason === "HELD")),
    expired: tally(row.lots.filter((lot) => !lot.usable && lot.exclusion_reason === "EXPIRED")),
    otherExcluded: tally(row.lots.filter((lot) => !lot.usable && lot.exclusion_reason !== "HELD" && lot.exclusion_reason !== "EXPIRED")),
    localDate: row.local_date,
  };
}

/** 409s from the shortage read that still leave live inventory worth showing. */
export function noticeFor409(code: string, recordedAt: string): ExplorerNotice | null {
  if (isStaleCode(code)) return { kind: "stale", code, recordedAt };
  if (code === "FORECAST_NOT_PLANNING_READY") return { kind: "not_ready", code, recordedAt };
  if (code === "FORECAST_INTEGRITY_FAILED") return { kind: "integrity", code, recordedAt };
  if (code === "DEMAND_FORECAST_UNAVAILABLE") return { kind: "demand_unavailable", code, recordedAt };
  return null;
}

function forecastDetail(result: Schema["ForecastResult"], dates: string[], products: Product[]): ForecastDetail {
  const donations: Record<string, Quantity[]> = {};
  const demandInterval: Record<string, "NONE" | "MODEL_QUANTILES"> = {};
  const bands: Record<string, Band> = {};
  const finite = (value: number | null | undefined): Quantity => (typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null);
  for (const series of result.forecast.series) {
    const { site_id: siteId, product_id: productId, target_type: target } = series.scope.key;
    const product = products.find((item) => item.id === productId);
    // A series in another unit than the product's base unit is never plotted with it.
    if (!product || series.scope.unit !== product.unit || series.status !== "AVAILABLE") continue;
    const byDay = new Map(series.points.map((point) => [point.day, point]));
    const key = cellKey(siteId, productId);
    if (target === "DONATION") {
      donations[key] = dates.map((date) => finite(byDay.get(date)?.central_estimate));
      continue;
    }
    const points = dates.map((date) => byDay.get(date));
    const quantiles = points.length > 0 && points.every((point) => point?.interval_method === "MODEL_QUANTILES" && finite(point.p10) !== null && finite(point.p90) !== null);
    demandInterval[key] = quantiles ? "MODEL_QUANTILES" : "NONE";
    if (quantiles) bands[key] = { low: points.map((point) => finite(point?.p10)), high: points.map((point) => finite(point?.p90)) };
  }
  return { kind: "available", donations, demandInterval, bands };
}

export function buildLiveSnapshot(
  summary: DashboardSummary,
  catalog: ForecastCatalog,
  shortage: ShortageProjection | null,
  notice: ExplorerNotice | null,
  detail: ForecastDetail,
): ExplorerSnapshot {
  const products: Product[] = catalog.products.map((product) => ({ id: product.id, name: product.name, unit: product.base_unit, unitPlural: pluralize(product.base_unit) }));
  const sites: Site[] = [...catalog.sites.filter((site) => site.role !== "HUB"), ...catalog.sites.filter((site) => site.role === "HUB")]
    .map((site) => ({ id: site.id, name: site.name, shortName: shortName(site.name), role: site.role }));
  const dates = shortage ? [...new Set(shortage.series.flatMap((series) => series.days.map((day) => day.day)))].sort() : [];

  const inventory: Record<string, InventoryCell> = {};
  for (const row of summary.inventory) inventory[cellKey(row.site_id, row.product_id)] = inventoryCell(row);

  const projections: Record<string, SeriesProjection> = {};
  for (const site of sites.filter((item) => item.role === "BENEFICIARY")) {
    for (const product of products) {
      const key = cellKey(site.id, product.id);
      if (notice) { projections[key] = { kind: "not_evaluated", reason: noticeReason(notice) }; continue; }
      const series = shortage?.series.find((item) => item.site_id === site.id && item.product_id === product.id);
      if (!series) { projections[key] = { kind: "not_evaluated", reason: "No shortage series for this site and product in the latest forecast." }; continue; }
      if (series.base_unit !== product.unit) { projections[key] = { kind: "not_evaluated", reason: `The series unit (${series.base_unit}) does not match the product's base unit (${product.unit}).` }; continue; }
      const byDay = new Map(series.days.map((day) => [day.day, day]));
      projections[key] = {
        kind: "projected",
        method: { provider: series.actual_provider, fallbackUsed: series.fallback_used, fallbackReason: series.fallback_reason },
        days: dates.map((date) => {
          const day = byDay.get(date);
          return day ? { target: parseQuantity(day.demand), served: parseQuantity(day.served), unmet: parseQuantity(day.unmet), eligibleEnd: parseQuantity(day.eligible_end) } : null;
        }),
      };
    }
  }

  const latest = summary.latest_forecast;
  return {
    source: {
      kind: "live",
      observedAt: shortage?.observed_at ?? summary.observed_at,
      forecast: latest ? { runId: latest.id, jobId: latest.job_id, recordedAt: latest.recorded_at, planningReady: latest.planning_ready } : null,
      warnings: shortage?.warnings ?? [],
      notice,
      sourceNames: catalog.sources.map((source) => `${source.name} (${source.classification})`),
    },
    timezone: catalog.sites[0]?.timezone ?? summary.inventory[0]?.timezone ?? "UTC",
    dates,
    products,
    sites,
    projections,
    inventory,
    inventoryRows: summary.inventory.length,
    forecastDetail: detail,
  };
}

export const liveExplorerSource: ExplorerDataSource = {
  id: "live-with-fixture-fallback",
  async load(signal, onUnauthorized) {
    let summary: DashboardSummary;
    let catalog: ForecastCatalog;
    try {
      [summary, catalog] = await Promise.all([overviewApi.summary(signal), overviewApi.catalog(signal)]);
    } catch (error) {
      if (isAbort(error) || signal.aborted) throw error;
      const { status } = statusOf(error);
      if (status === 401 || status === 403) {
        if (status === 401) onUnauthorized();
        return fixtureSnapshot(status);
      }
      throw error;
    }

    const latest = summary.latest_forecast;
    if (!latest || !latest.planning_ready) {
      return buildLiveSnapshot(summary, catalog, null, { kind: "not_ready", recordedAt: latest?.recorded_at ?? null }, { kind: "unavailable", reason: "no_forecast" });
    }

    // Both reads run together; each failure is classified on its own.
    const [shortageRead, forecastRead] = await Promise.allSettled([overviewApi.shortages(latest.id, signal), planningApi.forecast(latest.job_id)]);
    abortIfNeeded(signal);

    let shortage: ShortageProjection | null = null;
    let notice: ExplorerNotice | null = null;
    if (shortageRead.status === "fulfilled") shortage = shortageRead.value;
    else {
      if (isAbort(shortageRead.reason)) throw shortageRead.reason;
      const { status, code } = statusOf(shortageRead.reason);
      if (status === 401) onUnauthorized();
      notice = status === 409 ? noticeFor409(code, latest.recorded_at) : null;
      notice ??= status === 401 || status === 403 ? { kind: "projection_visitor", code, recordedAt: latest.recorded_at } : { kind: "projection_unavailable", code, recordedAt: latest.recorded_at };
    }

    const dates = shortage ? [...new Set(shortage.series.flatMap((series) => series.days.map((day) => day.day)))].sort() : [];
    const products: Product[] = catalog.products.map((product) => ({ id: product.id, name: product.name, unit: product.base_unit, unitPlural: pluralize(product.base_unit) }));
    let detail: ForecastDetail;
    if (forecastRead.status === "fulfilled") detail = forecastDetail(forecastRead.value, dates, products);
    else {
      const { status, code } = statusOf(forecastRead.reason);
      if (status === 401) onUnauthorized();
      detail = { kind: "unavailable", reason: status === 401 || status === 403 ? "visitor" : "error", code };
    }
    return buildLiveSnapshot(summary, catalog, shortage, notice, detail);
  },
};
