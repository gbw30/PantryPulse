import type { components } from "../../../../packages/contracts/src/schema";

// Read-only transport for the Overview. Same-origin proxy only (/api/v1/*); the API owns
// authentication, so presenter-only endpoints answer 401/403 for visitors.

export type OverviewSchema = components["schemas"];
export type DashboardSummary = OverviewSchema["DashboardSummary"];
export type InventorySnapshot = OverviewSchema["InventorySnapshot"];
export type ShortageProjection = OverviewSchema["ShortageProjection"];
export type ForecastCatalog = OverviewSchema["ForecastCatalog"];

export class OverviewApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
    this.name = "OverviewApiError";
  }
}

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

async function get<T>(path: string, signal: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1/${path}`, { cache: "no-store", credentials: "same-origin", signal });
  } catch (error) {
    if (isAbort(error)) throw error;
    throw new OverviewApiError(0, "NETWORK_ERROR", "The request did not reach the server.");
  }
  let body: unknown = null;
  try {
    body = await response.json();
  } catch (error) {
    if (isAbort(error)) throw error;
    if (response.ok) throw new OverviewApiError(response.status, "INVALID_RESPONSE", "The server returned a response that is not JSON.");
  }
  if (!response.ok) {
    const envelope = (body ?? {}) as Partial<OverviewSchema["ErrorEnvelope"]>;
    throw new OverviewApiError(response.status, envelope.error?.code ?? `HTTP_${response.status}`, envelope.error?.message ?? `Request failed with status ${response.status}.`);
  }
  return body as T;
}

const UUID = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;

export const overviewApi = {
  summary: (signal: AbortSignal) => get<DashboardSummary>("dashboard/summary", signal),
  catalog: (signal: AbortSignal) => get<ForecastCatalog>("forecast-catalog", signal),
  shortages: (forecastRunId: string, signal: AbortSignal) => {
    if (!UUID.test(forecastRunId)) return Promise.reject(new OverviewApiError(0, "INVALID_FORECAST_ID", "The latest forecast id is not a UUID."));
    return get<ShortageProjection>(`shortages/${forecastRunId}`, signal);
  },
};

const MAX_SAFE = String(Number.MAX_SAFE_INTEGER);

/**
 * Parses a nonnegative decimal string from the API. Returns null (shown as "Unavailable") when the
 * value is malformed or its integer part exceeds Number.MAX_SAFE_INTEGER, so nothing is ever rounded.
 */
export function parseQuantity(value: string | null | undefined): number | null {
  if (typeof value !== "string") return null;
  const match = /^(\d+)(?:\.(\d+))?$/.exec(value.trim());
  if (!match) return null;
  const integer = match[1].replace(/^0+(?=\d)/, "");
  if (integer.length > MAX_SAFE.length || (integer.length === MAX_SAFE.length && integer > MAX_SAFE)) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
