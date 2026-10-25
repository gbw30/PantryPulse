"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MotionConfig } from "motion/react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { AppShell } from "@/components/shell/app-shell";
import { usePresenter } from "@/components/shell/presenter-session";
import { ProvenancePill } from "@/components/overview/provenance-pill";
import { ApiError, TERMINAL_JOB_STATES, demoForecastRequest, isUuid, planningApi, type Methodology, type Schema } from "@/lib/planning-api";
import { CommonDifferences, EnforcedConstraints, MethodGoalTable, Provenance, SolverStatusTable, TransferDiffTable } from "./evidence";
import { MODE_LABEL, joinGoals, methodOutcome, shortId, usableMetrics, when, type ProductInfo, type SiteInfo } from "./model";
import { ComparisonRail, HatchDefs, KeyTradeoffs, MethodPairHeader, ProjectedFillRateBySite, ScenarioResultsSummary } from "./results";
import { GuidedScenarioStepper, modifierKey, type Draft } from "./wizard";

type Catalog = Schema["PlanningCatalog"];
type Network = Schema["ForecastCatalog"];
type Scenario = Schema["ScenarioResult"];
type Comparison = Schema["SavedComparison"];
type Job = Schema["ForecastJob"];
type Active = { id: string; kind: "comparison" | "forecast" };
type Notice = { title: string; detail?: string; code?: string; retry?: "load" | "poll" };

const STATE_LABEL: Record<Schema["AttemptState"], string> = {
  QUEUED: "Queued", RUNNING: "Running", STOPPING: "Stopping", SUCCEEDED: "Succeeded — results saved", FAILED: "Failed",
  TIMED_OUT: "Timed out", INTERRUPTED: "Interrupted", CANCELLED: "Cancelled", EXPIRED: "Expired",
};

function describe(error: unknown, action: string): Notice {
  if (!(error instanceof ApiError)) return { title: `${action} failed. Try again.` };
  if (error.code === "STALE_PLANNING_SOURCE") return { title: "Sources changed; refresh and freeze again.", detail: "Saved work was refreshed with the current source revision.", code: error.code };
  if (error.code === "SCENARIO_REVISION_MISMATCH") return { title: "This scenario changed since it was frozen. Create a new frozen scenario and compare again.", code: error.code };
  if (error.status === 0) return { title: "Could not reach the planning service. Check the connection and reconnect.", code: "NETWORK_ERROR" };
  if (error.status === 503) return { title: "The planning service is unavailable right now. Workers or the backend may be down.", code: error.code };
  if (error.status === 422 || error.code === "UNSUPPORTED_PLANNING_INPUT") return { title: "The server rejected these planning inputs. Check each step and try again.", code: error.code };
  return { title: `${action} failed.`, code: error.code };
}

const frozenMultiplier = (s: Scenario, key: string) => s.payload.modifiers.find((m) => modifierKey(m.site_id, m.product_id) === key)?.multiplier ?? "1";

export function ScenarioLab() {
  return (
    <MotionConfig reducedMotion="user">
      <AppShell active="scenarios" horizonLabel="7-day projection · 1–3 day window">
        <ScenarioLabScreen />
      </AppShell>
    </MotionConfig>
  );
}

function ScenarioLabScreen() {
  const presenter = usePresenter();
  const pending = useRef(false);
  const view = useRef(0);
  const [loading, setLoading] = useState(true);
  const [loadNotice, setLoadNotice] = useState<Notice | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [busy, setBusy] = useState(false);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [network, setNetwork] = useState<Network | null>(null);
  const [methodology, setMethodology] = useState<Methodology | null>(null);
  const [assumptions, setAssumptions] = useState<Schema["AssumptionsResult"] | null>(null);
  const [draft, setDraftState] = useState<Draft>({ forecastId: "", assumptionsId: "", mode: "", days: 1, multipliers: {}, search: "120" });
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [comparisonScenario, setComparisonScenario] = useState<Scenario | null>(null);
  const [active, setActive] = useState<Active | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [productId, setProductId] = useState("");
  const [reload, setReload] = useState(0);
  const [pollKick, setPollKick] = useState(0);
  const { state: session, expired } = presenter;

  const setDraft = useCallback((update: (d: Draft) => Draft) => setDraftState(update), []);
  const handle = useCallback((error: unknown, action: string) => {
    if (error instanceof ApiError && error.status === 401) { expired(); return; }
    setNotice(describe(error, action));
  }, [expired]);

  const products: ProductInfo[] = useMemo(() => network?.products.map((p) => ({ id: p.id, name: p.name, unit: p.base_unit })) ?? [], [network]);
  const beneficiaries: SiteInfo[] = useMemo(() => network?.sites.filter((s) => s.role === "BENEFICIARY").map((s) => ({ id: s.id, name: s.name })) ?? [], [network]);
  const resultSites: SiteInfo[] = useMemo(() => {
    const frozen = comparisonScenario?.payload.package.sites.filter((s) => s.role === "BENEFICIARY").map((s) => ({ id: s.id, name: s.name }));
    return frozen?.length ? frozen : beneficiaries;
  }, [comparisonScenario, beneficiaries]);

  const setUrl = (params: Record<string, string | null>) => {
    const url = new URL(window.location.href);
    for (const [k, v] of Object.entries(params)) { if (v === null) url.searchParams.delete(k); else url.searchParams.set(k, v); }
    window.history.replaceState(null, "", url);
  };

  const loadAssumptions = useCallback(async (id: string) => {
    const value = await planningApi.assumptions(id);
    setAssumptions(value);
    setDraftState((d) => ({ ...d, assumptionsId: value.id }));
  }, []);

  const loadComparison = useCallback(async (id: string) => {
    const revision = ++view.current;
    const value = await planningApi.comparison(id);
    const frozen = await planningApi.scenario(value.scenario_id).catch(() => null);
    if (revision !== view.current) return;
    setComparison(value); setComparisonScenario(frozen);
  }, []);

  const refreshCatalog = useCallback(async () => {
    const value = await planningApi.planningCatalog();
    setCatalog(value);
    return value;
  }, []);

  // Initial presenter load: catalog, network, methodology; then URL deep links (?comparison=, ?job=).
  useEffect(() => {
    if (session !== "presenter") { if (session === "visitor") queueMicrotask(() => setLoading(false)); return; }
    let alive = true;
    queueMicrotask(() => { if (alive) { setLoading(true); setLoadNotice(null); } });
    Promise.all([planningApi.planningCatalog(), planningApi.forecastCatalog(), planningApi.methodology()]).then(async ([list, net, method]) => {
      if (!alive) return;
      setCatalog(list); setNetwork(net); setMethodology(method);
      const multipliers: Record<string, string> = {};
      for (const site of net.sites.filter((s) => s.role === "BENEFICIARY")) for (const p of net.products) multipliers[modifierKey(site.id, p.id)] = "1";
      setDraftState((d) => ({ ...d, forecastId: d.forecastId || list.forecasts[0]?.id || "", multipliers: Object.keys(d.multipliers).length ? d.multipliers : multipliers,
        search: String(method.search_seconds?.default ?? 120), days: method.planning_window_days?.[0] ?? 1 }));
      setProductId((p) => p || net.products[0]?.id || "");
      if (list.assumptions[0]) await loadAssumptions(list.assumptions[0].id).catch((e) => handle(e, "Loading assumptions"));
      const params = new URL(window.location.href).searchParams;
      const comparisonId = params.get("comparison"), jobId = params.get("job");
      if (isUuid(comparisonId)) await loadComparison(comparisonId).catch((e) => handle(e, "Loading the saved comparison"));
      if (isUuid(jobId)) setActive({ id: jobId, kind: params.get("kind") === "forecast" ? "forecast" : "comparison" });
    }).catch((error) => {
      if (!alive) return;
      if (error instanceof ApiError && error.status === 401) { expired(); return; }
      setLoadNotice({ ...describe(error, "Loading Scenario Lab"), retry: "load" });
    }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [session, reload, loadAssumptions, loadComparison, handle, expired]);

  // Durable job polling (~2.5 s). Stale responses are ignored when the tracked job changes.
  useEffect(() => {
    if (!active || session !== "presenter") return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const status = await planningApi.job(active.id);
        if (stopped) return;
        if (status.state === "SUCCEEDED") {
          if (active.kind === "comparison") {
            try {
              await loadComparison(active.id);
            } catch (error) {
              if (error instanceof ApiError && error.code === "COMPARISON_NOT_PUBLISHED") { timer = setTimeout(poll, 2500); return; }
              throw error;
            }
          } else {
            const result = await planningApi.forecast(active.id);
            if (stopped) return;
            if (!result.planning_ready) setNotice({ title: "The forecast was saved but is not planning ready. Choose another forecast or review its history." });
            else { await refreshCatalog(); setDraftState((d) => ({ ...d, forecastId: result.forecast.run_id })); }
          }
          if (!stopped) setJob(status);
          return;
        }
        setJob(status);
        if (!TERMINAL_JOB_STATES.has(status.state)) timer = setTimeout(poll, 2500);
      } catch (error) {
        if (stopped) return;
        if (error instanceof ApiError && error.status === 401) { expired(); return; }
        setNotice({ ...describe(error, "Checking the job"), retry: "poll" });
      }
    };
    void poll();
    return () => { stopped = true; if (timer) clearTimeout(timer); };
  }, [active, session, pollKick, loadComparison, refreshCatalog, expired]);

  const perform = async (action: () => Promise<void>, label: string) => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true); setNotice(null);
    try { await action(); } catch (error) { handle(error, label); } finally { pending.current = false; setBusy(false); }
  };

  const track = (accepted: Schema["ForecastAccepted"], kind: Active["kind"]) => {
    setJob({ job_id: accepted.job_id, current_attempt_id: accepted.attempt_id, state: accepted.state, attempts: [] });
    setActive({ id: accepted.job_id, kind });
    setUrl({ job: accepted.job_id, kind: kind === "forecast" ? "forecast" : null, comparison: null });
  };

  const modifiers = (): Schema["DemandModifier"][] => beneficiaries.flatMap((site) => products.map((p) => ({
    site_id: site.id, product_id: p.id, mode: "CENTRAL" as const, multiplier: (draft.multipliers[modifierKey(site.id, p.id)] ?? "1").trim(), buffer_fraction: null,
  })));

  const diff = useMemo(() => {
    if (!scenario) return ["New scenario"];
    const out: string[] = [];
    if (scenario.forecast_run_id !== draft.forecastId) out.push(`Forecast ${shortId(scenario.forecast_run_id)} → ${shortId(draft.forecastId)}`);
    if (scenario.assumptions_id !== draft.assumptionsId) out.push(`Assumptions ${shortId(scenario.assumptions_id)} → ${shortId(draft.assumptionsId)}`);
    if (scenario.payload.transfer_mode !== draft.mode) out.push(`Mode ${MODE_LABEL[scenario.payload.transfer_mode]} → ${draft.mode ? MODE_LABEL[draft.mode] : "not chosen"}`);
    if (scenario.payload.planning_days !== draft.days) out.push(`Window ${scenario.payload.planning_days} → ${draft.days} days`);
    for (const [key, value] of Object.entries(draft.multipliers)) {
      const before = frozenMultiplier(scenario, key);
      if (Number(before) !== Number(value.trim()) || value.trim() === "") {
        const [siteId, pid] = key.split("|");
        out.push(`${beneficiaries.find((s) => s.id === siteId)?.name ?? shortId(siteId)} · ${products.find((p) => p.id === pid)?.name ?? shortId(pid)} ×${before} → ×${value}`);
      }
    }
    return out;
  }, [scenario, draft, beneficiaries, products]);
  const dirty = !scenario ? draft.mode !== "" : diff.length > 0;

  const freeze = () => perform(async () => {
    if (!catalog || !draft.mode) return;
    try {
      const value = await planningApi.freezeScenario({ forecast_run_id: draft.forecastId, assumptions_id: draft.assumptionsId,
        expected_source_revision: catalog.source_revision, transfer_mode: draft.mode, planning_days: draft.days,
        parent_id: scenario?.id ?? null, modifiers: modifiers() });
      setScenario(value);
      await refreshCatalog().catch(() => undefined);
    } catch (error) {
      if (error instanceof ApiError && error.code === "STALE_PLANNING_SOURCE") await refreshCatalog().catch(() => undefined);
      throw error;
    }
  }, "Freezing the scenario");

  const compare = () => perform(async () => {
    if (!scenario) return;
    track(await planningApi.compareMethods(scenario.id, { expected_scenario_hash: scenario.payload.operational_hash, search_seconds: Number(draft.search) }), "comparison");
  }, "Starting the comparison");

  const generateForecast = () => perform(async () => {
    const source = network?.sources.find((s) => s.classification === "SIMULATED");
    if (!source) return;
    track(await planningApi.generateForecast(demoForecastRequest(source.id, network?.sites[0]?.timezone ?? "America/New_York")), "forecast");
  }, "Generating the forecast");

  const saveAssumptions = async (text: string): Promise<string | null> => {
    if (!assumptions) return null;
    let payload: Schema["AssumptionsPayload"];
    try { payload = JSON.parse(text) as Schema["AssumptionsPayload"]; } catch { return "This is not valid JSON. Fix it and save again."; }
    let message: string | null = null;
    await perform(async () => {
      try {
        const value = await planningApi.saveAssumptions({ name: "Revised simulated assumptions", parent_id: assumptions.id, payload });
        setAssumptions(value); setDraftState((d) => ({ ...d, assumptionsId: value.id }));
        await refreshCatalog();
      } catch (error) { if (error instanceof ApiError && error.status === 422) message = "The server rejected this assumptions payload (422)."; throw error; }
    }, "Saving assumptions");
    return message;
  };

  const selectScenario = (id: string) => perform(async () => {
    const value = await planningApi.scenario(id);
    setScenario(value);
    const multipliers = { ...draft.multipliers };
    for (const m of value.payload.modifiers) multipliers[modifierKey(m.site_id, m.product_id)] = m.multiplier;
    setDraftState((d) => ({ ...d, forecastId: value.forecast_run_id, mode: value.payload.transfer_mode, days: value.payload.planning_days, multipliers }));
    if (value.assumptions_id !== assumptions?.id) await loadAssumptions(value.assumptions_id);
  }, "Loading the saved scenario");

  const selectComparison = (id: string) => perform(async () => { await loadComparison(id); setUrl({ comparison: id, job: null, kind: null }); }, "Loading the saved comparison");

  const loadOlder = () => perform(async () => {
    if (!catalog?.next_before || !catalog.next_before_id) return;
    const older = await planningApi.planningCatalog({ at: catalog.next_before, id: catalog.next_before_id });
    const merge = (a: Schema["SavedItem"][], b: Schema["SavedItem"][]) => [...a, ...b.filter((x) => !a.some((y) => y.id === x.id))];
    setCatalog({ ...older, source_revision: catalog.source_revision, assumptions: merge(catalog.assumptions, older.assumptions), forecasts: merge(catalog.forecasts, older.forecasts),
      scenarios: merge(catalog.scenarios, older.scenarios), comparisons: merge(catalog.comparisons, older.comparisons) });
  }, "Loading older saved work");

  const cancel = () => perform(async () => { if (active) { await planningApi.cancelJob(active.id); setPollKick((k) => k + 1); } }, "Cancelling");
  const retry = () => perform(async () => { if (active) track(await planningApi.retryJob(active.id), active.kind); }, "Retrying");

  const running = !!active && (!job || !TERMINAL_JOB_STATES.has(job.state));
  const readOnly = session !== "presenter" || !!loadNotice;
  const rows = useMemo(() => comparison ? joinGoals(resultSites, products, comparison.result.baseline_metrics ?? null,
    usableMetrics(methodOutcome(comparison, "CLASSICAL_GP")), usableMetrics(methodOutcome(comparison, "EGP_PI_INSPIRED"))) : [], [comparison, resultSites, products]);
  const anyVerified = !!comparison && rows.length > 0;
  const showPrevious = !!comparison && !!active && active.kind === "comparison" && comparison.id !== active.id;

  return (
    <div className="flex flex-1 flex-col gap-4 px-4 pt-3 pb-6 md:px-6 md:py-5">
      <HatchDefs />
      {/* R1 header */}
      <header className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <p className="font-condensed text-xs font-semibold tracking-[0.16em] text-muted-foreground uppercase">Fairness-aware planning</p>
          <h1 className="text-[26px] leading-tight font-semibold tracking-tight md:text-[28px]">Scenario Lab</h1>
          <p className="text-sm text-muted-foreground">Compare allocation methods on the same frozen network conditions.</p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div className="grid gap-1">
            <span id="sl-saved-comparison" className="text-xs text-muted-foreground">Saved comparison</span>
            <Select value={comparison?.id ?? ""} onValueChange={selectComparison} disabled={readOnly || busy || !catalog?.comparisons.length}>
              <SelectTrigger aria-labelledby="sl-saved-comparison" className="h-9 w-60"><SelectValue placeholder={readOnly ? "Presenter only" : "None saved yet"} /></SelectTrigger>
              <SelectContent>{catalog?.comparisons.map((c) => <SelectItem key={c.id} value={c.id}>{c.label} · {when(c.recorded_at)} · {shortId(c.id)}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="grid gap-1">
            <span id="sl-saved-scenario" className="text-xs text-muted-foreground">Saved scenario</span>
            <Select value={scenario?.id ?? ""} onValueChange={selectScenario} disabled={readOnly || busy || !catalog?.scenarios.length}>
              <SelectTrigger aria-labelledby="sl-saved-scenario" className="h-9 w-52"><SelectValue placeholder={readOnly ? "Presenter only" : "None saved yet"} /></SelectTrigger>
              <SelectContent>{catalog?.scenarios.map((s) => <SelectItem key={s.id} value={s.id}>{when(s.recorded_at)} · {shortId(s.id)}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          {catalog?.next_before && <Button variant="outline" size="sm" disabled={busy} onClick={() => void loadOlder()}>Load older saved work</Button>}
        </div>
      </header>

      {/* R2 context strip + job status */}
      <div className="flex flex-col gap-2 rounded-lg border border-border bg-card px-3 py-2 text-xs">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <ProvenancePill tone="fixture">SIMULATED data</ProvenancePill>
          {scenario ? (
            <span>
              <strong>Frozen scenario {shortId(scenario.id)}</strong> · {MODE_LABEL[scenario.payload.transfer_mode]} · {scenario.payload.planning_days}-day window from {scenario.payload.package.first_planning_date}
              {" "}· operational <code>{shortId(scenario.payload.operational_hash)}</code> · policy <code>{shortId(scenario.payload.policy_hash)}</code>
              {scenario.stale && <strong> · STALE sources</strong>}{scenario.historical && <strong> · HISTORICAL</strong>}
            </span>
          ) : <span className="text-muted-foreground">No frozen scenario yet — inputs below are a draft.</span>}
        </div>
        {active && (
          <div role="status" data-job-state={job?.state ?? "CONNECTING"} className="flex flex-wrap items-center gap-2 border-t border-border pt-2">
            <span><strong>{active.kind === "forecast" ? "Forecast job" : "Method comparison job"} {shortId(active.id)}:</strong> {job ? STATE_LABEL[job.state] : "Connecting"}</span>
            {job?.attempts.at(-1)?.reason_code && <code>{job.attempts.at(-1)?.reason_code}</code>}
            {running && <span className="text-muted-foreground">Durable job: refreshing the page resumes it. No progress percentage is reported.</span>}
            {running && <Button size="xs" variant="outline" disabled={busy || readOnly || job?.state === "STOPPING"} onClick={() => void cancel()}>Cancel computation</Button>}
            {job && TERMINAL_JOB_STATES.has(job.state) && job.state !== "SUCCEEDED" && <Button size="xs" variant="outline" disabled={busy || readOnly} onClick={() => void retry()}>Retry</Button>}
          </div>
        )}
      </div>

      {session === "visitor" && (
        <Alert>
          <AlertTitle>Read-only view</AlertTitle>
          <AlertDescription>Scenario Lab freezes scenarios and runs method comparisons, which are presenter-only. Sign in as presenter from the sidebar to load saved scenarios and comparisons. No sample results are shown here.</AlertDescription>
        </Alert>
      )}
      {loadNotice && (
        <Alert variant="destructive" role="alert">
          <AlertTitle>{loadNotice.title}</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-2">{loadNotice.code && <code>{loadNotice.code}</code>}
            <Button size="sm" variant="outline" onClick={() => setReload((n) => n + 1)}>Retry</Button></AlertDescription>
        </Alert>
      )}
      {notice && (
        <Alert variant="destructive" role="alert">
          <AlertTitle>{notice.title}</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-2">{notice.detail}{notice.code && <code>{notice.code}</code>}
            {notice.retry === "poll" && <Button size="sm" variant="outline" onClick={() => { setNotice(null); setPollKick((k) => k + 1); }}>Reconnect</Button>}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-4 md:grid-cols-[minmax(0,19rem)_minmax(0,1fr)] min-[1400px]:grid-cols-[minmax(0,18.5rem)_minmax(0,1fr)_minmax(0,19rem)]">
        {/* R3 wizard + R9 constraints */}
        <div className="min-w-0">
          {loading && session !== "visitor" ? <Skeleton className="h-96 w-full" /> : (
            <GuidedScenarioStepper readOnly={readOnly} busy={busy} jobRunning={running} draft={draft} setDraft={setDraft} catalog={catalog}
              beneficiaries={beneficiaries} products={products} assumptions={assumptions} scenario={scenario} dirty={dirty} diff={diff}
              windows={methodology?.planning_window_days ?? [1, 2, 3]} maxSearch={methodology?.search_seconds?.maximum ?? 300}
              canGenerate={!!network?.sources.some((s) => s.classification === "SIMULATED")}
              onSelectAssumptions={(id) => void perform(() => loadAssumptions(id), "Loading assumptions")}
              onGenerateForecast={() => void generateForecast()} onSaveAssumptions={saveAssumptions}
              onFreeze={() => void freeze()} onCompare={() => void compare()}
              constraints={<EnforcedConstraints comparison={comparison} />} />
          )}
        </div>

        {/* R4 + R5 center */}
        <div className="flex min-w-0 flex-col gap-4">
          <section aria-labelledby="results-heading" className="rounded-lg border border-border bg-card p-3 md:p-4">
            <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="results-heading" className="text-base font-semibold">Scenario results <span className="font-normal text-muted-foreground">(simulated)</span></h2>
              {comparison && <span className="rounded-md bg-muted px-2 py-0.5 text-xs">Same frozen scenario {shortId(comparison.scenario_id)} · {MODE_LABEL[comparison.result.transfer_mode]}</span>}
            </div>
            {showPrevious && <p className="mb-2 text-xs text-muted-foreground">Showing the previous verified result saved {when(comparison!.recorded_at)} while job {shortId(active!.id)} is {job ? STATE_LABEL[job.state].toLowerCase() : "connecting"}.</p>}
            {comparison ? (
              <div className="grid gap-3">
                <MethodPairHeader comparison={comparison} />
                {comparison.result.outcome === "FAILED" && <p className="text-sm">Neither method produced a verified allocation. Each method’s outcome is listed above; nothing is substituted.</p>}
                {anyVerified && <ScenarioResultsSummary comparison={comparison} products={products} />}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                {session === "visitor" ? "Saved results are visible to a signed-in presenter." : running ? "No verified comparison yet. A queued or running job is not a result." : "No verified comparison yet. Freeze a scenario and compare methods, or open a saved comparison."}
              </p>
            )}
          </section>
          {comparison && anyVerified && (
            <ProjectedFillRateBySite comparison={comparison} rows={rows} sites={resultSites} products={products} productId={productId} onProduct={setProductId} />
          )}
        </div>

        {/* R6 + R7 rail (stacks under results below 2xl) */}
        {comparison && (
          <div className="flex min-w-0 flex-col gap-4 md:max-[1399px]:col-span-2">
            {anyVerified && <ComparisonRail comparison={comparison} products={products} productId={productId} />}
            <KeyTradeoffs comparison={comparison} rows={rows} sites={resultSites} products={products} methodology={methodology} />
          </div>
        )}
      </div>

      {/* R8 detail evidence */}
      {comparison && (
        <section aria-labelledby="evidence-heading" className="grid gap-4 rounded-lg border border-border bg-card p-3 md:p-4">
          <h2 id="evidence-heading" className="text-base font-semibold">Method evidence</h2>
          {anyVerified && <MethodGoalTable comparison={comparison} scenario={comparisonScenario} rows={rows} sites={resultSites} products={products} />}
          <div className="grid gap-2"><h3 className="text-sm font-semibold">Transfer changes</h3>
            <TransferDiffTable comparison={comparison} scenario={comparisonScenario} rows={rows} sites={comparisonScenario?.payload.package.sites ?? resultSites} products={products} /></div>
          <div className="grid gap-2"><h3 className="text-sm font-semibold">Common differences</h3>
            <CommonDifferences comparison={comparison} scenario={comparisonScenario} rows={rows} sites={resultSites} products={products} /></div>
          <SolverStatusTable comparison={comparison} scenario={comparisonScenario} rows={rows} sites={resultSites} products={products} />
          <details className="text-sm"><summary className="cursor-pointer font-semibold">Provenance and frozen identities</summary>
            <div className="mt-2"><Provenance comparison={comparison} scenario={comparisonScenario} rows={rows} sites={resultSites} products={products} /></div></details>
        </section>
      )}
    </div>
  );
}
