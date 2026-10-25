import type { LiveNotice, StaleCode } from "./types";

// Plain-language copy for live notices. The API's error message is only the code lower-cased
// (apps/api/app/main.py), so it is never shown as prose; the code appears as secondary text.

const STALE_COPY: Record<StaleCode, { headline: string; reason: string }> = {
  FORECAST_HORIZON_ALREADY_STARTED: {
    headline: "The latest forecast's first day has already passed. Run a new forecast.",
    reason: "The latest forecast's first day has already passed.",
  },
  FORECAST_UNIT_OR_CALENDAR_CHANGED: {
    headline: "A site's unit or calendar changed after this forecast.",
    reason: "A site's unit or calendar changed after this forecast.",
  },
  FORECAST_NETWORK_SCOPE_CHANGED: {
    headline: "Sites or products changed after this forecast.",
    reason: "Sites or products changed after this forecast.",
  },
};

export const STALE_CODES = new Set<string>(Object.keys(STALE_COPY));

export function isStaleCode(code: string): code is StaleCode {
  return STALE_CODES.has(code);
}

/** Notice headline, always a sentence. */
export function noticeHeadline(notice: LiveNotice) {
  switch (notice.kind) {
    case "not_ready":
      return "No planning-ready forecast yet.";
    case "stale":
      return STALE_COPY[notice.code].headline;
    case "integrity":
      return "The saved forecast failed its integrity check; statuses are not evaluated.";
    case "demand_unavailable":
      return "A demand forecast in the latest run is unavailable, so statuses are not evaluated.";
  }
}

/** Short reason shown in the inspector's "Projection: Not evaluated" fact. */
export function noticeReason(notice: LiveNotice) {
  switch (notice.kind) {
    case "not_ready":
      return "No planning-ready forecast yet.";
    case "stale":
      return STALE_COPY[notice.code].reason;
    case "integrity":
      return "The saved forecast failed its integrity check.";
    case "demand_unavailable":
      return "A demand forecast in the latest run is unavailable.";
  }
}
