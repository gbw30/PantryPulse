import { useCallback, useRef } from "react";
import { api, apiUpload, ApiError, type Schema } from "@/lib/planning-api";

// Presenter operational writes (PR #78) through the same-origin proxy. FastAPI validates and enforces
// presenter-only access; this module only shapes requests and turns error codes into plain words.
// Raw rows from operational-catalog / supplies / receipts are untyped in the contract, so the types
// below list only the fields this screen reads (integers arrive as decimal strings).

export type CatalogRow = { id: string; name: string };
export type SiteRow = CatalogRow & { role: "HUB" | "BENEFICIARY" | string };
export type ProductRow = CatalogRow & { base_unit: string };
export type SourceRow = CatalogRow & { classification: "OBSERVED" | "SIMULATED" | string };
export type OperationalCatalog = { sites: SiteRow[]; products: ProductRow[]; donors: CatalogRow[]; data_sources: SourceRow[] };

export type SupplyRow = {
  id: string; site_id: string; product_id: string; source_id: string; source_record_key: string;
  quantity: string; received_quantity: string; outstanding_confirmed_quantity: string;
  expected_arrival_at: string | null; state: string; version: string;
};

export type ReceiptLineRow = { id: string; line_key: string; product_id: string; received_quantity: string };
export type ReceiptRevisionRow = {
  id: string; revision: string; receiving_site_id?: string; site_id?: string; donor_id: string;
  received_at: string; local_day: string; is_void: boolean; lines: ReceiptLineRow[];
};
export type ReceiptRead = {
  receipt: { id: string; source_id: string; source_record_key: string };
  revisions: ReceiptRevisionRow[];
  reconciliation: { needs_reconciliation: boolean } | null;
};

export type CommandResult = Schema["CommandResult"];
export type ImportFeedback = { atomic?: boolean; accepted_count?: string; rejected_count?: string; errors?: { row_index: number | null; field: string; code: string }[] };

export const dataInputApi = {
  catalog: () => api<OperationalCatalog>("operational-catalog"),
  inventory: (siteId: string, productId: string) => api<Schema["InventorySnapshot"]>(`inventory/sites/${siteId}/products/${productId}`),
  declareLot: (lotId: string, body: Schema["LotDeclarationWrite"], key: string) => api<CommandResult>(`inventory/lots/${lotId}/declarations`, body, key),
  adjust: (siteId: string, productId: string, body: Schema["StockAdjustmentRequest"], key: string) =>
    api<Schema["StockAdjustmentResult"]>(`inventory/sites/${siteId}/products/${productId}/adjustments`, body, key),
  importDemand: (body: Schema["DemandImport"], key: string) => api<CommandResult>("imports/demand", body, key),
  importDemandCsv: (sourceId: string, file: File, key: string) => {
    const form = new FormData();
    form.set("source_id", sourceId);
    form.set("file", file);
    return apiUpload<CommandResult>("imports/demand/csv", form, key);
  },
  importCoverage: (body: Schema["CoverageImport"], key: string) => api<CommandResult>("imports/donation-coverage", body, key),
  createReceipt: (body: Schema["ReceiptWrite"], key: string) => api<CommandResult>("receipts", body, key),
  receipt: (id: string) => api<ReceiptRead>(`receipts/${id}`),
  reviseReceipt: (id: string, body: Schema["ReceiptWrite"], key: string) => api<CommandResult>(`receipts/${id}/revisions`, body, key),
  postReceipt: (id: string, action: "post" | "reconcile", body: Schema["ReceiptStockWrite"], key: string) => api<CommandResult>(`receipts/${id}/${action}`, body, key),
  supplies: () => api<{ supplies: SupplyRow[] }>("supplies"),
  createSupply: (body: Schema["SupplyCreate"], key: string) => api<CommandResult>("supplies", body, key),
  confirmSupply: (id: string, body: Schema["SupplyConfirmation"], key: string) => api<CommandResult>(`supplies/${id}/confirmation`, body, key),
};

/**
 * One Idempotency-Key per user intent: the same key is reused when the same submission is retried
 * (for example after a network error) and replaced once the user edits the form or succeeds.
 */
export function useIntentKey() {
  const key = useRef<string | null>(null);
  const current = useCallback(() => (key.current ??= crypto.randomUUID()), []);
  const reset = useCallback(() => { key.current = null; }, []);
  return { current, reset };
}

const COPY: Record<string, string> = {
  STALE_INVENTORY_VERSION: "Inventory changed since you loaded it. Reload, review and re-apply.",
  STALE_SUPPLY_VERSION: "This expected supply changed since you loaded it. Reload the list and try again.",
  STALE_RECEIPT_REVISION: "This receipt has a newer revision. Reload it and revise the latest one.",
  STALE_HISTORY_REVISION: "A day in this import changed since its revision was read. Set expected revision to the current one.",
  INSUFFICIENT_STOCK: "The adjustment would take a lot below zero.",
  RECEIPT_ALREADY_POSTED_OR_VOID: "This receipt revision is already posted or void.",
  RECEIPT_NOT_POSTED: "Post the receipt before reconciling it.",
  RECEIPT_ALREADY_RECONCILED: "This receipt is already reconciled.",
  DECLARATION_REQUIRED: "Every receipt line needs an eligibility and expiry declaration.",
  FUTURE_RECEIPT: "Received time is in the future.",
  FUTURE_HISTORY: "Demand history cannot include future days.",
  DUPLICATE_IMPORT_DAY: "The same site, product and day appears twice.",
  EMPTY_DEMAND_OBSERVATION: "A row has no requested, fulfilled or unmet value. Leave it out instead.",
  INVALID_CSV_HEADERS: "CSV headers must be exactly: source_record_key, site_id, product_id, day, expected_revision, requested, fulfilled, unmet.",
  INVALID_CSV_ROWS: "The CSV has malformed rows or more than 100 rows.",
  INVALID_DEMAND_CSV: "The CSV could not be read. Check the encoding and values.",
  IMPORT_TOO_LARGE: "The file is larger than 60 kB.",
  INPUT_TOO_LARGE: "The request is too large.",
  IDEMPOTENCY_CONFLICT: "This request id was already used for different content. Edit and submit again.",
  OPERATIONAL_CONFLICT: "The record conflicts with existing data.",
  NOT_FOUND: "Record not found.",
  NEW_RECEIPT_HAS_NO_REVISION: "A new receipt cannot have an expected revision.",
  RECEIPT_SOURCE_MISMATCH: "A revision must keep the receipt's source and record key.",
  SUPPLY_NOT_CONFIRMED_OR_EXCEEDED: "The supply match is not confirmed or exceeds the outstanding quantity.",
  SUPPLY_MATCH_EXCEEDS_RECEIPT: "The supply match exceeds the received line quantity.",
  PRESENTER_REQUIRED: "Presenter sign-in required.",
  ORIGIN_FORBIDDEN: "The request came from an unexpected origin. Reload the page.",
  BACKEND_NOT_CONFIGURED: "The planning service is not configured.",
  BACKEND_UNAVAILABLE: "The planning service is unavailable right now.",
  NETWORK_ERROR: "Could not reach the server. Retry sends the same request again.",
};

/** Plain-language message with the API code beside it (the API returns codes only). */
export function describeError(error: unknown): string {
  if (!(error instanceof ApiError)) return "Request failed.";
  const text = COPY[error.code] ?? (error.status === 422 ? "The server rejected the input." : error.status >= 500 ? "The service failed to respond." : "Request failed.");
  return `${text} (${error.code})`;
}

export const isStale = (error: unknown) => error instanceof ApiError && error.status === 409 && error.code.startsWith("STALE_");
export const feedbackOf = (error: unknown): ImportFeedback | null =>
  error instanceof ApiError && Array.isArray((error.details as ImportFeedback).errors) ? error.details as ImportFeedback : null;

export const POSITIVE = /^[1-9][0-9]{0,18}$/;
export const NONNEGATIVE = /^(0|[1-9][0-9]{0,18})$/;
export const SIGNED_NONZERO = /^-?[1-9][0-9]{0,18}$/;
