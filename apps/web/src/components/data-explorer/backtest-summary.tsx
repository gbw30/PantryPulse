"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { SampleBadge, useNetwork } from "@/components/shell/network-switcher";
import { networkApi, type Network } from "@/lib/network-api";
import { ApiError, type Schema } from "@/lib/planning-api";
import { TrustPanel } from "./trust-panel";

/** Accuracy per location × product on the user's own history, plus the series that were not forecast. */
export function BacktestSummary({ backtest }: { backtest: Schema["BacktestResult"] }) {
  return (
    <div className="grid gap-3">
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {backtest.series.map((s) => (
          // Method details need the run's series (CR-w1-web-4); the backtest alone carries basis and score.
          <TrustPanel key={`${s.location_id}:${s.product_id}`} label={`${s.location_id} · ${s.product_id}`} basis={s.basis} score={s.score} method={null} donationForecast={null} />
        ))}
      </div>
      {backtest.ineligible.length > 0 && (
        <div className="grid gap-1 text-sm">
          <p className="font-medium">Not forecast</p>
          <ul aria-label="Not forecast" className="ml-5 list-disc text-muted-foreground">
            {backtest.ineligible.map((row) => <li key={`${row.location_id}:${row.product_id}`}>{row.location_id} · {row.product_id}: {row.reason}</li>)}
          </ul>
          <p className="text-xs text-muted-foreground">These are never forecast from zeros.</p>
        </div>
      )}
    </div>
  );
}

type Load = { status: "loading" } | { status: "error"; code: string } | { status: "ready"; backtest: Schema["BacktestResult"] };

/** The chosen v1 network's forecast trust for one forecast job (from the URL until CR-w1-web-2). */
export function ForecastTrustSection({ forecastJobId }: { forecastJobId?: string }) {
  const { network } = useNetwork();
  // A new job starts from "loading": the previous job's accuracy is never shown under it.
  return network ? <Trust key={forecastJobId ?? ""} network={network} forecastJobId={forecastJobId} /> : null;
}

function Trust({ network, forecastJobId }: { network: Network; forecastJobId?: string }) {
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!forecastJobId) return;
    let active = true;
    networkApi.backtest(forecastJobId).then(
      (backtest) => { if (active) setLoad({ status: "ready", backtest }); },
      (error: unknown) => { if (active) setLoad({ status: "error", code: error instanceof ApiError ? error.code : "REQUEST_FAILED" }); },
    );
    return () => { active = false; };
  }, [forecastJobId, attempt]);

  return (
    <section aria-labelledby="trust-heading" className="grid gap-3 rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="trust-heading" className="text-lg font-semibold">Forecast trust · {network.name}</h2>
        {network.is_sample && <SampleBadge />}
      </div>
      <p className="text-xs text-muted-foreground">Forecasts are projections. Accuracy is measured over the last 4 weekly origins of your own history (needs 35+ days).</p>
      {!forecastJobId && <p className="text-sm text-muted-foreground">Run a forecast for this network to see how far to trust it.</p>}
      {forecastJobId && load.status === "loading" && <p role="status" className="text-sm text-muted-foreground">Loading forecast accuracy…</p>}
      {forecastJobId && load.status === "error" && (
        <div role="alert" className="flex flex-wrap items-center gap-3 text-sm">
          Forecast accuracy unavailable ({load.code.replaceAll("_", " ").toLowerCase()}).
          <Button variant="outline" size="sm" onClick={() => { setLoad({ status: "loading" }); setAttempt((n) => n + 1); }}>Retry</Button>
        </div>
      )}
      {forecastJobId && load.status === "ready" && load.backtest.network_id === network.id && <BacktestSummary backtest={load.backtest} />}
      {forecastJobId && load.status === "ready" && load.backtest.network_id !== network.id && (
        <p className="text-sm text-muted-foreground">This forecast belongs to another network. Choose that network in the sidebar.</p>
      )}
    </section>
  );
}
