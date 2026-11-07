import { api, apiRaw, type Schema } from "./planning-api";

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
