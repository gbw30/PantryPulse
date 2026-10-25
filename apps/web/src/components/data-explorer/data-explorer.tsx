"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MotionConfig } from "motion/react";
import { AppShell } from "@/components/shell/app-shell";
import { usePresenter } from "@/components/shell/presenter-session";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { AnalyticsPanel } from "./analytics-panel";
import { NetworkDemandChart } from "./forecast-chart";
import { FIXTURE_LABEL, LIVE_LABEL, VISITOR_LABEL, fallbackReasonLabel, formatInstant, providerLabel } from "./format";
import { DataExplorerHeader } from "./header";
import { KpiRow } from "./kpi-row";
import { liveExplorerSource } from "./live-source";
import { ProvenancePill, StatusGlyph } from "./marks";
import { runMethods } from "./metrics";
import { ExplorerNoticeBanner, NoticeMeta } from "./notices";
import { OperationsBoard } from "./operations";
import { SevenDayPulse } from "./pulse";
import { SitePerformanceTable } from "./site-table";
import type { ExplorerTabKey } from "./tabs";
import type { ExplorerSnapshot, Product } from "./types";

type View = Extract<ExplorerTabKey, "dashboard" | "pulse" | "operations">;
type LoadState = { status: "loading" } | { status: "ready"; snapshot: ExplorerSnapshot } | { status: "error"; code: string };

const NOTICE_LINK = "font-medium text-foreground underline underline-offset-2 outline-none focus-visible:ring-2 focus-visible:ring-ring";

function Screen({ view, initialProductId }: { view: View; initialProductId: string | null }) {
  const { expired } = usePresenter();
  const [load, setLoad] = useState<LoadState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [productId, setProductId] = useState<string | null>(initialProductId);

  // Load through the adapter. Aborting on unmount/retry means a stale response never replaces newer intent.
  useEffect(() => {
    const controller = new AbortController();
    liveExplorerSource.load(controller.signal, expired).then(
      (snapshot) => { if (!controller.signal.aborted) setLoad({ status: "ready", snapshot }); },
      (error: unknown) => {
        if (controller.signal.aborted || (error instanceof DOMException && error.name === "AbortError")) return;
        const code = error && typeof error === "object" && "code" in error && typeof error.code === "string" ? error.code : "NETWORK_ERROR";
        setLoad({ status: "error", code });
      },
    );
    return () => controller.abort();
    // `expired` is stable (useCallback in the provider).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt]);

  const snapshot = load.status === "ready" ? load.snapshot : null;
  const product: Product | null = snapshot ? snapshot.products.find((item) => item.id === productId) ?? snapshot.products[0] ?? null : null;
  const live = snapshot?.source.kind === "live" ? snapshot.source : null;
  const fixture = snapshot?.source.kind === "fixture" ? snapshot.source : null;
  const methods = snapshot ? runMethods(snapshot) : null;

  function retry() {
    setLoad({ status: "loading" });
    setAttempt((value) => value + 1);
  }

  const meta = snapshot && (
    <p data-explorer-source={snapshot.source.kind} className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-foreground">
      <ProvenancePill tone={live ? "live" : "fixture"}>{live ? LIVE_LABEL : VISITOR_LABEL}</ProvenancePill>
      {live && <span className="text-muted-foreground">Observed {formatInstant(live.observedAt, snapshot.timezone)}</span>}
    </p>
  );

  const controls = snapshot && (
    <>
      <div className="grid gap-1">
        <span id="explorer-product-label" className="text-xs font-medium text-muted-foreground">Product</span>
        <Select value={product?.id ?? ""} onValueChange={setProductId}>
          <SelectTrigger aria-labelledby="explorer-product-label" className="h-10 w-full bg-card data-[size=default]:h-10 sm:w-[232px]">
            <SelectValue placeholder="Loading products…" />
          </SelectTrigger>
          <SelectContent>
            {snapshot.products.map((item) => <SelectItem key={item.id} value={item.id}>{item.name} ({item.unitPlural})</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      {live?.forecast && (
        <p data-run-chip className="flex h-10 items-center rounded-lg border border-border bg-card px-3 text-xs text-foreground">
          <span className="grid leading-tight">
            <span className="font-medium">Forecast run {live.forecast.runId.slice(0, 8)} · recorded {formatInstant(live.forecast.recordedAt, snapshot.timezone)}</span>
            <span className="text-muted-foreground">
              {methods && methods.providers.length > 0 ? methods.providers.map(providerLabel).join(", ") : "method not recorded"}
              {methods && methods.fallbacks.length > 0 ? ` · ${methods.fallbacks.length} fallback series` : ""}
            </span>
          </span>
        </p>
      )}
    </>
  );

  return (
    <div className="flex flex-1 flex-col gap-4 px-4 pt-3 pb-6 md:gap-5 md:px-6 md:py-5">
      <DataExplorerHeader active={view} controls={controls || undefined} meta={meta || undefined} productId={product?.id ?? null} />

      {load.status === "loading" && (
        <div aria-busy="true" aria-label="Loading the Data Explorer" role="status" className="contents">
          <span className="sr-only">Loading live data…</span>
          {view === "dashboard" ? (
            <>
              <KpiRow snapshot={null} product={null} />
              <div className="grid gap-4 lg:grid-cols-[minmax(0,1.7fr)_minmax(300px,1fr)]">
                <NetworkDemandChart snapshot={null} product={null} />
                <AnalyticsPanel snapshot={null} product={null} />
              </div>
              <SitePerformanceTable snapshot={null} product={null} />
            </>
          ) : view === "pulse" ? (
            <SevenDayPulse snapshot={null} product={null} />
          ) : (
            <OperationsBoard snapshot={null} productId={null} />
          )}
          <Skeleton data-loading-slot className="h-10 w-72" />
        </div>
      )}

      {load.status === "error" && (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-pp-danger bg-card px-3 py-2.5 text-sm text-foreground">
          <StatusGlyph status="shortfall" />
          <div className="grid min-w-0 flex-1 gap-0.5">
            <p><strong className="font-semibold">Data Explorer could not load.</strong> The request did not return data, so nothing is shown in its place.</p>
            <NoticeMeta code={load.code} />
          </div>
          <Button variant="outline" size="sm" className="max-md:h-11 max-md:px-4" onClick={retry}>Retry</Button>
        </div>
      )}

      {snapshot && product && (
        <>
          {fixture && (
            <div data-explorer-notice="visitor" role="status" className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground">
              <span>
                <strong className="font-semibold">Sign in for live data.</strong> You are viewing a static design fixture:{" "}
                <span className="font-medium">{FIXTURE_LABEL}</span>. Use the presenter sign-in in the sidebar.
              </span>
            </div>
          )}
          {live?.notice && <ExplorerNoticeBanner notice={live.notice} timezone={snapshot.timezone} />}
          {snapshot.inventoryRows === 0 && (
            <p data-explorer-notice="empty_inventory" role="status" className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground">
              <StatusGlyph status="not_evaluated" />
              No inventory rows in this snapshot. Stock figures are shown as unavailable, not zero.
            </p>
          )}
          {methods && methods.fallbacks.length > 0 && (
            <div data-fallback-pill className="rounded-lg border border-pp-warning bg-card px-3 py-2 text-xs text-foreground">
              <p className="font-semibold">Fallback forecast</p>
              <ul className="mt-0.5 grid gap-0.5">
                {methods.fallbacks.map((item) => (
                  <li key={`${item.site.id}-${item.product.id}`}>
                    {item.site.shortName} ({item.product.unitPlural}): {providerLabel(item.provider)} — {fallbackReasonLabel(item.reason)}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {view === "dashboard" && (
            <>
              <KpiRow snapshot={snapshot} product={product} />
              <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1.7fr)_minmax(300px,1fr)]">
                <NetworkDemandChart snapshot={snapshot} product={product} />
                <AnalyticsPanel snapshot={snapshot} product={product} />
              </div>
              <SitePerformanceTable snapshot={snapshot} product={product} />
            </>
          )}
          {view === "pulse" && <SevenDayPulse snapshot={snapshot} product={product} />}
          {view === "operations" && <OperationsBoard snapshot={snapshot} productId={product.id} />}

          <footer className="grid gap-0.5 border-t border-border pt-3 text-xs text-muted-foreground">
            <p>
              Source: {live ? live.sourceNames.join(", ") || "presenter API" : FIXTURE_LABEL}
              {live?.forecast && <> · forecast run <span className="font-mono break-all">{live.forecast.runId}</span></>}
              {live && <> · observed {formatInstant(live.observedAt, snapshot.timezone)}</>}
              {" "}· dates are local days in {snapshot.timezone}.
            </p>
            <p>All figures are projections, not observations. Served and unmet assume no transfers; review and planning happen in the <Link className={NOTICE_LINK} href="/optimization">optimization workspace</Link>.</p>
            {live && live.warnings.length > 0 && <p>Projection warnings: {live.warnings.join("; ")}.</p>}
          </footer>
        </>
      )}
    </div>
  );
}

/** Client root for /data, /data/pulse and /data/operations. */
export function DataExplorerScreen({ view, initialProductId = null }: { view: View; initialProductId?: string | null }) {
  return (
    <MotionConfig reducedMotion="user">
      <AppShell active="data">
        <Screen view={view} initialProductId={initialProductId} />
      </AppShell>
    </MotionConfig>
  );
}
