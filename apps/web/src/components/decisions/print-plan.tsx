"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { V1_METHOD_LABEL } from "@/components/scenario-lab/model";
import { networkApi } from "@/lib/network-api";
import { ApiError, isUuid, type Schema } from "@/lib/planning-api";
import { effectLines } from "./action-card";
import { isV1Method } from "./decisions-view";
import { SIMULATED_NOTE } from "./export-bar";

type Load = { status: "loading" } | { status: "error"; text: string }
  | { status: "ready"; saved: Schema["SavedComparisonV3"]; decisions: Schema["DecisionActions"] };

type Props = { networkId?: string; comparisonId?: string; method?: string; actionIds: string[] };

/** Print-friendly copy of the selected actions: the same rows and identities as the CSV export. */
export function PrintPlan({ networkId, comparisonId, method, actionIds }: Props) {
  const valid = isUuid(networkId) && isUuid(comparisonId) && isV1Method(method);
  const [load, setLoad] = useState<Load>({ status: "loading" });
  useEffect(() => {
    if (!isUuid(networkId) || !isUuid(comparisonId) || !isV1Method(method)) return;
    let active = true;
    Promise.all([networkApi.comparison(networkId, comparisonId), networkApi.actions(networkId, comparisonId, method)]).then(
      ([saved, decisions]) => { if (active) setLoad({ status: "ready", saved, decisions }); },
      (error: unknown) => { if (active) setLoad({ status: "error", text: error instanceof ApiError ? `${error.message} (${error.code})` : "the request failed" }); },
    );
    return () => { active = false; };
  }, [networkId, comparisonId, method]);

  if (!valid) return <main className="p-6 text-sm">Open the print page from Decisions after selecting actions.</main>;
  const ready = load.status === "ready" ? load : null;
  const result = ready?.saved.result.methods.find((m) => m.method === method);
  const rows = ready ? ready.decisions.actions.filter((a) => actionIds.includes(a.id)) : [];

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
          <p>Scenario {ready.saved.scenario_id} · hash {ready.saved.result.scenario_hash}</p>
          <p>Method {V1_METHOD_LABEL[method]} · {ready.saved.result.mode === "RETAIL" ? "Retail" : "Pantry"} network · units as in the plan</p>
          <p className="font-semibold">{SIMULATED_NOTE}</p>
          <p>{ready.decisions.non_additive_label}</p>
          {rows.length === 0 ? <p>No actions selected.</p> : (
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
          )}
        </>
      )}
    </main>
  );
}
