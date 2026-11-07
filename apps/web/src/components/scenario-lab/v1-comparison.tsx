"use client";

import { useEffect, useRef, useState } from "react";
import { SampleBadge, useNetwork } from "@/components/shell/network-switcher";
import { modeSummary } from "@/lib/mode-vocabulary";
import { networkApi, type Network } from "@/lib/network-api";
import { ApiError, type Schema } from "@/lib/planning-api";
import { V1_METHODS, type V1Measure, type V1Method } from "./model";
import { MethodComparisonResults } from "./results";
import { ComparisonSetup } from "./wizard";

const TERMINAL = new Set<Schema["AttemptState"]>(["SUCCEEDED", "FAILED", "TIMED_OUT", "INTERRUPTED", "CANCELLED", "EXPIRED"]);
const POLL_MS = 1000;

type Shown = { saved: Schema["SavedComparisonV3"]; scenario: Schema["ScenarioV3"]; requested: V1Method[] };
type Status = { kind: "idle" } | { kind: "busy"; text: string } | { kind: "error"; text: string };

const failure = (error: unknown) => (error instanceof ApiError ? `${error.message} (${error.code})` : "the request failed");

/** v1 method comparison for the chosen network (V1-SPEC §6.2), on the forecast run named in the URL (CR-w1-web-2). */
export function MethodComparisonSection({ forecastRunId }: { forecastRunId?: string }) {
  const { network } = useNetwork();
  // A new network starts a new comparison: nothing chosen for one network carries over to another.
  return network ? <Comparison key={network.id} network={network} forecastRunId={forecastRunId} /> : null;
}

function Comparison({ network, forecastRunId }: { network: Network; forecastRunId?: string }) {
  const [scenario, setScenario] = useState<Schema["ScenarioV3"] | null>(null);
  const [shown, setShown] = useState<Shown | null>(null);
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);

  const datasetId = network.dataset_version_id;
  const blocked = !datasetId ? "Import data for this network before planning."
    : !forecastRunId ? "No forecast run chosen. Open this page from a finished forecast for this network." : null;

  async function freeze({ transferMode, retailWeights }: { transferMode: Schema["TransferMode"]; retailWeights: Schema["RetailWeights"] | null }) {
    if (!datasetId || !forecastRunId) return;
    setStatus({ kind: "busy", text: "Freezing the scenario…" });
    // A failed freeze must not leave the previous scenario looking like the current choice.
    setScenario(null);
    setShown(null);
    try {
      const frozen = await networkApi.createScenario(network.id, { dataset_version_id: datasetId, forecast_run_id: forecastRunId,
        transfer_mode: transferMode, reserve_floors: [], retail_weights: retailWeights });
      if (!alive.current) return;
      setScenario(frozen);
      setStatus({ kind: "idle" });
    } catch (error) {
      if (alive.current) setStatus({ kind: "error", text: `Scenario not frozen: ${failure(error)}.` });
    }
  }

  async function compare(measure: V1Measure) {
    if (!scenario) return;
    const methods = V1_METHODS[network.mode];
    setStatus({ kind: "busy", text: "Comparing methods… A queued or running job is not a result." });
    try {
      const accepted = await networkApi.submitComparison(network.id, { scenario_id: scenario.id, methods, measure });
      let job = await networkApi.job(accepted.job_id);
      while (!TERMINAL.has(job.state)) {
        await new Promise((resolve) => setTimeout(resolve, POLL_MS));
        if (!alive.current) return;
        job = await networkApi.job(accepted.job_id);
      }
      if (job.state !== "SUCCEEDED") throw new Error(`comparison ${job.state.replaceAll("_", " ").toLowerCase()}`);
      const saved = await networkApi.comparisonAt(accepted.result_url);
      if (!alive.current) return;
      setShown({ saved, scenario, requested: methods });
      setStatus({ kind: "idle" });
    } catch (error) {
      const text = error instanceof ApiError ? failure(error) : error instanceof Error ? error.message : "the request failed";
      if (alive.current) setStatus({ kind: "error", text: `No comparison result: ${text}. Nothing is substituted.` });
    }
  }

  return (
    <section aria-labelledby="v1-compare-heading" className="grid gap-4 rounded-lg border border-border bg-card p-3 md:p-4">
      <div className="grid gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="v1-compare-heading" className="text-base font-semibold">Method comparison · {network.name}</h2>
          {network.is_sample && <SampleBadge />}
        </div>
        <p className="text-xs text-muted-foreground">{modeSummary(network.mode)}. All methods share one frozen scenario and one feasible region.</p>
      </div>
      <div className="grid min-w-0 gap-4 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <ComparisonSetup mode={network.mode} busy={status.kind === "busy"} scenario={scenario} blocked={blocked}
          onFreeze={(options) => void freeze(options)} onCompare={(measure) => void compare(measure)} />
        <div className="grid min-w-0 content-start gap-3">
          {status.kind === "busy" && <p role="status" className="text-sm text-muted-foreground">{status.text}</p>}
          {status.kind === "error" && <p role="alert" className="text-sm">{status.text}</p>}
          {shown ? <MethodComparisonResults comparison={shown.saved} scenario={shown.scenario} requested={shown.requested} />
            : status.kind !== "busy" && <p className="text-sm text-muted-foreground">No comparison yet. Freeze a scenario, then compare methods.</p>}
        </div>
      </div>
    </section>
  );
}
