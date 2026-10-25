"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError, localDay, type Schema } from "@/lib/planning-api";
import styles from "./workspace.module.css";

type Catalog = Schema["PlanningCatalog"];
type Network = Schema["ForecastCatalog"];
type Assumptions = Schema["AssumptionsResult"];
type Scenario = Schema["ScenarioResult"];
type Comparison = Schema["SavedComparison"];
type Job = Schema["ForecastJob"];
type Active = { id: string; kind: "forecasts" | "comparisons" };
const terminal = new Set(["SUCCEEDED", "FAILED", "TIMED_OUT", "INTERRUPTED", "CANCELLED", "EXPIRED"]);
const rational = (x: { numerator: number; denominator: number } | null | undefined) => x ? (x.numerator / x.denominator).toLocaleString(undefined, { maximumFractionDigits: 5 }) : "Unavailable";

export default function Workspace() {
  const [signedIn, setSignedIn] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [network, setNetwork] = useState<Network | null>(null);
  const [assumptions, setAssumptions] = useState<Assumptions | null>(null);
  const [policyText, setPolicyText] = useState("");
  const [forecastId, setForecastId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [mode, setMode] = useState<"" | "HUB_ONLY" | "HUB_AND_PANTRY">("");
  const [days, setDays] = useState(3);
  const [budget, setBudget] = useState(120);
  const [multiplier, setMultiplier] = useState("1");
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [active, setActive] = useState<Active | null>(null);
  const [job, setJob] = useState<Job | null>(null);

  const showError = useCallback((value: unknown) => {
    if (value instanceof ApiError && value.status === 401) setSignedIn(false);
    setError(value instanceof Error ? value.message : "Request failed. Reconnect and try again.");
  }, []);
  const refresh = useCallback(async () => {
    const [list, net] = await Promise.all([api<Catalog>("planning-catalog"), api<Network>("forecast-catalog")]);
    setCatalog(list); setNetwork(net); setSignedIn(true);
    return { list, net };
  }, []);
  async function selectAssumptions(id: string) {
    const value = await api<Assumptions>(`planning-assumptions/${id}`);
    setAssumptions(value); setPolicyText(JSON.stringify(value.payload, null, 2));
  }
  const perform = async (action: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await action(); } catch (e) { showError(e); } finally { setBusy(false); }
  };
  const track = (accepted: Schema["ForecastAccepted"], kind: Active["kind"]) => {
    setActive({ id: accepted.job_id, kind }); setJob(null);
    const url = new URL(window.location.href);
    url.searchParams.set("job", accepted.job_id); url.searchParams.set("kind", kind);
    window.history.replaceState(null, "", url);
  };
  useEffect(() => {
    let mounted = true;
    Promise.all([api<Catalog>("planning-catalog"), api<Network>("forecast-catalog")]).then(([list, net]) => {
      if (!mounted) return;
      setCatalog(list); setNetwork(net); setSignedIn(true);
      setSourceId(net.sources.find((s) => s.classification === "SIMULATED")?.id ?? "");
      setForecastId(list.forecasts[0]?.id ?? "");
      if (list.assumptions[0]) void selectAssumptions(list.assumptions[0].id).catch(showError);
      const params = new URL(window.location.href).searchParams;
      const id = params.get("job"), kind = params.get("kind");
      if (id && /^(?:[0-9a-f]{8}-)(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(id) && (kind === "forecasts" || kind === "comparisons")) setActive({ id, kind });
    }).catch((e) => { if (!(e instanceof ApiError && e.status === 401)) showError(e); })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, [refresh, showError]);
  useEffect(() => {
    if (!active || !signedIn) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const status = await api<Job>(`jobs/${active!.id}`);
        if (stopped) return;
        setJob(status);
        if (status.state === "SUCCEEDED") {
          if (active!.kind === "comparisons") {
            const result = await api<Comparison>(`comparisons/${active!.id}`);
            const saved = await api<Scenario>(`scenarios/${result.scenario_id}`);
            if (!stopped) { setComparison(result); setScenario(saved); }
          } else {
            const result = await api<Schema["ForecastResult"]>(`forecasts/${active!.id}`);
            if (!result.planning_ready) throw new Error("Forecast saved but not planning ready. Review history or choose another source.");
            if (!stopped) setForecastId(active!.id);
          }
          await refresh();
          return;
        }
        if (terminal.has(status.state)) return;
      } catch (e) { if (!stopped) showError(e); }
      if (!stopped) timer = setTimeout(poll, 2500);
    }
    void poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, [active, signedIn, refresh, showError]);

  async function login(form: FormData) {
    await api("presenter/login", { username: form.get("username"), password: form.get("password") });
    const { list, net } = await refresh();
    setSourceId(net.sources.find((s) => s.classification === "SIMULATED")?.id ?? "");
    setForecastId(list.forecasts[0]?.id ?? "");
    if (list.assumptions[0]) await selectAssumptions(list.assumptions[0].id);
  }
  async function generateForecast() {
    const zone = network?.sites[0]?.timezone ?? "America/New_York";
    const request: Schema["ForecastRequest"] = { source_id: sourceId,
      data_cutoff_date: localDay(zone, -1), history_start_date: localDay(zone, -90),
      snapshot_as_of: new Date().toISOString(), force_refresh: false,
      policy: { strategy: "SEASONAL_NAIVE", policy_version: "demo-proposal-14d-3samples-v1",
        adapter_version: "core-v1", preprocessing_version: "preserve-gaps-v1", postprocessing_version: "reject-invalid-v1",
        sparse_window_days: 14, sparse_min_samples: 3, allow_fallback: true,
        allow_fulfilled_proxy: false, allow_mixed_proxy_history: false } };
    track(await api<Schema["ForecastAccepted"]>("forecasts", request), "forecasts");
  }
  async function freeze() {
    if (!assumptions || !catalog || !mode) return;
    const request: Schema["ScenarioRequest"] = { forecast_run_id: forecastId, assumptions_id: assumptions.id,
      expected_source_revision: catalog.source_revision, transfer_mode: mode, planning_days: days,
      parent_id: scenario?.id ?? null, modifiers: assumptions.payload.reserves.map((r) => ({
        site_id: r.site_id, product_id: r.product_id, mode: "CENTRAL", multiplier, buffer_fraction: null })) };
    setScenario(await api<Scenario>("scenarios", request)); setComparison(null); await refresh();
  }
  async function loadComparison(id: string) {
    const value = await api<Comparison>(`comparisons/${id}`);
    setComparison(value); setScenario(await api<Scenario>(`scenarios/${value.scenario_id}`));
  }
  const running = active && (!job || !terminal.has(job.state));
  const siteName = (id: string) => scenario?.payload.package.sites.find((s) => s.id === id)?.name ?? id;
  const productName = (id: string) => network?.products.find((p) => p.id === id)?.name ?? id;

  return <main className={styles.workspace}>
    <header className={styles.header}><div><Link href="/">PantryPulse</Link><h1>Optimization workspace</h1></div>
      <span className={styles.pill}>Simulated network</span>
      {signedIn && <button onClick={() => void perform(async () => { await api("presenter/logout", {}); setSignedIn(false); setActive(null); setScenario(null); setComparison(null); window.history.replaceState(null, "", "/optimization"); })}>Sign out</button>}
    </header>
    <p className={styles.intro}>Compare classical goal programming with the EGP-PI-inspired method on the same frozen inputs. This is a simulation; no stock is reserved or dispatched.</p>
    {error && <div role="alert" className={styles.error}>{error}. <button onClick={() => void perform(async () => { await refresh(); setActive((v) => v ? { ...v } : null); })}>Reconnect</button></div>}
    {loading ? <p role="status">Checking presenter session…</p> : !signedIn ? <section className={styles.card}>
      <h2>Presenter sign in</h2><form onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); void perform(() => login(form)); }}>
        <label>Username<input name="username" autoComplete="username" required /></label>
        <label>Password<input name="password" type="password" autoComplete="current-password" required /></label>
        <button disabled={busy} type="submit">Sign in</button>
      </form><p>Use the presenter credentials configured for your isolated demo.</p>
    </section> : <>
      <div className={styles.grid}>
        <section className={styles.card}><h2>1 · Select a forecast</h2>
          <label>Saved planning-ready forecast<select value={forecastId} onChange={(e) => setForecastId(e.target.value)}><option value="">Choose a forecast</option>{catalog?.forecasts.map((r) => <option key={r.id} value={r.id}>{new Date(r.recorded_at).toLocaleString()} · {r.id.slice(0, 8)}</option>)}</select></label>
          <label>Fictional history source<select value={sourceId} onChange={(e) => setSourceId(e.target.value)}><option value="">Choose a source</option>{network?.sources.filter((s) => s.classification === "SIMULATED").map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
          <button disabled={busy || !!running || !sourceId} onClick={() => void perform(generateForecast)}>Generate forecast</button>
          <p>Seven days from yesterday’s cutoff, using seasonal naive with an explicitly enabled moving-average fallback. Donation predictions never become stock.</p>
        </section>
        <section className={styles.card}><h2>2 · Freeze a scenario</h2>
          <label>Transfer mode (required)<select value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}><option value="">Choose transfer mode</option><option value="HUB_ONLY">Hub to pantry only</option><option value="HUB_AND_PANTRY">Hub and pantry transfers</option></select></label>
          <div className={styles.row}><label>Allocation window<select value={days} onChange={(e) => setDays(Number(e.target.value))}>{[1, 2, 3].map((d) => <option key={d} value={d}>{d} day{d > 1 ? "s" : ""}</option>)}</select></label>
            <label>Demand multiplier<input type="number" min="0" max="3" step="0.01" value={multiplier} onChange={(e) => setMultiplier(e.target.value)} /></label></div>
          <label>Assumptions version<select value={assumptions?.id ?? ""} onChange={(e) => void perform(() => selectAssumptions(e.target.value))}><option value="" disabled>Choose assumptions</option>{catalog?.assumptions.map((r) => <option key={r.id} value={r.id}>{r.label} · {r.id.slice(0, 8)}</option>)}</select></label>
          <button disabled={busy || !forecastId || !mode || !assumptions} onClick={() => void perform(freeze)}>{scenario ? "Save revised scenario" : "Freeze scenario"}</button>
          <p>Dispatch on day one. Policy and scenario edits create new immutable versions.</p>
        </section>
        <section className={styles.card}><h2>3 · Compare methods</h2>
          <label>Native search per method (seconds)<input type="number" min="1" max="300" step="1" value={budget} onChange={(e) => setBudget(Number(e.target.value))} /></label>
          <p>One solver worker per method. Each method has {budget + 30}s total; the comparison has {2 * (budget + 30) + 30}s. Both receive identical settings.</p>
          <button disabled={busy || !!running || !scenario || !Number.isInteger(budget) || budget < 1 || budget > 300} onClick={() => void perform(async () => {
            if (scenario) track(await api<Schema["ForecastAccepted"]>("comparisons", { scenario_id: scenario.id, search_seconds: budget }), "comparisons");
          })}>Compare frozen scenario</button>
          {scenario ? <p>Scenario <code>{scenario.id.slice(0, 8)}</code> · {scenario.payload.transfer_mode} · {scenario.payload.planning_days} days · {scenario.payload.package.first_planning_date}{scenario.stale && " · STALE SOURCES"}{scenario.historical && " · HISTORICAL"}</p> : <p>Save a scenario to enable comparison.</p>}
          {scenario && <p>Changing the budget recomputes this saved scenario. To use current stock or new assumptions, save a revised scenario first.</p>}
        </section>
      </div>
      {active && <section className={styles.card} aria-label="Computation progress"><h2>Computation</h2>
        <p role="status">{job?.state ?? "Connecting"} · {active.kind === "forecasts" ? "Forecast" : "Sequential method comparison"} · {active.id.slice(0, 8)}</p>
        <p>You can refresh or reconnect without losing this durable job. Queue expiry is 30 minutes. Native search does not report a reliable percentage.</p>
        {job?.attempts.at(-1)?.reason_code && <p>{job.attempts.at(-1)?.reason_code}</p>}
        {running && <button disabled={busy || job?.state === "STOPPING"} onClick={() => void perform(async () => { await api(`jobs/${active.id}/cancel`, {}); setActive({ ...active }); })}>Cancel computation</button>}
        {job && terminal.has(job.state) && job.state !== "SUCCEEDED" && <button disabled={busy} onClick={() => void perform(async () => { track(await api<Schema["ForecastAccepted"]>(`jobs/${active.id}/retry`, {}), active.kind); })}>Retry frozen attempt</button>}
      </section>}
      <details className={styles.card}><summary>Edit simulated policy and assumptions</summary>
        <p>Research defaults are a simulated preset, not a validated real-world policy. Routes, handling/storage/receiving capacities, reserves and vulnerability scores are explicit assumptions.</p>
        {assumptions && <><label>Assumptions JSON<textarea rows={14} spellCheck={false} value={policyText} onChange={(e) => setPolicyText(e.target.value)} /></label>
          <button disabled={busy || policyText === JSON.stringify(assumptions.payload, null, 2)} onClick={() => void perform(async () => {
            const value = await api<Assumptions>("planning-assumptions", { name: "Revised simulated assumptions", parent_id: assumptions.id, payload: JSON.parse(policyText) });
            setAssumptions(value); setPolicyText(JSON.stringify(value.payload, null, 2)); await refresh();
          })}>Save new assumptions version</button></>}
      </details>
      <section className={styles.card}><h2>Saved work</h2><div className={styles.row}>
        <label>Read a saved scenario<select value={scenario?.id ?? ""} onChange={(e) => void perform(async () => { const saved = await api<Scenario>(`scenarios/${e.target.value}`); setScenario(saved); setComparison(null); setForecastId(saved.forecast_run_id); setMode(saved.payload.transfer_mode); setDays(saved.payload.planning_days); await selectAssumptions(saved.assumptions_id); })}><option value="" disabled>Choose scenario</option>{catalog?.scenarios.map((r) => <option key={r.id} value={r.id}>{new Date(r.recorded_at).toLocaleString()} · {r.id.slice(0, 8)}</option>)}</select></label>
        <label>Read a saved comparison<select value={comparison?.id ?? ""} onChange={(e) => void perform(() => loadComparison(e.target.value))}><option value="" disabled>Choose comparison</option>{catalog?.comparisons.map((r) => <option key={r.id} value={r.id}>{r.label} · {new Date(r.recorded_at).toLocaleString()} · {r.id.slice(0, 8)}</option>)}</select></label></div>
        <button disabled={busy} onClick={() => void perform(async () => { await refresh(); })}>Refresh saved work</button>
        {catalog?.next_before && <button disabled={busy} onClick={() => void perform(async () => { setCatalog(await api<Catalog>(`planning-catalog?before=${encodeURIComponent(catalog.next_before!)}&before_id=${catalog.next_before_id}`)); })}>Load older saved work</button>}
      </section>
      {comparison && scenario && <section className={styles.card}><h2>Comparison results · {comparison.result.outcome}</h2>
        <p>{comparison.stale ? "STALE: source records changed since this scenario was frozen. " : "Sources match this saved snapshot. "}{comparison.historical && "HISTORICAL: this scenario’s planning date is no longer today. "}Saved results never change when sources change.</p>
        <p>{scenario.payload.package.first_planning_date} · {scenario.payload.planning_days}-day allocation window · 7-day inventory projection · {comparison.settings.search_milliseconds as number / 1000}s search per method.</p>
        <div className={styles.methods}>{comparison.result.methods.map((method) => <article className={styles.method} key={method.method}>
          <h3>{method.method === "CLASSICAL_GP" ? "Classical goal programming" : "EGP-PI-inspired"}</h3>
          <p className={styles.pill}>{method.native_status ?? method.outcome} · {method.outcome}</p>
          <dl><dt>Native objective</dt><dd>{rational(method.objective)}</dd><dt>Best bound</dt><dd>{method.native_bound?.toLocaleString(undefined, { maximumFractionDigits: 5 }) ?? "Unavailable"}</dd><dt>Reported gap</dt><dd>{method.gap == null ? "Unavailable" : `${(method.gap * 100).toFixed(3)}%`}</dd><dt>Search / total method time</dt><dd>{method.search_seconds?.toFixed(2)}s / {method.total_seconds?.toFixed(2)}s</dd></dl>
          {method.error_code && <p role="note">{method.error_code}. The other method’s verified result remains available.</p>}
          {method.verification?.metrics && <><h4>Unmet demand before / after</h4><table><caption>Allocation window, by product</caption><thead><tr><th>Product / unit</th><th>Before</th><th>After</th></tr></thead><tbody>{scenario.payload.package.products.map((p) => <tr key={p.id}><th>{productName(p.id)} · {p.unit}</th><td>{comparison.result.baseline_metrics?.goals.filter((g) => g.product_id === p.id).reduce((n, g) => n + g.unmet, 0)}</td><td>{method.verification?.metrics?.goals.filter((g) => g.product_id === p.id).reduce((n, g) => n + g.unmet, 0)}</td></tr>)}</tbody></table>
            <p>Independent replay: passed. Cost: {method.verification.metrics.cost_minor} simulated cost points.</p>
            <h4>Proposed transfers</h4>{!method.candidate?.assignments.length && <p>No transfers selected.</p>}
            <ul>{method.candidate?.assignments.map((a, i) => <li key={`${a.route_id}-${a.original_lot_id}-${i}`}><strong>{siteName(a.source_id)} → {siteName(a.destination_id)}</strong><br />{a.units} {a.unit} · arrives {a.arrival}<br />Expiry: {a.expires_on ?? "Explicitly non-expiring"}. FEFO, donor protection and capacity constraints passed independent verification.</li>)}</ul>
            <details><summary>Per-site service and seven-day waste</summary><ul>{method.verification.metrics.goals.map((g) => <li key={`${g.site_id}-${g.product_id}`}>{siteName(g.site_id)} · {productName(g.product_id)}: {g.fulfilled} served / {g.target} target; {g.unmet} unmet</li>)}</ul><ul>{method.verification.metrics.waste_by_product.map(([id, amount]) => <li key={id}>{productName(id)}: {amount} expired units over 7 days</li>)}</ul></details>
          </>}
        </article>)}</div>
        <p>Native objectives differ. Compare common metrics and trade-offs; a feasible solution is not a proof of optimality.</p>
        <details><summary>Provenance and frozen identities</summary><p>Forecast: {scenario.forecast_run_id}<br />Assumptions: {scenario.assumptions_id}<br />Operational hash: {scenario.payload.operational_hash}<br />Policy hash: {scenario.payload.policy_hash}</p><p>Forecast providers: {[...new Set(scenario.payload.package.forecasts.map((f) => f.actual_provider))].join(", ")}. Numeric conversion: {[...new Set(scenario.payload.package.forecasts.map((f) => f.numeric_conversion))].join(", ")}.</p><pre>{JSON.stringify(comparison.settings, null, 2)}</pre><ul>{scenario.payload.package.provenance_warnings.map((w) => <li key={w}>{w}</li>)}</ul></details>
      </section>}
    </>}
  </main>;
}
