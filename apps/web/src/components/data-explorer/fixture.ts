import { cellKey } from "./metrics";
import type { ExplorerSnapshot, InventoryCell, Product, ProjectedDay, Quantity, SeriesProjection, Site } from "./types";

// SIMULATED — static design fixture, not model output. Shown to visitors when the read APIs answer
// 401/403. Site names, roles, products and units mirror data/demo/forecasting-v1.json; every quantity is
// authored for the design (no forecast, no optimisation) and exercises each state.

const DATES = ["2026-10-24", "2026-10-25", "2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30"];

const PRODUCTS: Product[] = [
  { id: "shelf-stable-meals", name: "Shelf-stable meals", unit: "meal", unitPlural: "meals" },
  { id: "bottled-water", name: "Bottled water", unit: "bottle", unitPlural: "bottles" },
];
const [MEALS, WATER] = PRODUCTS.map((product) => product.id);

const SITES: Site[] = [
  { id: "riverbend", name: "Riverbend Pantry", shortName: "Riverbend", role: "BENEFICIARY" },
  { id: "oak-terrace", name: "Oak Terrace Pantry", shortName: "Oak Terrace", role: "BENEFICIARY" },
  { id: "cedar-grove", name: "Cedar Grove Pantry", shortName: "Cedar Grove", role: "BENEFICIARY" },
  { id: "maple-crossing", name: "Maple Crossing Pantry", shortName: "Maple Crossing", role: "BENEFICIARY" },
  { id: "willow-creek", name: "Willow Creek Pantry", shortName: "Willow Creek", role: "BENEFICIARY" },
  { id: "pine-ridge", name: "Pine Ridge Pantry", shortName: "Pine Ridge", role: "BENEFICIARY" },
  { id: "gator-hub", name: "Gator Distribution Hub", shortName: "Gator Hub", role: "HUB" },
];

/** Physical stock only, like the live projection: served = min(stock, target), unmet = target − served. */
function project(stock: number, demand: number[]): SeriesProjection {
  let left = stock;
  const days: ProjectedDay[] = demand.map((target) => {
    const served = Math.min(left, target);
    left -= served;
    return { target, served, unmet: target - served, eligibleEnd: left };
  });
  return { kind: "projected", days, method: null };
}

const SEEDS: Record<string, Record<string, { stock: number; demand: number[] } | null>> = {
  riverbend: { [MEALS]: { stock: 60, demand: [48, 52, 50, 55, 58, 50, 47] }, [WATER]: { stock: 300, demand: [40, 42, 41, 44, 45, 42, 40] } },
  "oak-terrace": { [MEALS]: { stock: 30, demand: [36, 38, 35, 40, 42, 38, 36] }, [WATER]: { stock: 150, demand: [35, 36, 38, 37, 39, 36, 35] } },
  "cedar-grove": { [MEALS]: { stock: 400, demand: [30, 32, 0, 34, 31, 30, 29] }, [WATER]: { stock: 500, demand: [30, 31, 32, 30, 29, 31, 30] } },
  "maple-crossing": { [MEALS]: { stock: 250, demand: [25, 27, 26, 28, 30, 26, 24] }, [WATER]: { stock: 80, demand: [44, 46, 45, 47, 44, 45, 43] } },
  // Willow Creek meals: no series in the fixture (exercises Not evaluated).
  "willow-creek": { [MEALS]: null, [WATER]: { stock: 220, demand: [28, 29, 30, 31, 30, 29, 28] } },
  "pine-ridge": { [MEALS]: { stock: 140, demand: [22, 24, 23, 25, 26, 24, 22] }, [WATER]: { stock: 260, demand: [33, 35, 34, 36, 35, 34, 33] } },
};

const HUB_STOCK: Record<string, number> = { [MEALS]: 800, [WATER]: 1000 };

function cell(usable: number, held = 0, expired = 0): InventoryCell {
  const tallyOf = (units: number) => ({ lots: units > 0 ? 1 : 0, units });
  return { usable, onHand: usable + held + expired, eligible: tallyOf(usable), held: tallyOf(held), expired: tallyOf(expired), otherExcluded: { lots: 0, units: 0 }, localDate: DATES[0] };
}

const steady = (units: number): Quantity[] => DATES.map(() => units);

export function fixtureSnapshot(status: number): ExplorerSnapshot {
  const projections: Record<string, SeriesProjection> = {};
  const inventory: Record<string, InventoryCell> = {};
  for (const site of SITES) {
    for (const product of PRODUCTS) {
      const key = cellKey(site.id, product.id);
      if (site.role === "HUB") { inventory[key] = cell(HUB_STOCK[product.id]); continue; }
      const seed = SEEDS[site.id][product.id];
      projections[key] = seed ? project(seed.stock, seed.demand) : { kind: "not_evaluated", reason: "No series for this site and product in the static fixture." };
      const held = site.id === "oak-terrace" && product.id === MEALS ? 15 : 0;
      const expired = site.id === "maple-crossing" && product.id === WATER ? 6 : 0;
      inventory[key] = cell(seed?.stock ?? 90, held, expired);
    }
  }
  return {
    source: { kind: "fixture", status },
    timezone: "America/New_York",
    dates: DATES,
    products: PRODUCTS,
    sites: SITES,
    projections,
    inventory,
    inventoryRows: SITES.length * PRODUCTS.length,
    forecastDetail: {
      kind: "available",
      donations: {
        [cellKey("gator-hub", MEALS)]: steady(40),
        [cellKey("gator-hub", WATER)]: [0, 60, 0, 60, 0, 60, 0],
        [cellKey("riverbend", MEALS)]: steady(8),
      },
      demandInterval: {},
      bands: {},
    },
  };
}
