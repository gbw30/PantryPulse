"use client";

import { useEffect, useState } from "react";
import { MotionConfig } from "motion/react";
import { MethodVerification } from "@/components/recommendations/vocabulary";
import { V1_METHOD_LABEL, type V1Method } from "@/components/scenario-lab/model";
import { AppShell } from "@/components/shell/app-shell";
import { SampleBadge, useNetwork } from "@/components/shell/network-switcher";
import { modeSummary } from "@/lib/mode-vocabulary";
import { networkApi, type Network } from "@/lib/network-api";
import { ApiError, isUuid, type Schema } from "@/lib/planning-api";
import { ActionList } from "./action-list";
import { ExportBar, PlanNotes } from "./export-bar";

export const isV1Method = (value: string | undefined): value is V1Method => !!value && Object.hasOwn(V1_METHOD_LABEL, value);
const failure = (error: unknown) => (error instanceof ApiError ? `${error.message} (${error.code})` : "the request failed");

type Load = { status: "loading" } | { status: "error"; text: string }
  | { status: "ready"; saved: Schema["SavedComparisonV3"]; decisions: Schema["DecisionActions"] };

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
    Promise.all([networkApi.comparison(network.id, comparisonId), networkApi.actions(network.id, comparisonId, method)]).then(
      ([saved, decisions]) => { if (active) setLoad({ status: "ready", saved, decisions }); },
      (error: unknown) => {
        // Both reads are scoped to the sidebar network, so another network's comparison arrives as a 404.
        const text = error instanceof ApiError && error.status === 404
          ? `Comparison not found in ${network.name}. If it belongs to another network, choose that network in the sidebar.`
          : `Suggested actions unavailable: ${failure(error)}.`;
        if (active) setLoad({ status: "error", text });
      },
    );
    return () => { active = false; };
  }, [network.id, network.name, comparisonId, method]);

  const label = V1_METHOD_LABEL[method];
  const ready = load.status === "ready" ? load : null;
  const result = ready?.saved.result.methods.find((m) => m.method === method);
  const ids = ready ? ready.decisions.actions.map((a) => a.id).filter((id) => selected.has(id)) : [];
  const printHref = `/decisions/print?${new URLSearchParams({ network_id: network.id, comparison_id: comparisonId, method, actions: ids.join(",") })}`;

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
      setExportError(`Export failed: ${failure(error)}.`);
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
          {!result?.verified ? (
            <p className="text-sm">
              {label} has no verified plan in this comparison, so there are no suggested actions.{result?.failure_reason ? ` ${result.failure_reason}.` : ""}
            </p>
          ) : (<>
          <ExportBar total={ready.decisions.actions.length} count={ids.length} busy={exporting} printHref={printHref} onExport={() => void exportCsv()}
            onSelectAll={() => setSelected(new Set(ready.decisions.actions.map((a) => a.id)))} onClear={() => setSelected(new Set())} />
          {exportError && <p role="alert" className="text-sm">{exportError}</p>}
          <ActionList decisions={ready.decisions} mode={ready.saved.result.mode} usdUnavailableReason={result?.usd_unavailable_reason ?? null}
            selected={selected} onToggle={(id, on) => setSelected((s) => { const next = new Set(s); if (on) next.add(id); else next.delete(id); return next; })} />
          </>)}
        </>
      )}
    </section>
  );
}
