import { api, ApiError, apiRaw, apiText, apiWrite, type Schema } from "./planning-api";

/** Ids from the page URL or a response stay one path segment (no client-side path traversal). */
const seg = encodeURIComponent;
/** Job states after which `GET /jobs/{id}` will not change. */
export const JOB_ENDED = new Set<Schema["AttemptState"]>(["SUCCEEDED", "FAILED", "TIMED_OUT", "INTERRUPTED", "CANCELLED", "EXPIRED"]);
const UUID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";
const COMPARISON_URL = new RegExp(`^/api/v1/networks/${UUID}/comparisons/${UUID}$`, "i");

export type Network = Schema["Network"];
export type TemplateCatalog = Schema["TemplateCatalog"];
export type TemplateName = Schema["Template"]["name"];
export type ImportStatus = Schema["ImportStatus"];

/** Same-origin download URL for a template CSV (the proxy allows only template names and `kind`). */
export const templateUrl = (name: TemplateName, kind: "blank" | "example") => `/api/v1/templates/${name}.csv?kind=${kind}`;

/** v1 network and template reads (README "Interfaces frozen in W0-08"). Presenter-only; a visitor gets 401. */
export const networkApi = {
  list: () => api<Schema["NetworkList"]>("networks"),
  get: (networkId: string) => api<Network>(`networks/${encodeURIComponent(networkId)}`),
  templates: (mode?: Network["mode"]) => api<TemplateCatalog>(mode ? `templates?mode=${mode}` : "templates"),
  createImport: (body: Schema["ImportCreate"]) => api<Schema["ImportCreated"]>("imports", body),
  uploadImportFile: (importId: string, name: TemplateName, file: Blob) => apiRaw<Schema["ImportFile"]>(`imports/${seg(importId)}/files/${name}`, file, "text/csv"),
  commitImport: (importId: string, body: Schema["ImportCommit"]) => api<Schema["ImportAccepted"]>(`imports/${seg(importId)}/commit`, body),
  importStatus: (importId: string) => api<ImportStatus>(`imports/${seg(importId)}`),
  enrichment: (networkId: string) => api<Schema["EnrichmentStatus"]>(`networks/${seg(networkId)}/enrichment`),
  retryEnrichment: (networkId: string) => api<Schema["ForecastAccepted"]>(`networks/${seg(networkId)}/enrichment/retry`, {}),
  setAttributes: (networkId: string, locationId: string, body: Schema["LocationAttributesUpdate"]) =>
    apiWrite<Schema["LocationAttributes"]>("PUT", `networks/${seg(networkId)}/locations/${encodeURIComponent(locationId)}/attributes`, body),
  routes: (networkId: string) => api<Schema["RouteList"]>(`networks/${seg(networkId)}/routes`),
  googlePreview: (networkId: string) => api<Schema["GoogleLookupPreview"]>(`networks/${seg(networkId)}/routes/google-preview`, {}),
  googleFetch: (networkId: string) => api<Schema["ForecastAccepted"]>(`networks/${seg(networkId)}/routes/google-fetch`, {}),
  danger: (networkId: string, forecastRunId: string) =>
    api<Schema["DangerRanking"]>(`networks/${seg(networkId)}/danger?forecast_run_id=${encodeURIComponent(forecastRunId)}`),
  backtest: (forecastJobId: string) => api<Schema["BacktestResult"]>(`forecasts/${encodeURIComponent(forecastJobId)}/backtest`),
  createScenario: (networkId: string, body: Schema["ScenarioOptions"]) => api<Schema["ScenarioV3"]>(`networks/${seg(networkId)}/scenarios`, body),
  submitComparison: (networkId: string, body: Schema["ComparisonRequestV3"]) => api<Schema["ForecastAccepted"]>(`networks/${seg(networkId)}/comparisons`, body),
  /** The finished comparison named by the job's `result_url`; anything else is refused rather than fetched. */
  comparisonAt: async (resultUrl: string) => {
    if (!COMPARISON_URL.test(resultUrl)) throw new ApiError("INVALID_RESPONSE", 0);
    return api<Schema["SavedComparisonV3"]>(resultUrl.replace(/^\/api\/v1\//, ""));
  },
  comparison: (networkId: string, comparisonId: string) => api<Schema["SavedComparisonV3"]>(`networks/${seg(networkId)}/comparisons/${seg(comparisonId)}`),
  actions: (networkId: string, comparisonId: string, method: Schema["MethodResult"]["method"]) =>
    api<Schema["DecisionActions"]>(`networks/${seg(networkId)}/comparisons/${seg(comparisonId)}/methods/${seg(method)}/actions`),
  /** The server's plan CSV for the chosen actions (each row carries the scenario hash and the simulation note). */
  exportPlan: (networkId: string, comparisonId: string, method: Schema["MethodResult"]["method"], actionIds: string[]) =>
    apiText(`networks/${seg(networkId)}/comparisons/${seg(comparisonId)}/methods/${seg(method)}/export`, { action_ids: actionIds }),
  locations: (networkId: string) => api<Schema["LocationList"]>(`networks/${seg(networkId)}/locations`),
  projection: (networkId: string, forecastRunId: string, locationId: string) => api<Schema["LocationProjection"]>(
    `networks/${seg(networkId)}/projection?${new URLSearchParams({ forecast_run_id: forecastRunId, location_id: locationId })}`),
  job: (jobId: string) => api<Schema["ForecastJob"]>(`jobs/${seg(jobId)}`),
  settings: () => api<Schema["LocalSettings"]>("settings"),
  /** Write-only: the key is sent once and never read back. */
  setGoogleKey: (key: string) => apiWrite<Schema["LocalSettings"]>("PUT", "settings/google-maps-key", { key }),
  deleteGoogleKey: () => apiWrite<Schema["LocalSettings"]>("DELETE", "settings/google-maps-key"),
  /** Why an example CSV can't be downloaded, from the API's error envelope ("message (task)"); null when it can. */
  async exampleUnavailableReason(name: TemplateName): Promise<string | null> {
    const response = await fetch(templateUrl(name, "example"), { cache: "no-store", credentials: "same-origin" });
    if (response.ok) return null;
    const error = (await response.json().catch(() => null) as Partial<Schema["ErrorEnvelope"]> | null)?.error;
    if (!error) return `HTTP ${response.status}`;
    const task = (error.details as { task?: unknown } | null | undefined)?.task;
    return `${error.message}${typeof task === "string" ? ` (${task})` : ""}`;
  },
};
