import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePresenterOptional } from "@/components/shell/presenter-session";
import { Button } from "@/components/ui/button";
import { JOB_ACTIVE, networkApi, type Network } from "@/lib/network-api";
import { ApiError, type Schema } from "@/lib/planning-api";

// W4-02 (Gabriel, 2026-11-10): the app runs a network's forecast (V1-SPEC journey step 3) and every v1 view
// uses the newest published run for the network's current data, read from GET /networks/{id}/forecasts.

type Summary = Schema["ForecastRunSummary"];
type State = Schema["AttemptState"];
export type ForecastRuns = { status: "loading" } | { status: "error"; code: string }
  | { status: "ready"; current: Summary | null; latest: Summary | null };

const POLL_MS = 2000;
const words = (code: string) => code.replaceAll("_", " ").toLowerCase();
const failure = (error: unknown) => (error instanceof ApiError ? `${error.message} (${error.code})` : "the request failed");
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * The forecast runs of the network's current dataset version: `current` is the newest published run, `latest`
 * the newest of any state, so a forecast still running after a reload shows as running. `reload` keeps the
 * runs shown until the new list arrives.
 */
export function useForecastRun(network: Network) {
  // Keyed by network and dataset version: runs listed for other data are never shown as this data's runs.
  const key = `${network.id}:${network.dataset_version_id ?? ""}`;
  const [loaded, setLoaded] = useState<{ key: string; runs: ForecastRuns } | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    networkApi.forecastRuns(network.id).then(
      (list) => {
        const mine = list.runs.filter((r) => r.dataset_version_id === network.dataset_version_id);
        if (active) setLoaded({ key, runs: { status: "ready", current: mine.find((r) => r.forecast_run_id !== null) ?? null, latest: mine[0] ?? null } });
      },
      (error: unknown) => { if (active) setLoaded({ key, runs: { status: "error", code: error instanceof ApiError ? error.code : "REQUEST_FAILED" } }); },
    );
    return () => { active = false; };
  }, [key, network.id, network.dataset_version_id, attempt]);
  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  const runs: ForecastRuns = loaded?.key === key ? loaded.runs : { status: "loading" };
  return { runs, reload };
}

/** The forecast run a view uses, or null while loading, after an error or when there is none. */
export const currentRunId = (runs: ForecastRuns) => (runs.status === "ready" ? runs.current?.forecast_run_id ?? null : null);

/** What a view shows instead of its forecast content: loading, an error with retry, or no run yet (pointing to Overview). */
export function ForecastRunsNote({ runs, onRetry, none }: { runs: ForecastRuns; onRetry: () => void; none?: React.ReactNode }) {
  if (runs.status === "loading") return <p role="status" className="text-sm text-muted-foreground">Loading this network&apos;s forecast…</p>;
  if (runs.status === "error") {
    return (
      <div role="alert" className="flex flex-wrap items-center gap-3 text-sm">
        Forecast runs unavailable ({words(runs.code)}).
        <Button variant="outline" size="sm" onClick={onRetry}>Retry</Button>
      </div>
    );
  }
  if (runs.current) return null;
  return (
    <p className="text-sm text-muted-foreground">
      {none ?? <>No forecast for this network yet. <Link href="/overview" className="font-medium text-foreground underline underline-offset-2">Run one on the Overview</Link>.</>}
    </p>
  );
}

type Phase = { kind: "idle" } | { kind: "starting" } | { kind: "following"; jobId: string; state: State }
  | { kind: "ended"; state: State } | { kind: "current" } | { kind: "error"; text: string };

function initial(latest: Summary | null): Phase {
  if (!latest) return { kind: "idle" };
  if (JOB_ACTIVE.has(latest.state)) return { kind: "following", jobId: latest.job_id, state: latest.state };
  return latest.state === "SUCCEEDED" ? { kind: "idle" } : { kind: "ended", state: latest.state };
}

const following = { QUEUED: "Forecast queued…", RUNNING: "Forecast running…", STOPPING: "Forecast stopping…" } as Record<State, string>;

/**
 * Presenter only: run a forecast for the network's current data, follow its job (GET /jobs/{id}) and call
 * `onDone` once it ends, so the views read the new run. `latest` resumes a forecast that was already running.
 */
export function RunForecast({ network, latest, onDone }: { network: Network; latest: Summary | null; onDone: () => void }) {
  const presenter = usePresenterOptional()?.state === "presenter";
  const [phase, setPhase] = useState<Phase>(() => initial(latest));
  const jobId = phase.kind === "following" ? phase.jobId : null;

  useEffect(() => {
    if (!jobId) return;
    let active = true;
    void (async () => {
      try {
        for (;;) {
          const job = await networkApi.job(jobId);
          if (!active) return;
          if (!JOB_ACTIVE.has(job.state)) {
            setPhase({ kind: "ended", state: job.state });
            onDone();
            return;
          }
          setPhase({ kind: "following", jobId, state: job.state });
          await sleep(POLL_MS);
          if (!active) return;
        }
      } catch (error) {
        if (active) setPhase({ kind: "error", text: `Lost track of the forecast (${failure(error)}). It may still finish; reload this page to check.` });
      }
    })();
    return () => { active = false; };
  }, [jobId, onDone]);

  const dataset = network.dataset_version_id;
  if (!presenter) return null;
  if (!dataset) return <p className="text-sm text-muted-foreground">Import this network&apos;s data before forecasting.</p>;

  async function run(datasetVersionId: string) {
    setPhase({ kind: "starting" });
    try {
      const accepted = await networkApi.submitForecast(network.id, { dataset_version_id: datasetVersionId });
      // The API reuses a finished run with the same input (jobs.py, `replayed`): nothing new was run.
      if (accepted.replayed && accepted.state === "SUCCEEDED") {
        setPhase({ kind: "current" });
        onDone();
        return;
      }
      setPhase({ kind: "following", jobId: accepted.job_id, state: accepted.state });
    } catch (error) {
      setPhase({ kind: "error", text: `Forecast not started: ${failure(error)}.` });
    }
  }

  const busy = phase.kind === "starting" || phase.kind === "following";
  return (
    <div className="flex flex-wrap items-center gap-3">
      {/* Busy stays focusable (aria-disabled): disabling the focused button would drop keyboard focus to the page. */}
      <Button size="sm" className="aria-disabled:opacity-50" aria-disabled={busy || undefined} onClick={busy ? undefined : () => void run(dataset)}>Run forecast</Button>
      {phase.kind === "starting" && <p role="status" className="text-sm">Starting the forecast…</p>}
      {phase.kind === "following" && <p role="status" className="text-sm">{following[phase.state] ?? `Forecast ${words(phase.state)}…`}</p>}
      {phase.kind === "ended" && phase.state === "SUCCEEDED" && <p role="status" className="text-sm">Forecast finished. The views below use the new run.</p>}
      {phase.kind === "current" && <p role="status" className="text-sm">The forecast is already up to date with the current data.</p>}
      {phase.kind === "ended" && phase.state !== "SUCCEEDED" && (
        <p role="alert" className="text-sm">The forecast did not finish ({words(phase.state)}). Nothing changed; run it again.</p>
      )}
      {phase.kind === "error" && <p role="alert" className="text-sm">{phase.text}</p>}
    </div>
  );
}
