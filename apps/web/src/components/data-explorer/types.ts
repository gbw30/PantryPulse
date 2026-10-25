// View model for the Data Explorer. Presentation types only, not API contracts: the live adapter maps
// generated contract types onto them and the SIMULATED fixture fills the same shape. Quantities stay
// per product in the product's base unit; nothing here sums across products.

export type SiteRole = "BENEFICIARY" | "HUB";

export type Product = { id: string; name: string; /** Base unit, singular. */ unit: string; unitPlural: string };

export type Site = { id: string; name: string; shortName: string; role: SiteRole };

/** A quantity in the product's base unit; null when malformed or beyond the safe integer range. */
export type Quantity = number | null;

/** The provider that actually produced a series; `fallbackUsed` says whether another method filled in. */
export type ForecastMethod = { provider: string; fallbackUsed: boolean; fallbackReason: string | null };

/** One projected day: forecast-derived target, projected service, unmet and eligible stock at day end. */
export type ProjectedDay = { target: Quantity; served: Quantity; unmet: Quantity; eligibleEnd: Quantity };

/**
 * Beneficiary × product projection. `days` aligns with `ExplorerSnapshot.dates`; a null entry means
 * the day is missing from the series (never zero).
 */
export type SeriesProjection =
  | { kind: "projected"; days: (ProjectedDay | null)[]; method: ForecastMethod | null }
  | { kind: "not_evaluated"; reason: string };

export type LotTally = { lots: number; units: Quantity };

/** Current inventory for one site × product, from the snapshot's lots. */
export type InventoryCell = {
  usable: Quantity;
  onHand: Quantity;
  eligible: LotTally;
  held: LotTally;
  expired: LotTally;
  /** Ineligible or unknown eligibility/expiry lots. */
  otherExcluded: LotTally;
  localDate: string;
};

/** Model quantiles (p10/p90) for one site's demand series. Raw quantiles, not calibrated intervals. */
export type Band = { low: Quantity[]; high: Quantity[] };

export type ForecastDetail =
  | {
      kind: "available";
      /** Donation forecasts keyed `${siteId}|${productId}`, aligned with dates. */
      donations: Record<string, Quantity[]>;
      demandInterval: Record<string, "NONE" | "MODEL_QUANTILES">;
      bands: Record<string, Band>;
    }
  | { kind: "unavailable"; reason: "visitor" | "error" | "no_forecast"; code?: string };

export type StaleCode = "FORECAST_HORIZON_ALREADY_STARTED" | "FORECAST_UNIT_OR_CALENDAR_CHANGED" | "FORECAST_NETWORK_SCOPE_CHANGED";

/** Why projections are missing although live inventory loaded. */
export type ExplorerNotice =
  | { kind: "not_ready"; recordedAt: string | null; code?: "FORECAST_NOT_PLANNING_READY" }
  | { kind: "stale"; code: StaleCode; recordedAt: string }
  | { kind: "integrity"; code: "FORECAST_INTEGRITY_FAILED"; recordedAt: string }
  | { kind: "demand_unavailable"; code: "DEMAND_FORECAST_UNAVAILABLE"; recordedAt: string }
  | { kind: "projection_visitor"; code: string; recordedAt: string }
  | { kind: "projection_unavailable"; code: string; recordedAt: string };

export type LiveForecast = { runId: string; jobId: string; recordedAt: string; planningReady: boolean };

/** Which source the screen shows. Live and fixture data are never mixed in one snapshot. */
export type ExplorerSource =
  | { kind: "live"; observedAt: string; forecast: LiveForecast | null; warnings: string[]; notice: ExplorerNotice | null; sourceNames: string[] }
  | { kind: "fixture"; status: number };

export type ExplorerSnapshot = {
  source: ExplorerSource;
  timezone: string;
  /** Projection local dates (seven), or empty when no projection was read. */
  dates: string[];
  products: Product[];
  /** Beneficiaries first, then hubs. */
  sites: Site[];
  /** Beneficiaries only, keyed `${siteId}|${productId}`. */
  projections: Record<string, SeriesProjection>;
  /** Every site, keyed `${siteId}|${productId}`; absent when the snapshot has no row. */
  inventory: Record<string, InventoryCell>;
  inventoryRows: number;
  forecastDetail: ForecastDetail;
};

/** The screen reads only through this adapter. */
export interface ExplorerDataSource {
  readonly id: string;
  /** `onUnauthorized` runs on any 401 so the shell can mark the presenter session expired. */
  load(signal: AbortSignal, onUnauthorized: () => void): Promise<ExplorerSnapshot>;
}

export type SiteStatus = "shortfall" | "watch" | "covered" | "not_evaluated";
export type MarkStatus = SiteStatus | "hub";
