"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { currentRunId, ForecastRunsNote, useForecastRun } from "@/components/forecast/forecast-run";
import { InboundNote, SampleBadge, useNetwork } from "@/components/shell/network-switcher";
import { networkApi, type Network } from "@/lib/network-api";
import { ApiError, type Schema } from "@/lib/planning-api";
import { NOT_EVALUATED, NOT_MEASURABLE, TrustPanel, ZERO_ACTUAL } from "./trust-panel";

type Run = Schema["NetworkForecastRun"];
type Backtest = Schema["BacktestResult"];
type Label = (locationId: string) => string;

const seriesKey = (locationId: string, productId: string) => `${locationId}\u0000${productId}`;
const words = (code: string) => code.replaceAll("_", " ").toLowerCase();

/** A location's pooled score in one unit, in the trust panel's words. */
function locationScore(score: Schema["BacktestScore"]) {
  if (score.status === "not_evaluated_zero_actual") return ZERO_ACTUAL;
  if (score.status !== "evaluated") return NOT_EVALUATED;
  if (score.wape_pct === null) return NOT_MEASURABLE;
  const weeks = score.origins_evaluated === 1 ? "the last week" : `the last ${score.origins_evaluated} weeks`;
  return `off by about ${Math.round(Math.abs(Number(score.wape_pct)))}% over ${weeks}`;
}

/**
 * Accuracy per location × product on the user's own history, each with its run's method (CR-w1-web-4), the
 * pooled score per location and unit, and the series that were not forecast.
 */
function BacktestSummary({ backtest, run, label }: { backtest: Backtest; run: Run; label: Label }) {
  const demand = new Map(run.series.filter((s) => s.kind === "demand").map((s) => [seriesKey(s.location_id, s.product_id), s]));
  const donations = new Map(run.series.filter((s) => s.kind === "donation" && s.status === "AVAILABLE")
    .map((s) => [seriesKey(s.location_id, s.product_id), s]));
  // One product's donation forecast over its days, in its own unit; never added across products.
  const donation = (locationId: string, productId: string) => {
    const s = donations.get(seriesKey(locationId, productId));
    return s ? { units: s.points.reduce((sum, p) => sum + p.central_estimate, 0), unit: s.unit } : null;
  };
  return (
    <div className="grid gap-3">
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {backtest.series.map((s) => (
          <TrustPanel key={`${s.location_id}:${s.product_id}`} label={`${label(s.location_id)} · ${s.product_id}`} basis={s.basis} score={s.score}
            method={demand.get(seriesKey(s.location_id, s.product_id)) ?? null} donationForecast={donation(s.location_id, s.product_id)} />
        ))}
      </div>
      {backtest.locations.length > 0 && (
        <div className="grid gap-1">
          <div className="overflow-x-auto rounded-lg border border-border" role="group" aria-label="Scrollable accuracy by location" tabIndex={0}>
            <table className="w-full min-w-[32rem] border-collapse text-left text-sm">
              <caption className="px-3 pt-2 text-left text-sm font-medium">Accuracy by location and unit</caption>
              <thead className="text-xs text-muted-foreground">
                <tr>
                  <th scope="col" className="px-3 py-2 font-medium">Location</th>
                  <th scope="col" className="px-3 py-2 font-medium">Unit</th>
                  <th scope="col" className="px-3 py-2 font-medium">Series</th>
                  <th scope="col" className="px-3 py-2 font-medium">Accuracy</th>
                </tr>
              </thead>
              <tbody>
                {backtest.locations.map((row) => (
                  <tr key={`${row.location_id}:${row.unit}`} className="border-t border-border">
                    <th scope="row" className="px-3 py-2 font-normal">{label(row.location_id)}</th>
                    <td className="px-3 py-2">{row.unit}</td>
                    <td className="px-3 py-2 tabular-nums">{row.series_count} series</td>
                    <td className="px-3 py-2">{locationScore(row.score)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-muted-foreground">Each row pools that location&apos;s scored demand series in one unit; different units are never pooled. Measured on this network&apos;s past days; no claim about future accuracy.</p>
        </div>
      )}
      {backtest.ineligible.length > 0 && (
        <div className="grid gap-1 text-sm">
          <p className="font-medium">Not forecast</p>
          <ul aria-label="Not forecast" className="ml-5 list-disc text-muted-foreground">
            {backtest.ineligible.map((row) => <li key={`${row.location_id}:${row.product_id}`}>{label(row.location_id)} · {row.product_id}: {row.reason}</li>)}
          </ul>
          <p className="text-xs text-muted-foreground">These are never forecast from zeros.</p>
        </div>
      )}
    </div>
  );
}

type Load = { status: "loading" } | { status: "error"; code: string } | { status: "other_network" } | { status: "ready"; run: Run; backtest: Backtest };
type Names = { status: "loading" } | { status: "error"; code: string } | { status: "ready"; byId: Map<string, string> };

/** The chosen v1 network's forecast trust, for the newest forecast run of its current data (W4-02). */
export function ForecastTrustSection() {
  const { network } = useNetwork();
  return network ? <TrustSection key={network.id} network={network} /> : null;
}

function TrustSection({ network }: { network: Network }) {
  const { runs, reload } = useForecastRun(network);
  const forecastRunId = currentRunId(runs);
  return (
    <section aria-labelledby="trust-heading" className="grid gap-3 rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="trust-heading" className="text-lg font-semibold">Forecast trust · {network.name}</h2>
        {network.is_sample && <SampleBadge />}
      </div>
      <InboundNote provided={network.inbound_file_provided} />
      <p className="text-xs text-muted-foreground">Forecasts are projections. Accuracy is measured over the last 4 weekly origins of this network&apos;s history (needs 35+ days).</p>
      <ForecastRunsNote runs={runs} onRetry={reload} />
      {/* A new run starts from "loading": the previous run's accuracy is never shown under it. */}
      {forecastRunId && <Trust key={forecastRunId} network={network} forecastRunId={forecastRunId} />}
    </section>
  );
}

function Trust({ network, forecastRunId }: { network: Network; forecastRunId: string }) {
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [names, setNames] = useState<Names>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    // The run names its forecast job, whose backtest scores the same series.
    networkApi.forecastRun(network.id, forecastRunId).then(async (run) => {
      if (!active) return;
      if (run.network_id !== network.id) { setLoad({ status: "other_network" }); return; }
      const backtest = await networkApi.backtest(run.job_id);
      if (active) setLoad({ status: "ready", run, backtest });
    }).catch((error: unknown) => {
      if (active) setLoad({ status: "error", code: error instanceof ApiError ? error.code : "REQUEST_FAILED" });
    });
    return () => { active = false; };
  }, [network.id, forecastRunId, attempt]);
  useEffect(() => {
    let active = true;
    networkApi.locations(network.id).then(
      (list) => { if (active) setNames({ status: "ready", byId: new Map(list.locations.map((l) => [l.location_id, l.name])) }); },
      (error: unknown) => { if (active) setNames({ status: "error", code: error instanceof ApiError ? error.code : "REQUEST_FAILED" }); },
    );
    return () => { active = false; };
  }, [network.id]);
  const label: Label = (id) => {
    const name = names.status === "ready" ? names.byId.get(id) : undefined;
    return name ? `${name} (${id})` : id;
  };

  return (
    <>
      {names.status === "error" && (
        <p className="text-xs text-muted-foreground">Location names unavailable ({words(names.code)}). Locations are shown by ID.</p>
      )}
      {load.status === "loading" && <p role="status" className="text-sm text-muted-foreground">Loading forecast accuracy…</p>}
      {load.status === "error" && (
        <div role="alert" className="flex flex-wrap items-center gap-3 text-sm">
          Forecast accuracy unavailable ({words(load.code)}).
          <Button variant="outline" size="sm" onClick={() => { setLoad({ status: "loading" }); setAttempt((n) => n + 1); }}>Retry</Button>
        </div>
      )}
      {load.status === "ready" && <BacktestSummary backtest={load.backtest} run={load.run} label={label} />}
      {load.status === "other_network" && (
        <p className="text-sm text-muted-foreground">This forecast belongs to another network. Choose that network in the sidebar.</p>
      )}
    </>
  );
}
