// View model for the Overview / Network Atlas. These are presentation types, not API contracts:
// a future adapter maps generated backend types onto them without changing the screen.

export type SiteRole = "BENEFICIARY" | "HUB";

export type Product = {
  id: string;
  name: string;
  /** Base unit, singular (e.g. "meal"). */
  unit: string;
  unitPlural: string;
};

export type Site = {
  id: string;
  name: string;
  /** Short label for crowded surfaces (map markers, site list). */
  shortName: string;
  role: SiteRole;
};

export type ExpiringLots = { count: number; units: number };

/**
 * The provider that actually produced a live series. A provider name alone never implies a fallback:
 * `fallbackUsed` says whether the requested method failed and another one filled in.
 */
export type ForecastMethod = { provider: string; fallbackUsed: boolean; fallbackReason: string | null };
export type SeriesMethod = ForecastMethod & { siteId: string; productId: string };

/** A quantity in the product's base unit, or null when unavailable (malformed or beyond the safe integer range). */
export type Quantity = number | null;

/** Daily series align index-for-index with `OverviewSnapshot.dates`. Units are the product's base unit. */
export type BeneficiaryProjection = {
  kind: "projected";
  /** Forecast-derived target units per day. */
  targetUnits: number[];
  servedUnits: number[];
  unmetUnits: number[];
  demandOutlook: number[];
  /** null: not in this projection (the live shortage projection has demand and physical stock only). */
  donationOutlook: number[] | null;
  eligibleStockNow: Quantity;
  eligibleStockAtHorizonEnd: Quantity;
  /** null when a lot quantity is unavailable. */
  expiringLots: ExpiringLots | null;
  /** How this series was forecast (live data only). */
  method?: ForecastMethod;
};

export type HubProjection = {
  kind: "hub";
  donationOutlook: number[] | null;
  eligibleStockNow: Quantity;
  /** Assumes no transfers: no plan is saved. Undefined: not in this projection (the hub has no series). */
  eligibleStockAtHorizonEnd?: Quantity;
  expiringLots: ExpiringLots | null;
};

export type InsufficientProjection = {
  kind: "insufficient_data";
  reason: string;
  /** Known current stock, or null when stock is unknown too. Never a projection. */
  eligibleStockNow: number | null;
};

/** No status. Live data may still carry current inventory for the site and product. */
export type NotEvaluatedProjection = { kind: "not_evaluated"; reason: string; eligibleStockNow?: Quantity; expiringLots?: ExpiringLots | null };

export type SiteProductProjection = BeneficiaryProjection | HubProjection | InsufficientProjection | NotEvaluatedProjection;

export type OverviewProvenance = {
  classification: "SIMULATED";
  /** Shown verbatim wherever the data is displayed. */
  label: string;
  fixtureId: string;
  sourceDataset: string;
};

export type StaleCode = "FORECAST_HORIZON_ALREADY_STARTED" | "FORECAST_UNIT_OR_CALENDAR_CHANGED" | "FORECAST_NETWORK_SCOPE_CHANGED";

/** Why live statuses are missing even though presenter data loaded. The UI supplies its own copy per kind/code. */
export type LiveNotice =
  | { kind: "not_ready"; recordedAt: string | null; code?: "FORECAST_NOT_PLANNING_READY" }
  | { kind: "stale"; code: StaleCode; recordedAt: string }
  | { kind: "integrity"; code: "FORECAST_INTEGRITY_FAILED"; recordedAt: string }
  | { kind: "demand_unavailable"; code: "DEMAND_FORECAST_UNAVAILABLE"; recordedAt: string };

/** Which source the screen is showing. Fixture and live data are never mixed in one snapshot. */
export type SnapshotSource =
  | { kind: "fixture" }
  | { kind: "live"; observedAt: string; forecastRunId: string | null; forecastRecordedAt: string | null; methods: SeriesMethod[]; warnings: string[]; notice: LiveNotice | null };

/** Set when the static fixture is shown because live data was not available. */
export type FallbackReason = { kind: "visitor"; status: number } | { kind: "unavailable"; code: string; status: number };

export type OverviewSnapshot = {
  snapshotId: string;
  source: SnapshotSource;
  fallback?: FallbackReason;
  provenance: OverviewProvenance;
  timezone: string;
  /** Consecutive local dates, ISO yyyy-mm-dd (seven for a projection; inventory-only views may have one). */
  dates: string[];
  products: Product[];
  sites: Site[];
  /** projections[siteId][productId] */
  projections: Record<string, Record<string, SiteProductProjection>>;
  /** Set when the snapshot carries no projection at all. */
  emptyReason?: string;
};

/** The page reads only through this adapter. A real API adapter replaces the static fixture later. */
export interface OverviewDataSource {
  readonly id: string;
  load(signal: AbortSignal): Promise<OverviewSnapshot>;
}

export type BeneficiaryStatus = "shortfall" | "watch" | "covered" | "not_evaluated";
export type MarkerStatus = BeneficiaryStatus | "hub";
