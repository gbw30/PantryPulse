"use client";

import { useCallback, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { MotionConfig, useReducedMotion } from "motion/react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AppShell } from "@/components/shell/app-shell";
import { usePresenter } from "@/components/shell/presenter-session";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { isUuid } from "@/lib/planning-api";
import { ActionPlan } from "./action-plan";
import { ImpactFairness, NetworkOptimization, SiteRecommendations } from "./detail-tabs";
import {
  actionRows, defaultMethod, forecastProviders, formatDay, formatInstant, isTabKey, isUsable, METHOD_LABEL, planRecord, providerLabel,
  replayLabel, shortId, sortRows, TAB_KEYS, TAB_LABEL, transferModeLabel, type ActionRow, type Loaded, type Method, type SortKey, type TabKey,
} from "./model";
import type { ReviewOutcome } from "./review-dialog";
import { useCatalog, useComparison } from "./use-recommendations";
import { LINK, Notice, ProvenancePill, SolverStatus } from "./vocabulary";

function useIsDesktop() {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia("(min-width: 1024px)");
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    () => window.matchMedia("(min-width: 1024px)").matches,
    () => true,
  );
}

function Chip({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <span className="inline-flex items-baseline gap-1.5 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium text-foreground">{value}</span>
    </span>
  );
}

/** R2: everything the plan claims to be, in one wrapping line of labelled chips. */
function PlanContext({ loaded, method }: { loaded: Loaded; method: Method }) {
  const outcome = loaded.comparison.result.methods.find((item) => item.method === method);
  const payload = loaded.scenario.payload;
  const providers = forecastProviders(loaded);
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 rounded-lg border border-border bg-card px-3 py-2">
      <Chip label="Scenario" value={shortId(loaded.comparison.scenario_id)} />
      <Chip label="Mode" value={transferModeLabel(loaded.comparison.result.transfer_mode)} />
      <Chip label="Window" value={`${payload.planning_days} days from ${formatDay(payload.package.first_planning_date)}`} />
      <Chip label="Forecast method" value={providers.length ? providers.map(providerLabel).join(", ") : "Unavailable"} />
      <Chip label="Method" value={METHOD_LABEL[method]} />
      {outcome && <SolverStatus method={outcome} />}
      {loaded.comparison.stale && <Chip label="Flag" value="Stale sources" />}
      {loaded.comparison.historical && <Chip label="Flag" value="Historical" />}
      <ProvenancePill>Simulated data</ProvenancePill>
    </div>
  );
}

function LoadingBlock() {
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]" aria-hidden="true">
      <Skeleton className="h-72 rounded-xl" />
      <Skeleton className="h-72 rounded-xl" />
    </div>
  );
}

export function RecommendationsScreen() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const reduced = useReducedMotion() ?? false;
  const isDesktop = useIsDesktop();
  const { state: presenterState, expired } = usePresenter();
  const presenter = presenterState === "presenter";

  const tab: TabKey = isTabKey(params.get("tab")) ? (params.get("tab") as TabKey) : "action-plan";
  const urlComparison = params.get("comparison");

  const setParam = useCallback((key: string, value: string | null) => {
    const next = new URLSearchParams(params.toString());
    if (value === null) next.delete(key); else next.set(key, value);
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  }, [params, pathname, router]);

  const { state: catalog, retry: retryCatalog } = useCatalog(presenter, expired);

  // Saved comparison: URL wins when valid; otherwise newest (catalog order).
  const comparisonId = useMemo(() => {
    if (catalog.kind !== "ready") return null;
    if (isUuid(urlComparison) && catalog.comparisons.some((item) => item.id === urlComparison)) return urlComparison;
    return catalog.comparisons[0]?.id ?? null;
  }, [catalog, urlComparison]);

  const productNames = catalog.kind === "ready" ? catalog.productNames : null;
  const { state: comparisonState, retry: retryComparison } = useComparison(presenter ? comparisonId : null, productNames, expired);
  const loaded = comparisonState.kind === "ready" ? comparisonState.loaded : null;

  const [methodChoice, setMethodChoice] = useState<Method | null>(null);
  const [sort, setSort] = useState<SortKey>("deficit");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [siteId, setSiteId] = useState<string | null>(null);
  // Reviewed markers live for this page session only (Q-54-4; no read-back API yet).
  const [reviewedPlans, setReviewedPlans] = useState<Set<string>>(new Set());
  const [reviewStale, setReviewStale] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);
  const previewRef = useRef<HTMLElement | null>(null);

  // A different comparison resets per-plan view state (render-time reset, no effect).
  const [viewFor, setViewFor] = useState(comparisonId);
  if (viewFor !== comparisonId) {
    setViewFor(comparisonId);
    setMethodChoice(null); setSelectedKey(null); setSiteId(null); setReviewStale(false);
  }

  const method = loaded ? methodChoice ?? defaultMethod(loaded.comparison.result.methods) : null;
  const outcome = loaded && method ? loaded.comparison.result.methods.find((item) => item.method === method) ?? null : null;
  const usable = outcome ? isUsable(outcome) : false;
  const rows = useMemo(() => (loaded && outcome && usable ? sortRows(actionRows(loaded, outcome), sort) : []), [loaded, outcome, usable, sort]);
  const selected = rows.find((row) => row.key === selectedKey) ?? rows[0] ?? null;
  const plan = loaded && method && usable ? planRecord(loaded, method) : null;

  const selectRow = useCallback((row: ActionRow) => {
    setSelectedKey(row.key);
    // On mobile the preview follows the list; bring it into view without moving focus.
    if (!isDesktop) previewRef.current?.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
  }, [isDesktop, reduced]);

  const onReviewOutcome = useCallback((result: ReviewOutcome) => {
    if (result === "reviewed" && plan) setReviewedPlans((prev) => new Set(prev).add(plan.id));
    if (result === "stale") setReviewStale(true);
    if (result === "expired") { setSessionExpired(true); expired(); }
  }, [plan, expired]);

  const horizon = loaded ? `${loaded.scenario.payload.planning_days}-day window` : undefined;

  let body: React.ReactNode;
  if (presenterState === "checking") {
    body = <LoadingBlock />;
  } else if (!presenter || sessionExpired) {
    body = (
      <Notice kind={sessionExpired ? "expired" : "visitor"} title={sessionExpired ? "Presenter session expired." : "Saved plans are presenter-only."}>
        <p>
          {sessionExpired
            ? "Your session expired or was signed out elsewhere; nothing was recorded. Sign in again from the sidebar to continue."
            : "Recommendations come from saved, independently verified allocation plans, which this demo keeps behind the presenter session. Sign in from the sidebar footer to load them; visitors stay read-only and no sample plan is shown."}
        </p>
      </Notice>
    );
  } else if (catalog.kind === "loading" || (catalog.kind === "ready" && comparisonId && comparisonState.kind === "loading")) {
    body = <LoadingBlock />;
  } else if (catalog.kind === "error" || comparisonState.kind === "error") {
    const code = catalog.kind === "error" ? catalog.code : comparisonState.kind === "error" ? comparisonState.code : "";
    body = (
      <Alert variant="destructive">
        <AlertTitle className="text-foreground">Could not load saved plans.</AlertTitle>
        <AlertDescription>
          <p>The request did not complete; nothing on this screen is a plan. Error code <code className="font-mono text-[11px]">{code}</code>.</p>
          <Button variant="outline" size="sm" onClick={() => (catalog.kind === "error" ? retryCatalog() : retryComparison())}>Retry</Button>
        </AlertDescription>
      </Alert>
    );
  } else if (catalog.kind === "ready" && !comparisonId) {
    body = (
      <Notice kind="empty" title="No saved comparison yet.">
        <p>Recommendations read a saved method comparison. <Link className={LINK} href="/scenarios">Run a comparison in Scenario Lab</Link>, then return here.</p>
      </Notice>
    );
  } else if (comparisonState.kind === "computing") {
    body = (
      <Notice kind="computing" title="This comparison is still computing.">
        <p>The job has not published a saved result yet (COMPARISON_NOT_PUBLISHED). No plan is shown until it is saved and independently replayed.</p>
        <Button variant="outline" size="sm" className="w-fit" onClick={retryComparison}>Check again</Button>
      </Notice>
    );
  } else if (loaded && method && outcome) {
    const failedMethods = loaded.comparison.result.methods.filter((item) => !isUsable(item));
    body = (
      <div className="grid gap-4">
        {(loaded.comparison.stale || loaded.comparison.historical) && (
          <Notice kind="stale" tone="warning" title="Sources changed since this scenario was frozen; review is still a simulation.">
            <p>The plan below reads the archived frozen inputs, not current data.</p>
          </Notice>
        )}
        {loaded.comparison.result.outcome === "PARTIAL" && (
          <Notice kind="partial" tone="warning" title="One method failed in this comparison.">
            <p>{failedMethods.map((item) => `${METHOD_LABEL[item.method]}: ${item.error_code ?? item.outcome}`).join(" · ")}. The verified method stays usable; no substitute is shown.</p>
          </Notice>
        )}
        {loaded.comparison.result.outcome === "FAILED" && (
          <Notice kind="failed" tone="danger" title="Neither method produced a verified plan.">
            <p>{loaded.comparison.result.methods.map((item) => `${METHOD_LABEL[item.method]}: ${item.error_code ?? item.outcome}`).join(" · ")}. No actions are listed; there is no plan to review.</p>
          </Notice>
        )}
        <PlanContext loaded={loaded} method={method} />
        <div className="flex flex-wrap items-center gap-2">
          <span id="rec-method-label" className="text-xs font-medium text-muted-foreground">Plan method</span>
          <div role="group" aria-labelledby="rec-method-label" aria-label="Plan method" className="inline-flex rounded-lg border border-border bg-card p-0.5">
            {loaded.comparison.result.methods.map((item) => (
              <Button key={item.method} variant="ghost" size="sm" aria-pressed={item.method === method}
                className={cn("h-8 rounded-md px-3", item.method === method && "bg-pp-teal-soft text-foreground hover:bg-pp-teal-soft")}
                onClick={() => { setMethodChoice(item.method); setSelectedKey(null); }}>
                {METHOD_LABEL[item.method]}{!isUsable(item) && <span className="sr-only"> (no verified plan)</span>}
              </Button>
            ))}
          </div>
        </div>
        <Tabs value={tab} onValueChange={(value) => setParam("tab", value === "action-plan" ? null : value)}>
          <TabsList variant="line" className="max-w-full overflow-x-auto">
            {TAB_KEYS.map((key) => <TabsTrigger key={key} value={key} className="flex-none px-3">{TAB_LABEL[key]}</TabsTrigger>)}
          </TabsList>
          <TabsContent value="action-plan" className="pt-3">
            {usable ? (
              <ActionPlan loaded={loaded} method={outcome} rows={rows} selected={selected} onSelect={selectRow} sort={sort} onSort={setSort}
                isDesktop={isDesktop} previewRef={previewRef} reduced={reduced} presenter={presenter}
                plan={plan}
                reviewed={plan !== null && reviewedPlans.has(plan.id)} reviewStale={reviewStale}
                onReviewOutcome={onReviewOutcome} onReload={() => { setReviewStale(false); retryComparison(); }} />
            ) : (
              <Notice kind="method-unavailable" tone="warning" title={`${METHOD_LABEL[method]} has no verified plan for this comparison.`}>
                <p>
                  {outcome.error_code ? <>Error code <code className="font-mono">{outcome.error_code}</code>. </> : null}
                  Outcome {outcome.outcome}, solver status {outcome.native_status ?? "none"}, independent replay {replayLabel(outcome)}. No actions are shown for it.
                </p>
              </Notice>
            )}
          </TabsContent>
          <TabsContent value="sites" className="pt-3">
            {usable ? (
              <SiteRecommendations loaded={loaded} method={outcome} selectedKey={selected?.key ?? null} onSelect={(row) => setSelectedKey(row.key)}
                siteId={siteId ?? loaded.scenario.payload.package.sites.find((site) => site.role === "HUB")?.id ?? loaded.scenario.payload.package.sites[0]?.id ?? ""}
                onSite={setSiteId} />
            ) : <Notice kind="method-unavailable" tone="warning" title={`${METHOD_LABEL[method]} has no verified plan; there is nothing to filter by site.`} />}
          </TabsContent>
          <TabsContent value="network" className="pt-3"><NetworkOptimization loaded={loaded} method={outcome} /></TabsContent>
          <TabsContent value="fairness" className="pt-3"><ImpactFairness loaded={loaded} method={outcome} /></TabsContent>
        </Tabs>
      </div>
    );
  } else {
    body = <LoadingBlock />;
  }

  return (
    <MotionConfig reducedMotion="user">
      <AppShell active="recommendations" horizonLabel={horizon}>
        <div className="flex flex-1 flex-col gap-4 px-4 pt-3 pb-6 md:px-6 md:py-5">
          <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div className="min-w-0">
              <p className="font-condensed text-xs font-semibold tracking-[0.16em] text-muted-foreground uppercase">Corrective-action review</p>
              <h1 className="text-[26px] leading-tight font-semibold tracking-tight md:text-[28px]">Recommendations</h1>
              <p className="text-sm text-muted-foreground">Review feasible options and their projected impact before any operational decision.</p>
            </div>
            {presenter && catalog.kind === "ready" && catalog.comparisons.length > 0 && (
              <div className="grid w-full gap-1 md:w-[320px]">
                <span id="rec-comparison-label" className="text-xs font-medium text-muted-foreground">Saved comparison</span>
                <Select value={comparisonId ?? ""} onValueChange={(value) => setParam("comparison", value)}>
                  <SelectTrigger aria-labelledby="rec-comparison-label" aria-label="Saved comparison" className="h-10 w-full bg-card data-[size=default]:h-10"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {catalog.comparisons.map((item) => (
                      <SelectItem key={item.id} value={item.id}>{item.label} · {formatInstant(item.recorded_at)} · {shortId(item.id)}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </header>
          {body}
        </div>
      </AppShell>
    </MotionConfig>
  );
}
