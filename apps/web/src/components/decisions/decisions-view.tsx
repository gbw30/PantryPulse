"use client";

import { useEffect, useMemo, useState } from "react";
import { MotionConfig } from "motion/react";
import { MethodVerification } from "@/components/recommendations/vocabulary";
import { V1_METHOD_LABEL, type V1Method } from "@/components/scenario-lab/model";
import { solverText } from "@/components/scenario-lab/results";
import { AppShell } from "@/components/shell/app-shell";
import { SampleBadge, useNetwork } from "@/components/shell/network-switcher";
import { modeSummary } from "@/lib/mode-vocabulary";
import { networkApi, type Network } from "@/lib/network-api";
import { ApiError, isUuid, type Schema } from "@/lib/planning-api";
import { ActionList } from "./action-list";
import { ExportBar, PlanNotes } from "./export-bar";

export const isV1Method = (value: string | undefined): value is V1Method => !!value && Object.hasOwn(V1_METHOD_LABEL, value);
type MethodResult = Schema["SavedComparisonV3"]["result"]["methods"][number];
/** Decisions and its print page show actions only for a verified plan. */
export const noVerifiedPlan = (method: V1Method, result: MethodResult | undefined) =>
  `${V1_METHOD_LABEL[method]} has no verified plan in this comparison, so there are no suggested actions.${result?.failure_reason ? ` ${result.failure_reason}.` : ""}${result ? ` ${solverText(result.native_status)}.` : ""}`;
export const methodNotCompared = (method: V1Method) =>
  `${V1_METHOD_LABEL[method]} is not one of the methods in this comparison. Open suggested actions from a method result in Scenario Lab.`;
const failure = (error: unknown) => (error instanceof ApiError ? `${error.message} (${error.code})` : "the request failed");
const EXPORT_MAX_ACTIONS = 40_000; // the API's cap on one export's action_ids (ExportRequest)

export type Plan = { saved: Schema["SavedComparisonV3"]; result: MethodResult; decisions: Schema["DecisionActions"] | null };

/**
 * The comparison first, then the method's actions only for a verified result: the actions route answers
 * 409 RESULT_NOT_VERIFIED otherwise, and the page must still show why there is no plan. `decisions` is null
 * for an unverified method. A method the comparison does not contain rejects with METHOD_NOT_IN_COMPARISON.
 */
export async function loadPlan(networkId: string, comparisonId: string, method: V1Method): Promise<Plan> {
  const saved = await networkApi.comparison(networkId, comparisonId);
  const result = saved.result.methods.find((m) => m.method === method);
  if (!result) throw new ApiError("METHOD_NOT_IN_COMPARISON", 404);
  if (!result.verified) return { saved, result, decisions: null };
  try {
    return { saved, result, decisions: await networkApi.actions(networkId, comparisonId, method) };
  } catch (error) {
    if (error instanceof ApiError && error.code === "RESULT_NOT_VERIFIED") return { saved, result, decisions: null };
    throw error;
  }
}

// The print page gets the selection through storage, not its URL: hundreds of ids overflow a URL (code-review #7).
// One selection is kept, naming the plan it belongs to; each save replaces it, so storage never piles up.
const SELECTION_KEY = "pantrypulse:print-selection";
type Selection = { network_id: string; comparison_id: string; method: V1Method; ids: string[] };
function saveSelection(networkId: string, comparisonId: string, method: V1Method, ids: string[]) {
  const value: Selection = { network_id: networkId, comparison_id: comparisonId, method, ids };
  try {
    window.localStorage.setItem(SELECTION_KEY, JSON.stringify(value));
  } catch {
    // Full or blocked: leave no older selection behind, so the print page says the selection is missing.
    try { window.localStorage.removeItem(SELECTION_KEY); } catch { /* storage unavailable */ }
  }
}
/** The ids chosen on Decisions for this plan; empty when none were stored for it or storage is unavailable. */
export function readSelection(networkId: string, comparisonId: string, method: V1Method): string[] {
  try {
    const stored = JSON.parse(window.localStorage.getItem(SELECTION_KEY) ?? "null") as Partial<Selection> | null;
    if (stored?.network_id !== networkId || stored.comparison_id !== comparisonId || stored.method !== method || !Array.isArray(stored.ids)) return [];
    return stored.ids.filter((id): id is string => typeof id === "string");
  } catch {
    return [];
  }
}

type Load = { status: "loading" } | { status: "error"; text: string } | ({ status: "ready" } & Plan);

/** V1-SPEC §6.5: suggested actions of one method result on one frozen scenario, then export. */
export function DecisionsView({ comparisonId, method }: { comparisonId?: string; method?: string }) {
  return (
    <MotionConfig reducedMotion="user">
      <AppShell active="scenarios" horizonLabel="Simulated plan">
        <div className="flex flex-1 flex-col gap-4 px-4 pt-3 pb-6 md:px-6 md:py-5">
          <header>
            <h1 className="text-[26px] leading-tight font-semibold tracking-tight md:text-[28px]">Decisions</h1>
            <p className="text-sm text-muted-foreground">Suggested transfers from one compared method, each with its reason and effect.</p>
          </header>
          {isUuid(comparisonId) && isV1Method(method)
            ? <Decisions comparisonId={comparisonId} method={method} />
            : <p className="text-sm text-muted-foreground">Open suggested actions from a verified method result in Scenario Lab.</p>}
        </div>
      </AppShell>
    </MotionConfig>
  );
}

function Decisions({ comparisonId, method }: { comparisonId: string; method: V1Method }) {
  const { network } = useNetwork();
  return network ? <Loaded key={`${network.id}:${comparisonId}:${method}`} network={network} comparisonId={comparisonId} method={method} /> : null;
}

function Loaded({ network, comparisonId, method }: { network: Network; comparisonId: string; method: V1Method }) {
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    loadPlan(network.id, comparisonId, method).then(
      (plan) => { if (active) setLoad({ status: "ready", ...plan }); },
      (error: unknown) => {
        // Both reads are scoped to the sidebar network, so another network's comparison arrives as a 404.
        const text = error instanceof ApiError && error.code === "METHOD_NOT_IN_COMPARISON" ? methodNotCompared(method)
          : error instanceof ApiError && error.status === 404
          ? `Comparison not found in ${network.name}. If it belongs to another network, choose that network in the sidebar.`
          : `Suggested actions unavailable: ${failure(error)}.`;
        if (active) setLoad({ status: "error", text });
      },
    );
    return () => { active = false; };
  }, [network.id, network.name, comparisonId, method]);

  const label = V1_METHOD_LABEL[method];
  const ready = load.status === "ready" ? load : null;
  const result = ready?.result;
  const ids = useMemo(() => ready?.decisions?.actions.map((a) => a.id).filter((id) => selected.has(id)) ?? [], [ready, selected]);
  useEffect(() => saveSelection(network.id, comparisonId, method, ids), [network.id, comparisonId, method, ids]);
  const printHref = `/decisions/print?${new URLSearchParams({ network_id: network.id, comparison_id: comparisonId, method })}`;

  async function exportCsv() {
    setExporting(true);
    setExportError(null);
    try {
      const csv = await networkApi.exportPlan(network.id, comparisonId, method, ids);
      const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
      const link = Object.assign(document.createElement("a"), { href: url, download: `pantrypulse-plan-${comparisonId.slice(0, 8)}-${method}.csv` });
      // In the document for Firefox; the URL lives on long enough for Safari to start reading the blob.
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
      const tooMany = error instanceof ApiError && (error.status === 413 || (error.status === 422 && ids.length > EXPORT_MAX_ACTIONS));
      setExportError(tooMany ? "Export failed: too many actions selected to export at once (at most 40,000). Select fewer and export again." : `Export failed: ${failure(error)}.`);
    } finally {
      setExporting(false);
    }
  }

  return (
    <section aria-labelledby="decisions-heading" className="grid gap-4 rounded-lg border border-border bg-card p-3 md:p-4">
      <div className="grid gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="decisions-heading" className="text-base font-semibold">Suggested actions · {network.name}</h2>
          {network.is_sample && <SampleBadge />}
        </div>
        <p className="text-xs text-muted-foreground">{modeSummary(network.mode)} · {label}</p>
      </div>
      {load.status === "loading" && <p role="status" className="text-sm text-muted-foreground">Loading suggested actions…</p>}
      {load.status === "error" && <p role="alert" className="text-sm">{load.text}</p>}
      {ready && ready.saved.network_id !== network.id && (
        <p className="text-sm text-muted-foreground">This comparison belongs to another network. Choose that network in the sidebar.</p>
      )}
      {ready && ready.saved.network_id === network.id && (
        <>
          <div className="grid gap-1 text-xs">
            <p className="font-medium">Scenario {ready.saved.scenario_id.slice(0, 8)} · hash {ready.saved.result.scenario_hash.slice(0, 12)}…</p>
            {result && <MethodVerification verified={result.verified} />}
          </div>
          <PlanNotes saved={ready.saved} />
          {!ready.decisions ? (
            <p className="text-sm">{noVerifiedPlan(method, result)}</p>
          ) : (<>
          <ExportBar total={ready.decisions.actions.length} count={ids.length} busy={exporting} printHref={printHref} onExport={() => void exportCsv()}
            onSelectAll={() => setSelected(new Set(ready.decisions?.actions.map((a) => a.id)))} onClear={() => setSelected(new Set())} />
          {exportError && <p role="alert" className="text-sm">{exportError}</p>}
          <ActionList decisions={ready.decisions} mode={ready.saved.result.mode} usdUnavailableReason={result?.usd_unavailable_reason ?? null}
            selected={selected} onToggle={(id, on) => setSelected((s) => { const next = new Set(s); if (on) next.add(id); else next.delete(id); return next; })} />
          </>)}
        </>
      )}
    </section>
  );
}
