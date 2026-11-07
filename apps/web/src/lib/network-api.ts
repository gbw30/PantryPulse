import { api, apiRaw, apiWrite, type Schema } from "./planning-api";

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
  uploadImportFile: (importId: string, name: TemplateName, file: Blob) => apiRaw<Schema["ImportFile"]>(`imports/${importId}/files/${name}`, file, "text/csv"),
  commitImport: (importId: string, body: Schema["ImportCommit"]) => api<Schema["ImportAccepted"]>(`imports/${importId}/commit`, body),
  importStatus: (importId: string) => api<ImportStatus>(`imports/${importId}`),
  enrichment: (networkId: string) => api<Schema["EnrichmentStatus"]>(`networks/${networkId}/enrichment`),
  retryEnrichment: (networkId: string) => api<Schema["ForecastAccepted"]>(`networks/${networkId}/enrichment/retry`, {}),
  setAttributes: (networkId: string, locationId: string, body: Schema["LocationAttributesUpdate"]) =>
    apiWrite<Schema["LocationAttributes"]>("PUT", `networks/${networkId}/locations/${encodeURIComponent(locationId)}/attributes`, body),
  routes: (networkId: string) => api<Schema["RouteList"]>(`networks/${networkId}/routes`),
  googlePreview: (networkId: string) => api<Schema["GoogleLookupPreview"]>(`networks/${networkId}/routes/google-preview`, {}),
  googleFetch: (networkId: string) => api<Schema["ForecastAccepted"]>(`networks/${networkId}/routes/google-fetch`, {}),
  danger: (networkId: string, forecastRunId: string) =>
    api<Schema["DangerRanking"]>(`networks/${networkId}/danger?forecast_run_id=${encodeURIComponent(forecastRunId)}`),
  backtest: (forecastJobId: string) => api<Schema["BacktestResult"]>(`forecasts/${encodeURIComponent(forecastJobId)}/backtest`),
  createScenario: (networkId: string, body: Schema["ScenarioOptions"]) => api<Schema["ScenarioV3"]>(`networks/${networkId}/scenarios`, body),
  submitComparison: (networkId: string, body: Schema["ComparisonRequestV3"]) => api<Schema["ForecastAccepted"]>(`networks/${networkId}/comparisons`, body),
  /** The finished comparison named by the job's `result_url` (GET networks/{id}/comparisons/{comparison_id}). */
  comparisonAt: (resultUrl: string) => api<Schema["SavedComparisonV3"]>(resultUrl.replace(/^\/api\/v1\//, "")),
  job: (jobId: string) => api<Schema["ForecastJob"]>(`jobs/${encodeURIComponent(jobId)}`),
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
