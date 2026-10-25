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

/** Next projected deficit on or after the selected day (Watch and Shortfall sites). */
export function nextDeficitFrom(projection: SiteProductProjection | undefined, fromIndex: number): { dayIndex: number; unmetUnits: number } | null {
  if (!projection || projection.kind !== "projected") return null;
  for (let index = fromIndex; index < projection.unmetUnits.length; index += 1) {
    if (projection.unmetUnits[index] > 0) return { dayIndex: index, unmetUnits: projection.unmetUnits[index] };
  }
  return null;
}

/** Short visible status line: Watch adds the date of its next deficit. */
export function statusLine(status: MarkerStatus, projection: SiteProductProjection | undefined, dayIndex: number, dates: string[]) {
  if (status !== "watch") return STATUS_LABEL[status];
  const next = nextDeficitFrom(projection, dayIndex);
  return next ? `Watch · ${formatShortDate(dates[next.dayIndex])}` : STATUS_LABEL[status];
}

/** Units in the product's base unit; an unavailable quantity is never rounded or guessed. */
export function formatUnits(value: number | null, product: Product) {
  if (value === null) return "Unavailable";
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
  if (dates.length === 1) return `${formatShortDate(dates[0])}, ${toUtcNoon(dates[0]).getUTCFullYear()}`;
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
export function statusDetail(projection: SiteProductProjection | undefined, product: Product, dates: string[], dayIndex: number) {
  if (!projection || projection.kind === "not_evaluated") return "no projection";
  if (projection.kind === "insufficient_data") return "insufficient data";
  if (projection.kind === "hub") return projection.eligibleStockNow === null ? "eligible stock unavailable" : `${formatUnits(projection.eligibleStockNow, product)} eligible now`;
  const next = nextDeficitFrom(projection, dayIndex);
  if (!next) return `no projected deficit from ${formatDay(dates[dayIndex])}`;
  return `next deficit ${formatDay(dates[next.dayIndex])}: ${formatUnits(next.unmetUnits, product)} unmet`;
}

/** Popover/inspector line for the next deficit on or after the selected day, with units. */
export function nextDeficitLine(projection: SiteProductProjection | undefined, product: Product, dates: string[], dayIndex: number) {
  const next = nextDeficitFrom(projection, dayIndex);
  if (!next) return `No projected deficit from ${formatDay(dates[dayIndex])} through ${formatDay(dates[dates.length - 1])}`;
  return `${formatDay(dates[next.dayIndex])} · ${formatUnits(next.unmetUnits, product)} unmet`;
}

export function markerAccessibleName(site: Site, status: MarkerStatus, detail: string, extra?: string) {
  return `${site.name}, ${roleLabel(site)}, ${STATUS_LABEL[status]}, ${detail}${extra ? `, ${extra}` : ""}`;
}

/** An API instant shown in the network's local time zone, e.g. "Nov 2, 9:30 AM EST". */
export function formatInstant(iso: string | null | undefined, timeZone: string) {
  if (!iso) return "unknown time";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const options: Intl.DateTimeFormatOptions = { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" };
  try {
    return date.toLocaleString("en-US", { ...options, timeZone });
  } catch {
    return date.toLocaleString("en-US", { ...options, timeZone: "UTC" });
  }
}
