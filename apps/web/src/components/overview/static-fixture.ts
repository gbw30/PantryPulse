import type {
  BeneficiaryProjection,
  HubProjection,
  OverviewDataSource,
  OverviewSnapshot,
  Product,
  Site,
  SiteProductProjection,
} from "./types";

// SIMULATED — static design fixture, not model output.
// Site names, roles, products and units mirror data/demo/forecasting-v1.json (forecasting-core-demo-v1).
// Its history starts 2026-07-26 and runs 90 days, so the seven local horizon dates begin 2026-10-24.
// Every quantity below is authored for the design and exercises each legend state; none is a forecast.

export const STATIC_FIXTURE_LABEL = "SIMULATED — static design fixture, not model output";

const DATES = ["2026-10-24", "2026-10-25", "2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30"];

const PRODUCTS: Product[] = [
  { id: "shelf-stable-meals", name: "Shelf-stable meals", unit: "meal", unitPlural: "meals" },
  { id: "bottled-water", name: "Bottled water", unit: "bottle", unitPlural: "bottles" },
];

const SITES: Site[] = [
  { id: "riverbend", name: "Riverbend Pantry", shortName: "Riverbend", role: "BENEFICIARY" },
  { id: "oak-terrace", name: "Oak Terrace Pantry", shortName: "Oak Terrace", role: "BENEFICIARY" },
  { id: "cedar-grove", name: "Cedar Grove Pantry", shortName: "Cedar Grove", role: "BENEFICIARY" },
  { id: "maple-crossing", name: "Maple Crossing Pantry", shortName: "Maple Crossing", role: "BENEFICIARY" },
  { id: "willow-creek", name: "Willow Creek Pantry", shortName: "Willow Creek", role: "BENEFICIARY" },
  { id: "pine-ridge", name: "Pine Ridge Pantry", shortName: "Pine Ridge", role: "BENEFICIARY" },
  { id: "gator-hub", name: "Gator Distribution Hub", shortName: "Gator Hub", role: "HUB" },
];

/** A lot of eligible stock. `lastUsableDay` is a horizon index; null means usable beyond the horizon. */
type Lot = { units: number; lastUsableDay: number | null };
type Seed = { lots: Lot[]; demand: number[]; donation: number[] };

/**
 * Fixture arithmetic only (no forecasting or optimisation): donations arrive each morning as
 * long-dated lots, demand is served first-expiry-first-out, and lots past their last usable day leave
 * eligible stock. Unmet units are demand that stock could not cover; no transfer is assumed.
 */
function projectFixture(seed: Seed) {
  let lots = seed.lots.map((lot) => ({ ...lot }));
  const served: number[] = [];
  const unmet: number[] = [];
  seed.demand.forEach((demand, day) => {
    if (seed.donation[day] > 0) lots.push({ units: seed.donation[day], lastUsableDay: null });
    lots.sort((a, b) => (a.lastUsableDay ?? Infinity) - (b.lastUsableDay ?? Infinity));
    let remaining = demand;
    for (const lot of lots) {
      const take = Math.min(lot.units, remaining);
      lot.units -= take;
      remaining -= take;
    }
    served.push(demand - remaining);
    unmet.push(remaining);
    lots = lots.filter((lot) => lot.units > 0 && lot.lastUsableDay !== day);
  });
  const expiring = seed.lots.filter((lot) => lot.lastUsableDay !== null && lot.lastUsableDay < DATES.length);
  return {
    served,
    unmet,
    stockNow: seed.lots.reduce((sum, lot) => sum + lot.units, 0),
    stockEnd: lots.reduce((sum, lot) => sum + lot.units, 0),
    expiringLots: { count: expiring.length, units: expiring.reduce((sum, lot) => sum + lot.units, 0) },
  };
}

function beneficiary(seed: Seed): BeneficiaryProjection {
  const result = projectFixture(seed);
  return {
    kind: "projected",
    targetUnits: [...seed.demand],
    servedUnits: result.served,
    unmetUnits: result.unmet,
    demandOutlook: [...seed.demand],
    donationOutlook: [...seed.donation],
    eligibleStockNow: result.stockNow,
    eligibleStockAtHorizonEnd: result.stockEnd,
    expiringLots: result.expiringLots,
  };
}

function hub(lots: Lot[], donation: number[]): HubProjection {
  const result = projectFixture({ lots, demand: donation.map(() => 0), donation });
  return {
    kind: "hub",
    donationOutlook: [...donation],
    eligibleStockNow: result.stockNow,
    eligibleStockAtHorizonEnd: result.stockEnd,
    expiringLots: result.expiringLots,
  };
}

const MEALS = "shelf-stable-meals";
const WATER = "bottled-water";

const PROJECTIONS: Record<string, Record<string, SiteProductProjection>> = {
  // Meals: shortfall from the first day. Water: covered.
  riverbend: {
    [MEALS]: beneficiary({ lots: [{ units: 40, lastUsableDay: 3 }], demand: [70, 72, 68, 75, 80, 66, 60], donation: [10, 15, 10, 20, 10, 15, 10] }),
    [WATER]: beneficiary({ lots: [{ units: 400, lastUsableDay: null }], demand: [48, 50, 52, 50, 49, 51, 50], donation: [0, 24, 0, 24, 0, 24, 0] }),
  },
  // Meals: watch (deficit on day 4). Water: shortfall from the first day.
  "oak-terrace": {
    [MEALS]: beneficiary({ lots: [{ units: 120, lastUsableDay: 5 }, { units: 60, lastUsableDay: null }], demand: [55, 58, 60, 62, 64, 60, 58], donation: [5, 5, 5, 5, 0, 0, 5] }),
    [WATER]: beneficiary({ lots: [{ units: 30, lastUsableDay: null }], demand: [60, 62, 58, 64, 60, 61, 59], donation: [12, 12, 12, 12, 12, 12, 12] }),
  },
  // Meals: covered with an expiring lot. Water: watch (deficit on day 5).
  "cedar-grove": {
    [MEALS]: beneficiary({ lots: [{ units: 30, lastUsableDay: 2 }, { units: 300, lastUsableDay: null }], demand: [40, 42, 38, 45, 44, 40, 41], donation: [10, 10, 10, 10, 10, 10, 10] }),
    [WATER]: beneficiary({ lots: [{ units: 180, lastUsableDay: null }], demand: [40, 42, 44, 45, 46, 44, 42], donation: [0, 0, 12, 0, 0, 12, 0] }),
  },
  // Meals: covered. Water: watch on the first day, shortfall from day 2.
  "maple-crossing": {
    [MEALS]: beneficiary({ lots: [{ units: 25, lastUsableDay: 4 }, { units: 200, lastUsableDay: null }], demand: [30, 31, 29, 30, 32, 30, 28], donation: [10, 10, 10, 10, 10, 10, 10] }),
    [WATER]: beneficiary({ lots: [{ units: 70, lastUsableDay: null }], demand: [55, 58, 56, 57, 55, 54, 56], donation: [0, 0, 0, 0, 0, 0, 0] }),
  },
  // Meals: watch (deficit on day 6). Water: covered with a lot expiring on day 2.
  "willow-creek": {
    [MEALS]: beneficiary({ lots: [{ units: 185, lastUsableDay: null }], demand: [35, 38, 36, 40, 42, 45, 40], donation: [5, 0, 5, 0, 5, 0, 5] }),
    [WATER]: beneficiary({ lots: [{ units: 48, lastUsableDay: 1 }, { units: 360, lastUsableDay: null }], demand: [45, 44, 46, 45, 47, 44, 45], donation: [0, 0, 0, 0, 0, 0, 0] }),
  },
  // Meals: shortfall on the first day only, then covered after a large donation (a later selected day
  // must not show the earlier deficit). Water: insufficient data — no projection, never shown as covered.
  "pine-ridge": {
    [MEALS]: beneficiary({ lots: [{ units: 10, lastUsableDay: 0 }, { units: 8, lastUsableDay: null }], demand: [32, 34, 30, 33, 35, 31, 30], donation: [0, 120, 0, 90, 0, 60, 0] }),
    [WATER]: {
      kind: "insufficient_data",
      reason: "Too few recent bottled-water demand observations to project this site.",
      eligibleStockNow: 96,
    },
  },
  "gator-hub": {
    [MEALS]: hub([{ units: 120, lastUsableDay: 6 }, { units: 900, lastUsableDay: null }], [80, 0, 120, 0, 60, 0, 90]),
    [WATER]: hub([{ units: 1200, lastUsableDay: null }], [0, 240, 0, 0, 240, 0, 0]),
  },
};

const PROVENANCE = {
  classification: "SIMULATED" as const,
  label: STATIC_FIXTURE_LABEL,
  fixtureId: "overview-static-v1",
  sourceDataset: "forecasting-core-demo-v1",
};

export const staticFixtureSnapshot: OverviewSnapshot = {
  snapshotId: "overview-static-v1",
  provenance: PROVENANCE,
  timezone: "America/New_York",
  dates: DATES,
  products: PRODUCTS,
  sites: SITES,
  projections: PROJECTIONS,
};

const EMPTY_REASON = "No projection is available for this snapshot. Every site is shown as Not evaluated until projections are saved.";

export const emptyFixtureSnapshot: OverviewSnapshot = {
  snapshotId: "overview-static-empty-v1",
  provenance: { ...PROVENANCE, fixtureId: "overview-static-empty-v1" },
  timezone: "America/New_York",
  dates: DATES,
  products: PRODUCTS,
  sites: SITES,
  projections: Object.fromEntries(SITES.map((site) => [site.id, Object.fromEntries(PRODUCTS.map((product) => [product.id, { kind: "not_evaluated", reason: "No projection in this snapshot." }]))])),
  emptyReason: EMPTY_REASON,
};

function abortError() {
  return new DOMException("The snapshot request was cancelled.", "AbortError");
}

function resolved(snapshot: OverviewSnapshot, id: string): OverviewDataSource {
  return {
    id,
    load: (signal) => (signal.aborted ? Promise.reject(abortError()) : Promise.resolve(snapshot)),
  };
}

export const staticFixtureSource = resolved(staticFixtureSnapshot, "static-fixture");
export const emptyFixtureSource = resolved(emptyFixtureSnapshot, "static-fixture-empty");

/** Design-state preview: the adapter fails. The screen must show an alert and no data. */
export const unavailableSource: OverviewDataSource = {
  id: "static-fixture-unavailable",
  load: () => Promise.reject(new Error("The static fixture adapter is configured to fail for this design-state preview.")),
};

/** Design-state preview: the request never settles, so the loading state stays visible. */
export const pendingSource: OverviewDataSource = {
  id: "static-fixture-loading",
  load: (signal) => new Promise((_, reject) => signal.addEventListener("abort", () => reject(abortError()), { once: true })),
};

export const OVERVIEW_STATE_PREVIEWS = {
  empty: emptyFixtureSource,
  unavailable: unavailableSource,
  loading: pendingSource,
} as const;

export type OverviewStatePreview = keyof typeof OVERVIEW_STATE_PREVIEWS;

export function overviewSourceFor(preview: string | undefined): { source: OverviewDataSource; preview: OverviewStatePreview | null } {
  if (preview && preview in OVERVIEW_STATE_PREVIEWS) {
    const key = preview as OverviewStatePreview;
    return { source: OVERVIEW_STATE_PREVIEWS[key], preview: key };
  }
  return { source: staticFixtureSource, preview: null };
}
