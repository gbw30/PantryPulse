import type { components } from "../../../../packages/contracts/src/schema";

export type Schema = components["schemas"];
export class ApiError extends Error {
  /** `details` is the error envelope's `error.details` (for example atomic import row feedback). */
  constructor(public code: string, public status: number, public details: Record<string, unknown> = {}) { super(code.replaceAll("_", " ").toLowerCase()); }
}

function csrfToken() {
  const csrf = document.cookie.split("; ").find((item) => item.startsWith("pp_csrf="))?.slice(8);
  return decodeURIComponent(csrf ?? "");
}

async function send<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1/${path}`, { cache: "no-store", credentials: "same-origin", ...init });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("NETWORK_ERROR", 0);
  }
  let value: unknown = null;
  try { value = await response.json(); } catch { if (response.ok) throw new ApiError("INVALID_RESPONSE", response.status); }
  if (!response.ok) {
    const error = (value as Partial<Schema["ErrorEnvelope"]> | null)?.error;
    throw new ApiError(error?.code ?? "REQUEST_FAILED", response.status, (error?.details as Record<string, unknown> | undefined) ?? {});
  }
  return value as T;
}

/** GET without a body; POST JSON with CSRF and an Idempotency-Key (reuse the key when retrying one intent). */
export async function api<T>(path: string, body?: unknown, idempotencyKey?: string): Promise<T> {
  return send<T>(path, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? {} : { "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken(), "Idempotency-Key": idempotencyKey ?? crypto.randomUUID() },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

/** Multipart POST (CSV import). The browser sets the multipart boundary. */
export async function apiUpload<T>(path: string, form: FormData, idempotencyKey?: string): Promise<T> {
  return send<T>(path, { method: "POST", body: form,
    headers: { "X-CSRF-Token": csrfToken(), "Idempotency-Key": idempotencyKey ?? crypto.randomUUID() } });
}

export function localDay(timezone: string, offset = 0) {
  const day = new Intl.DateTimeFormat("en-CA", { timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  const date = new Date(`${day}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + offset);
  return date.toISOString().slice(0, 10);
}

const UUID = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
export const isUuid = (value: string | null | undefined): value is string => typeof value === "string" && UUID.test(value);

/** Job states after which polling stops. */
export const TERMINAL_JOB_STATES = new Set<Schema["AttemptState"]>(["SUCCEEDED", "FAILED", "TIMED_OUT", "INTERRUPTED", "CANCELLED", "EXPIRED"]);

/** The demo forecast request used by the connected workspace: seven days from yesterday's cutoff. */
export function demoForecastRequest(sourceId: string, timezone: string, strategy: Schema["ForecastSubmissionPolicy"]["strategy"] = "SEASONAL_NAIVE"): Schema["ForecastRequest"] {
  return { source_id: sourceId,
    data_cutoff_date: localDay(timezone, -1), history_start_date: localDay(timezone, -90),
    snapshot_as_of: new Date().toISOString(), force_refresh: false,
    policy: { strategy, policy_version: "demo-proposal-14d-3samples-v1",
      adapter_version: "core-v1", preprocessing_version: "preserve-gaps-v1", postprocessing_version: "reject-invalid-v1",
      sparse_window_days: 14, sparse_min_samples: 3, allow_fallback: true,
      allow_fulfilled_proxy: false, allow_mixed_proxy_history: false } };
}

export type Methodology = {
  methods: Schema["AllocationMethod"][]; transfer_modes: Schema["TransferMode"][]; default_transfer_mode: null;
  decision_ids: string[]; expiry: string; search_seconds: { default: number; maximum: number };
  donor_protection_days: number; planning_window_days: number[]; stock_effect: string; limitations: string[];
};

/** Typed presenter planning calls (same-origin proxy only). Every one answers 401 for visitors. */
export const planningApi = {
  planningCatalog: (before?: { at: string; id: string }) => api<Schema["PlanningCatalog"]>(before
    ? `planning-catalog?before=${encodeURIComponent(before.at)}&before_id=${before.id}` : "planning-catalog"),
  forecastCatalog: () => api<Schema["ForecastCatalog"]>("forecast-catalog"),
  methodology: () => api<Methodology>("allocation-methodology"),
  assumptions: (id: string) => api<Schema["AssumptionsResult"]>(`planning-assumptions/${id}`),
  saveAssumptions: (request: Schema["AssumptionsRequest"], key?: string) => api<Schema["AssumptionsResult"]>("planning-assumptions", request, key),
  generateForecast: (request: Schema["ForecastRequest"], key?: string) => api<Schema["ForecastAccepted"]>("forecasts", request, key),
  forecast: (jobId: string) => api<Schema["ForecastResult"]>(`forecasts/${jobId}`),
  freezeScenario: (request: Schema["ScenarioRequest"], key?: string) => api<Schema["ScenarioResult"]>("scenarios", request, key),
  scenario: (id: string) => api<Schema["ScenarioResult"]>(`scenarios/${id}`),
  /** Paired CLASSICAL_GP / EGP_PI_INSPIRED job on one frozen scenario; 409 SCENARIO_REVISION_MISMATCH if the hash moved. */
  compareMethods: (scenarioId: string, body: Schema["PairSubmit"], key?: string) => api<Schema["ForecastAccepted"]>(`scenarios/${scenarioId}/compare-methods`, body, key),
  job: (id: string) => api<Schema["ForecastJob"]>(`jobs/${id}`),
  cancelJob: (id: string, key?: string) => api<Schema["ForecastCancelled"]>(`jobs/${id}/cancel`, {}, key),
  retryJob: (id: string, key?: string) => api<Schema["ForecastAccepted"]>(`jobs/${id}/retry`, {}, key),
  /** A comparison's id equals its job id; 409 COMPARISON_NOT_PUBLISHED while it is still computing. */
  comparison: (id: string) => api<Schema["SavedComparison"]>(`comparisons/${id}`),
  /** Verified plans (ids + result_hash) for an allocation or comparison job. */
  allocationResults: (jobId: string) => api<Schema["AllocationResults"]>(`allocation-jobs/${jobId}/results`),
  plan: (id: string) => api<Schema["PlanResult"]>(`plans/${id}`),
  /** Simulation-only review marker; no stock, purchase or dispatch effect. 409 PLAN_REVISION_MISMATCH if the plan changed. */
  reviewPlan: (planId: string, body: Schema["ReviewRequest"], key?: string) => api<Record<string, unknown>>(`plans/${planId}/review`, body, key),
};
