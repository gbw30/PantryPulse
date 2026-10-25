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

/** Daily series align index-for-index with `OverviewSnapshot.dates`. Units are the product's base unit. */
export type BeneficiaryProjection = {
  kind: "projected";
  /** Forecast-derived target units per day. */
  targetUnits: number[];
  servedUnits: number[];
  unmetUnits: number[];
  demandOutlook: number[];
  donationOutlook: number[];
  eligibleStockNow: number;
  eligibleStockAtHorizonEnd: number;
  expiringLots: ExpiringLots;
};

export type HubProjection = {
  kind: "hub";
  donationOutlook: number[];
  eligibleStockNow: number;
  /** Assumes no transfers: no plan is saved. */
  eligibleStockAtHorizonEnd: number;
  expiringLots: ExpiringLots;
};

export type InsufficientProjection = {
  kind: "insufficient_data";
  reason: string;
  /** Known current stock, or null when stock is unknown too. Never a projection. */
  eligibleStockNow: number | null;
};

export type NotEvaluatedProjection = { kind: "not_evaluated"; reason: string };

export type SiteProductProjection = BeneficiaryProjection | HubProjection | InsufficientProjection | NotEvaluatedProjection;

export type OverviewProvenance = {
  classification: "SIMULATED";
  /** Shown verbatim wherever the data is displayed. */
  label: string;
  fixtureId: string;
  sourceDataset: string;
};

export type OverviewSnapshot = {
  snapshotId: string;
  provenance: OverviewProvenance;
  timezone: string;
  /** Seven consecutive local dates, ISO yyyy-mm-dd. */
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
