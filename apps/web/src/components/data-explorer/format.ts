import type { ExplorerNotice, MarkStatus, Product, Quantity, StaleCode } from "./types";

// Formatting and copy for the Data Explorer. Definitions mirror the Overview legend words on purpose
// (copied, not imported: PP-52 owns components/overview).

export const LIVE_LABEL = "Live · simulated network";
export const VISITOR_LABEL = "Static fixture · visitor view";
export const FIXTURE_LABEL = "SIMULATED — static design fixture, not model output";

export const STATUS_LABEL: Record<MarkStatus, string> = {
  shortfall: "Shortfall",
  watch: "Watch",
  covered: "Covered",
  not_evaluated: "Not evaluated",
  hub: "Hub · source",
};

export function pluralize(unit: string) {
  if (/s$/i.test(unit)) return unit;
  if (/[^aeiou]y$/i.test(unit)) return `${unit.slice(0, -1)}ies`;
  return `${unit}s`;
}

export function shortName(name: string) {
  return name.replace(/ Pantry$/, "").replace(/ Distribution Hub$/, " Hub");
}

/** Units in the product's base unit; an unavailable quantity is never rounded or guessed. */
export function formatUnits(value: Quantity, product: Product) {
  if (value === null) return "Unavailable";
  return `${value.toLocaleString("en-US", { maximumFractionDigits: 1 })} ${value === 1 ? product.unit : product.unitPlural}`;
}

export function formatNumber(value: Quantity) {
  return value === null ? "Unavailable" : value.toLocaleString("en-US", { maximumFractionDigits: 1 });
}

/** A ratio as a percent. Never shows 100% unless fully served; N/A for a zero denominator. */
export function formatPercent(numerator: number, denominator: number) {
  if (denominator <= 0) return "N/A";
  if (numerator >= denominator) return "100%";
  const pct = (numerator / denominator) * 100;
  if (pct > 0 && pct < 1) return "<1%";
  return `${Math.min(99, Math.round(pct))}%`;
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
  if (dates.length === 0) return "no projection dates";
  if (dates.length === 1) return `${formatShortDate(dates[0])}, ${toUtcNoon(dates[0]).getUTCFullYear()}`;
  const first = toUtcNoon(dates[0]);
  const last = toUtcNoon(dates[dates.length - 1]);
  const end = first.getUTCMonth() === last.getUTCMonth() ? String(last.getUTCDate()) : formatShortDate(dates[dates.length - 1]);
  return `${formatShortDate(dates[0])}–${end}, ${last.getUTCFullYear()}`;
}

/** An API instant in the network's local time zone, e.g. "Nov 2, 7:05 AM EST". */
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

const PROVIDER_LABEL: Record<string, string> = {
  SEASONAL_NAIVE: "Seasonal-naive baseline",
  MOVING_AVERAGE: "Moving-average baseline",
  CHRONOS2: "Chronos-2 model",
};

const FALLBACK_REASON: Record<string, string> = {
  INSUFFICIENT_DATA: "Too little history for the primary method",
  INVALID_PROVIDER_OUTPUT: "The primary method returned invalid output",
  PROVIDER_UNAVAILABLE: "The primary model was unavailable",
};

export function providerLabel(provider: string) {
  return PROVIDER_LABEL[provider] ?? provider;
}

export function fallbackReasonLabel(reason: string | null) {
  if (!reason) return "No reason was recorded.";
  const plain = FALLBACK_REASON[reason];
  return plain ? `${plain} (${reason}).` : `Reason: ${reason}.`;
}

const STALE_COPY: Record<StaleCode, string> = {
  FORECAST_HORIZON_ALREADY_STARTED: "The latest forecast's first day has already passed. Run a new forecast.",
  FORECAST_UNIT_OR_CALENDAR_CHANGED: "A site's unit or calendar changed after this forecast.",
  FORECAST_NETWORK_SCOPE_CHANGED: "Sites or products changed after this forecast.",
};

export function isStaleCode(code: string): code is StaleCode {
  return Object.hasOwn(STALE_COPY, code);
}

export function noticeHeadline(notice: ExplorerNotice) {
  switch (notice.kind) {
    case "not_ready": return "No planning-ready forecast yet.";
    case "stale": return STALE_COPY[notice.code];
    case "integrity": return "The saved forecast failed its integrity check; statuses are not evaluated.";
    case "demand_unavailable": return "A demand forecast in the latest run is unavailable, so statuses are not evaluated.";
    case "projection_visitor": return "The shortage projection needs a presenter session.";
    case "projection_unavailable": return "The shortage projection could not be read.";
  }
}

/** Short reason shown where a projection would be. */
export function noticeReason(notice: ExplorerNotice) {
  switch (notice.kind) {
    case "not_ready": return "No planning-ready forecast yet.";
    case "stale": return STALE_COPY[notice.code];
    case "integrity": return "The saved forecast failed its integrity check.";
    case "demand_unavailable": return "A demand forecast in the latest run is unavailable.";
    case "projection_visitor": return "The shortage projection needs a presenter session.";
    case "projection_unavailable": return "The shortage projection could not be read.";
  }
}
