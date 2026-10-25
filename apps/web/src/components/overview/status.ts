import type { MarkerStatus, Product, Site, SiteProductProjection } from "./types";

// Display-only deficit-date facts for the selected product and local day. These are legend
// definitions for this screen, not solver or allocation policy.
export const STATUS_LABEL: Record<MarkerStatus, string> = {
  shortfall: "Shortfall",
  watch: "Watch",
  covered: "Covered",
  not_evaluated: "Not evaluated",
  hub: "Hub · source",
};

export function statusFor(projection: SiteProductProjection | undefined, dayIndex: number): MarkerStatus {
  if (!projection) return "not_evaluated";
  if (projection.kind === "hub") return "hub";
  if (projection.kind !== "projected") return "not_evaluated";
  if (projection.unmetUnits[dayIndex] > 0) return "shortfall";
  if (projection.unmetUnits.slice(dayIndex + 1).some((units) => units > 0)) return "watch";
  return "covered";
}

export function firstDeficit(projection: SiteProductProjection | undefined): { dayIndex: number; unmetUnits: number } | null {
  if (!projection || projection.kind !== "projected") return null;
  const dayIndex = projection.unmetUnits.findIndex((units) => units > 0);
  return dayIndex < 0 ? null : { dayIndex, unmetUnits: projection.unmetUnits[dayIndex] };
}

export function formatUnits(value: number, product: Product) {
  return `${value.toLocaleString("en-US")} ${value === 1 ? product.unit : product.unitPlural}`;
}

function toUtcNoon(isoDate: string) {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day, 12));
}

// Dates are local calendar dates already; format them without shifting by the browser's zone.
export function formatDay(isoDate: string) {
  return toUtcNoon(isoDate).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" });
}

export function formatShortDate(isoDate: string) {
  return toUtcNoon(isoDate).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

export function formatRange(dates: string[]) {
  const first = toUtcNoon(dates[0]);
  const last = toUtcNoon(dates[dates.length - 1]);
  const sameMonth = first.getUTCMonth() === last.getUTCMonth();
  const end = sameMonth ? String(last.getUTCDate()) : formatShortDate(dates[dates.length - 1]);
  return `${formatShortDate(dates[0])}–${end}, ${last.getUTCFullYear()}`;
}

export function roleLabel(site: Site) {
  return site.role === "HUB" ? "distribution hub" : "beneficiary pantry";
}

/** One-line status detail used by markers, the site list and the popover. */
export function statusDetail(projection: SiteProductProjection | undefined, product: Product, dates: string[]) {
  if (!projection || projection.kind === "not_evaluated") return "no projection";
  if (projection.kind === "insufficient_data") return "insufficient data";
  if (projection.kind === "hub") return `${formatUnits(projection.eligibleStockNow, product)} eligible now`;
  const deficit = firstDeficit(projection);
  if (!deficit) return "no projected deficit";
  return `first deficit ${formatDay(dates[deficit.dayIndex])}: ${formatUnits(deficit.unmetUnits, product)} unmet`;
}

export function markerAccessibleName(site: Site, status: MarkerStatus, detail: string) {
  return `${site.name}, ${roleLabel(site)}, ${STATUS_LABEL[status]}, ${detail}`;
}
