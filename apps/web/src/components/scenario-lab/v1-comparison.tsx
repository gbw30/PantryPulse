"use client";

import { useEffect, useRef, useState } from "react";
import { SampleBadge, useNetwork } from "@/components/shell/network-switcher";
import { Button } from "@/components/ui/button";
import { modeSummary } from "@/lib/mode-vocabulary";
import { JOB_ACTIVE, JOB_ENDED, networkApi, type Network } from "@/lib/network-api";
import { ApiError, type Schema } from "@/lib/planning-api";
import { V1_METHODS, type V1Measure, type V1Method } from "./model";
import { MethodComparisonResults } from "./results";
import { ComparisonSetup, type FreezeOptions } from "./wizard";

const POLL_MS = 1000;

type Shown = { saved: Schema["SavedComparisonV3"]; scenario: Schema["ScenarioV3"]; requested: V1Method[] };
type Job = { jobId: string; resultUrl: string; scenario: Schema["ScenarioV3"]; requested: V1Method[] };
// "lost": the accepted job is durable and may still finish, so comparing again would queue a duplicate.
type Status = { kind: "idle" } | { kind: "busy"; text: string } | { kind: "error"; text: string } | { kind: "lost"; job: Job; reason: string };

const words = (code: string) => code.replaceAll("_", " ").toLowerCase();
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

  async function freeze({ transferMode, retailWeights, planningDays, policy }: FreezeOptions) {
    if (!datasetId || !forecastRunId) return;
    setStatus({ kind: "busy", text: "Freezing the scenario…" });
    // A failed freeze must not leave the previous scenario looking like the current choice.
    setScenario(null);
    setShown(null);
    try {
      const frozen = await networkApi.createScenario(network.id, { dataset_version_id: datasetId, forecast_run_id: forecastRunId,
        transfer_mode: transferMode, reserve_floors: [], retail_weights: retailWeights,
        // Retail must not send either field (WINDOW_AND_POLICY_ONLY_IN_PANTRY).
        ...(planningDays !== null && policy ? { planning_days: planningDays, policy } : {}) });
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
      await follow({ jobId: accepted.job_id, resultUrl: accepted.result_url, scenario, requested: methods });
    } catch (error) {
      if (alive.current) setStatus({ kind: "error", text: `No comparison result: ${failure(error)}. Nothing is substituted.` });
    }
  }

  /** Poll an accepted job to its result. A failed read loses contact with the job; it does not end it. */
  async function follow(job: Job) {
    setStatus({ kind: "busy", text: "Comparing methods… A queued or running job is not a result." });
    try {
      let { state } = await networkApi.job(job.jobId);
      while (JOB_ACTIVE.has(state)) {
        await new Promise((resolve) => setTimeout(resolve, POLL_MS));
        if (!alive.current) return;
        ({ state } = await networkApi.job(job.jobId));
      }
      if (!JOB_ENDED.has(state)) {
        if (alive.current) setStatus({ kind: "lost", job, reason: `The comparison job reported a status this page doesn't know (${words(state)}).` });
        return;
      }
      if (state !== "SUCCEEDED") {
        if (alive.current) setStatus({ kind: "error", text: `No comparison result: comparison ${words(state)}. Nothing is substituted.` });
        return;
      }
      const saved = await networkApi.comparisonAt(job.resultUrl);
      if (!alive.current) return;
      setShown({ saved, scenario: job.scenario, requested: job.requested });
      setStatus({ kind: "idle" });
    } catch (error) {
      if (alive.current) setStatus({ kind: "lost", job, reason: `Lost contact with the comparison job (${words(error instanceof ApiError ? error.code : "REQUEST_FAILED")}).` });
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
        <ComparisonSetup mode={network.mode} busy={status.kind === "busy" || status.kind === "lost"} scenario={scenario} blocked={blocked}
          onFreeze={(options) => void freeze(options)} onCompare={(measure) => void compare(measure)} />
        <div className="grid min-w-0 content-start gap-3">
          {status.kind === "busy" && <p role="status" className="text-sm text-muted-foreground">{status.text}</p>}
          {status.kind === "error" && <p role="alert" className="text-sm">{status.text}</p>}
          {status.kind === "lost" && (
            <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-pp-warning bg-card px-4 py-3 text-sm">
              {status.reason} It may still finish; check again before comparing again.
              <Button variant="outline" size="sm" onClick={() => { const { job } = status; void follow(job); }}>Check again</Button>
            </div>
          )}
          {shown ? <MethodComparisonResults comparison={shown.saved} scenario={shown.scenario} requested={shown.requested} />
            : status.kind !== "busy" && status.kind !== "lost" && <p className="text-sm text-muted-foreground">No comparison yet. Freeze a scenario, then compare methods.</p>}
        </div>
      </div>
    </section>
  );
}
