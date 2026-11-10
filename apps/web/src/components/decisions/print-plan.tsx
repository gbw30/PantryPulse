"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { V1_METHOD_LABEL } from "@/components/scenario-lab/model";
import { SAMPLE_LABEL } from "@/components/shell/network-switcher";
import { networkApi, type Network } from "@/lib/network-api";
import { ApiError, isUuid } from "@/lib/planning-api";
import { effectLines } from "./action-card";
import { isV1Method, loadPlan, methodNotCompared, noVerifiedPlan, readSelection, type Plan } from "./decisions-view";
import { PlanNotes, SIMULATED_NOTE } from "./export-bar";

type Load = { status: "loading" } | { status: "error"; text: string }
  | ({ status: "ready"; network: Network; actionIds: string[] } & Plan);

type Props = { networkId?: string; comparisonId?: string; method?: string };

/**
 * Print-friendly copy of the selected actions: the same rows and identities as the CSV export. The rows come
 * from the API; the selection Decisions stored is only the list of ids to show.
 */
export function PrintPlan({ networkId, comparisonId, method }: Props) {
  const valid = isUuid(networkId) && isUuid(comparisonId) && isV1Method(method);
  const [load, setLoad] = useState<Load>({ status: "loading" });
  useEffect(() => {
    if (!isUuid(networkId) || !isUuid(comparisonId) || !isV1Method(method)) return;
    let active = true;
    Promise.all([loadPlan(networkId, comparisonId, method), networkApi.get(networkId)]).then(
      ([plan, network]) => { if (active) setLoad({ status: "ready", ...plan, network, actionIds: readSelection(networkId, comparisonId, method) }); },
      (error: unknown) => {
        const text = error instanceof ApiError && error.code === "METHOD_NOT_IN_COMPARISON" ? methodNotCompared(method)
          : error instanceof ApiError ? `${error.message} (${error.code})` : "the request failed";
        if (active) setLoad({ status: "error", text });
      },
    );
    return () => { active = false; };
  }, [networkId, comparisonId, method]);

  if (!valid) return <main className="p-6 text-sm">Open the print page from Decisions after selecting actions.</main>;
  const ready = load.status === "ready" ? load : null;
  const result = ready?.result;
  const chosen = new Set(ready?.actionIds);
  const rows = ready?.decisions?.actions.filter((a) => chosen.has(a.id)) ?? [];

  return (
    <main className="mx-auto grid max-w-5xl gap-3 bg-background p-4 text-sm text-foreground md:p-8 print:p-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">PantryPulse plan · {V1_METHOD_LABEL[method]}</h1>
        <Button type="button" size="sm" variant="outline" className="print:hidden" onClick={() => window.print()}>Print</Button>
      </div>
      {load.status === "loading" && <p role="status">Loading the selected actions…</p>}
      {load.status === "error" && <p role="alert">Plan unavailable: {load.text}.</p>}
      {ready && (
        <>
          <p>{ready.network.name}</p>
          {ready.network.is_sample && <p className="font-semibold">{SAMPLE_LABEL}</p>}
          <p>Scenario {ready.saved.scenario_id} · hash {ready.saved.result.scenario_hash}</p>
          <p>Method {V1_METHOD_LABEL[method]} · {ready.saved.result.mode === "RETAIL" ? "Retail" : "Pantry"} network</p>
          <PlanNotes saved={ready.saved} />
          {!ready.decisions ? <p>{noVerifiedPlan(method, result)}</p>
            : rows.length === 0 ? <p role="alert">No selected actions were found for this plan. Open the print page from Decisions after selecting actions.</p> : (<>
          <p className="font-semibold">{SIMULATED_NOTE}</p>
          <p>{ready.decisions.non_additive_label}</p>
          <table className="w-full border-collapse text-left align-top">
            <caption className="sr-only">Selected actions</caption>
            <thead>
              <tr className="border-b border-border">
                {["Action", "Why", "Effect"].map((h) => <th key={h} scope="col" className="py-1.5 pr-3 font-semibold">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((a) => {
                const lines = effectLines(a, ready.saved.result.mode, result?.usd_unavailable_reason ?? null);
                return (
                  <tr key={a.id} className="border-b border-border align-top break-inside-avoid">
                    <td className="py-1.5 pr-3">{a.action_text}</td>
                    <td className="py-1.5 pr-3">{a.why_text} <span className="text-muted-foreground">({a.explanation_kind === "proven_binding" ? "proven: binding constraint" : "inferred reason"})</span></td>
                    <td className="py-1.5 pr-3">{[lines.receiver, lines.sender, lines.expired, lines.usd].filter(Boolean).join("; ")}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </>)}
        </>
      )}
    </main>
  );
}
