"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { FormEvent } from "react";
import { ArrowRight, CheckCircle2, Clock3, FlaskConical, LockKeyhole, RefreshCw } from "lucide-react";
import type { components } from "../../../../../packages/contracts/schema";

type Wire = components["schemas"];
type Scenario = Wire["ScenarioSummary"];
type Job = Wire["JobSummary"];
type Comparison = Wire["ComparisonSummary"];
type Plan = Wire["PlanSummary"];
type Seed = Wire["SeedResponse"];
type Mode = Wire["TransferMode"];
type Method = Wire["MethodOutcome"];
type Package = Wire["ORInputPackage"];
type Metrics = Wire["Metrics"];

const terminal = new Set(["SUCCEEDED", "PARTIAL", "FAILED", "TIMED_OUT", "CANCELLED", "INTERRUPTED", "EXPIRED", "LOST", "CANCELED"]);

function csrfCookie() {
  const match = document.cookie.split("; ").find((value) => value.startsWith("pp_csrf="));
  return match ? decodeURIComponent(match.slice("pp_csrf=".length)) : "";
}

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    method: body === undefined ? "GET" : "POST",
    credentials: "same-origin",
    cache: "no-store",
    headers: body === undefined ? {} : {
      "Content-Type": "application/json", "X-CSRF-Token": csrfCookie(),
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(`${data.error?.code ?? response.status}: ${data.error?.message ?? "Request could not be completed"}`);
  return data as T;
}

function ratio(value: Wire["Rational"] | null | undefined) {
  return value ? (value.numerator / value.denominator).toLocaleString(undefined, { maximumFractionDigits: 4 }) : "—";
}

export default function OptimizationDesk({ initialJobId }: { initialJobId: string | null }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [presenter, setPresenter] = useState(false);
  const [mode, setMode] = useState<Mode | "">("");
  const [windowDays, setWindowDays] = useState(3);
  const [multiplier, setMultiplier] = useState("1");
  const [seed, setSeed] = useState<Seed | null>(null);
  const [network, setNetwork] = useState<Package | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [jobId, setJobId] = useState<string | null>(initialJobId);
  const [loadGeneration, setLoadGeneration] = useState(0);
  const [job, setJob] = useState<Job | null>(null);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [history, setHistory] = useState<{ id: string; label: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [savedId, setSavedId] = useState(initialJobId ?? "");

  const siteName = (id: string) => network?.sites.find((site) => site.id === id)?.name ?? scenario?.sites.find((site) => site.id === id)?.name ?? `Site ${id.slice(-4)}`;
  const unitName = (id: string) => network?.products.find((product) => product.id === id)?.unit ?? scenario?.products.find((product) => product.id === id)?.unit ?? `Product ${id.slice(-4)}`;

  useEffect(() => {
    let live = true;
    api<{ authenticated?: boolean }>("/presenter/session").then((data) => {
      if (live) setPresenter(Boolean(data.authenticated));
    }).catch(() => {});
    return () => { live = false; };
  }, []);

  useEffect(() => {
    if (!jobId) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const current = await api<Job>(`/jobs/${jobId}`);
        if (stopped) return;
        setJob(current);
        const savedPlans = await Promise.all(current.plans.map((plan) => api<Plan>(`/plans/${plan.plan_id}`)));
        if (stopped) return;
        setPlans(savedPlans);
        if (current.comparison_id) {
          const savedComparison = await api<Comparison>(`/comparisons/${current.comparison_id}`);
          if (stopped) return;
          setComparison(savedComparison);
          const savedScenario = await api<Scenario>(`/scenarios/${savedComparison.scenario_id}`);
          if (stopped) return;
          setScenario(savedScenario);
          api<Wire["PackageSummary"]>(`/or/input-packages/${savedScenario.input_package_id}`).then((item) => {
            if (!stopped && item.payload) setNetwork(item.payload as unknown as Package);
          }).catch(() => {});
        }
        if (!terminal.has(current.state)) timer = setTimeout(poll, 1000);
      } catch (failure) {
        if (!stopped) setError(failure instanceof Error ? failure.message : "Saved job unavailable");
      }
    }
    void poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, [jobId, loadGeneration]);

  async function action(work: () => Promise<void>) {
    setBusy(true); setError(""); setNotice("");
    try { await work(); } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Request could not be completed");
    } finally { setBusy(false); }
  }

  async function login(event: FormEvent) {
    event.preventDefault();
    await action(async () => {
      await api<Wire["LoginResponse"]>("/presenter/login", { username, password });
      setPassword(""); setPresenter(true); setNotice("Presenter session started.");
    });
  }

  async function loadNetwork() {
    await action(async () => {
      const selected = await api<Seed>("/demo/seed", { fixture: "six-beneficiary-v1" });
      const saved = await api<Wire["PackageSummary"]>(`/or/input-packages/${selected.input_package_id}`);
      setSeed(selected);
      if (saved.payload) setNetwork(saved.payload as unknown as Package);
      setNotice("Six fictional pantries, one hub, two products and seven forecast dates are saved. Choose a transfer mode to freeze a scenario.");
    });
  }

  async function freezeScenario() {
    if (!seed || !mode) return;
    await action(async () => {
      const request: Wire["ScenarioCreate"] = {
        input_package_id: seed.input_package_id, policy_id: seed.policy_id,
        transfer_mode: mode, planning_days: windowDays, intent: "CURRENT",
        expected_source_revision: seed.source_revision_token,
        modifiers: seed.modifiers.map((modifier) => ({ ...modifier, multiplier })),
      };
      const saved = await api<Scenario>("/scenarios", request);
      if (jobId) setHistory((items) => [...items.filter((item) => item.id !== jobId), {
        id: jobId, label: `${scenario?.transfer_mode ?? "Saved"} · ${scenario?.operational_hash.slice(0, 8)}`,
      }]);
      setScenario(saved); setComparison(null); setPlans([]); setJob(null); setJobId(null);
      setNotice("A new immutable scenario is saved. Existing comparisons keep their original inputs.");
    });
  }

  async function submitPair() {
    if (!scenario) return;
    await action(async () => {
      const accepted = await api<Wire["JobAccepted"]>(`/scenarios/${scenario.id}/compare-methods`, {
        expected_scenario_hash: scenario.operational_hash, intent: scenario.intent,
      });
      setComparison(null); setPlans([]); setJob(null); setJobId(accepted.job_id); setSavedId(accepted.job_id);
      window.history.replaceState(null, "", `/optimization?job=${accepted.job_id}`);
      setNotice("Comparison accepted. Both methods use this scenario and run sequentially.");
    });
  }

  async function review(plan: Plan, reviewAction: "REVIEWED" | "REJECTED") {
    await action(async () => {
      const event = await api<Wire["ReviewResponse"]>(`/plans/${plan.id}/review`, {
        action: reviewAction, expected_result_hash: plan.result_hash, note: null,
      });
      setNotice(`${event.action} recorded at ${new Date(event.created_at).toLocaleString()}. Inventory was not changed.`);
    });
  }

  const currentRunning = Boolean(jobId && (!job || !terminal.has(job.state)));
  const methods = comparison?.result.methods ?? plans.map((plan) => plan.result);
  const classical = methods.find((method) => method.method === "CLASSICAL_GP");
  const research = methods.find((method) => method.method === "EGP_PI_INSPIRED");
  const products = [...new Set(methods.flatMap((method) => method.verification?.metrics?.goals.map((goal) => goal.product_id) ?? []))];
  const baseline = comparison?.result.baseline_metrics as Metrics | null | undefined;

  return (
    <main className="or-desk">
      <header className="or-header">
        <Link className="or-brand" href="/">Pantry<span>Pulse</span></Link>
        <nav aria-label="Project links"><Link href="/design-lab">Design lab</Link><a href="https://doi.org/10.1111/itor.70252">Research · 11 Sep 2026</a></nav>
        <span className="or-pill"><FlaskConical size={14} aria-hidden="true" /> Simulated network</span>
      </header>
      <div className="or-title"><p className="or-eyebrow">Community operations desk</p><h1>Compare allocation plans</h1><p>Inspect dated service, unmet need and the trade-offs between two allocation objectives.</p></div>
      <div className="or-disclosure">Fictional stock, forecasts and vulnerability scores. Recommendations and reviews have no reservation or dispatch effect. The live forecast and stock source connection is not qualified.</div>
      {error && <div className="or-alert" role="alert">{error}</div>}
      {notice && <div className="or-notice" role="status">{notice}</div>}
      <div className="or-workspace">
        <aside className="or-controls" aria-label="Scenario and presenter controls">
          <section className="or-card">
            <h2><LockKeyhole size={17} aria-hidden="true" /> Presenter access</h2>
            {presenter ? <><p>Session active. Visitors can open saved simulated results.</p><button className="or-link-button" disabled={busy} onClick={() => action(async () => { await api("/presenter/logout", {}); setPresenter(false); })}>Sign out</button></> :
              <form onSubmit={login} className="or-form"><label>Username<input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} required /></label><label>Password<input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label><button disabled={busy} type="submit">Sign in</button></form>}
          </section>
          <section className="or-card">
            <h2>1. Select inputs</h2><p>Use the published simulated fixture. Loading inputs does not run a solver.</p>
            <button disabled={!presenter || busy || currentRunning} onClick={loadNetwork}>Load simulated network</button>
            {seed && <p className="or-small">Source revision: {seed.source_revision_token}</p>}
            <div className="or-rule" />
            <h2>2. Freeze a scenario</h2>
            <div className="or-form"><label>Transfer mode<select value={mode} onChange={(event) => setMode(event.target.value as Mode | "")}><option value="">Choose a mode…</option><option value="HUB_ONLY">Hub only</option><option value="HUB_AND_PANTRY">Hub and pantry</option></select></label><p className="or-small">Pantry senders must protect seven days of their own demand and reserves without proposed inbound stock.</p><label>Allocation window<select value={windowDays} onChange={(event) => setWindowDays(Number(event.target.value))}>{[1, 2, 3].map((day) => <option key={day} value={day}>{day} {day === 1 ? "day" : "days"}</option>)}</select></label><label>Demand multiplier<input type="number" min="0" max="3" step="0.1" value={multiplier} onChange={(event) => setMultiplier(event.target.value)} /></label><p className="or-small">Changing demand creates a new scenario from the original forecasts. Each date is rounded once on the server.</p><button disabled={!presenter || !seed || !mode || busy || currentRunning} onClick={freezeScenario}>Freeze new scenario <ArrowRight size={15} aria-hidden="true" /></button></div>
          </section>
          <section className="or-card"><h2>Open saved work</h2><form className="or-form" onSubmit={(event) => { event.preventDefault(); setError(""); setComparison(null); setPlans([]); setJob(null); setJobId(savedId.trim()); setLoadGeneration((value) => value + 1); }}><label>Saved job ID<input value={savedId} onChange={(event) => setSavedId(event.target.value)} placeholder="Job UUID" required /></label><button className="or-secondary" disabled={busy}>Open saved results</button></form>{history.length > 0 && <ul className="or-history">{history.map((item) => <li key={item.id}><Link href={`/optimization?job=${item.id}`}>{item.label}</Link></li>)}</ul>}</section>
        </aside>
        <div className="or-results">
          <section className="or-card or-scenario">
            <div><p className="or-eyebrow">Frozen scenario</p><h2>{scenario ? scenario.transfer_mode.replaceAll("_", " ") : "Choose a mode to begin"}</h2><p>{scenario ? `${scenario.planning_days}-day allocation window · seven dated forecast inputs` : "Both methods will share exactly the same operational inputs, policy and solver settings."}</p>{scenario && <p className="or-small">{scenario.source_kind} · {scenario.historical ? "Historical replay" : scenario.stale ? "Stale for current recommendations" : "Current revision"} · {scenario.operational_hash.slice(0, 12)}</p>}</div>
            <button disabled={!presenter || !scenario || busy || currentRunning || Boolean(scenario.stale)} onClick={submitPair}><RefreshCw size={16} aria-hidden="true" /> Compare methods</button>
          </section>
          {job && <div className="or-job" role="status"><Clock3 size={18} aria-hidden="true" /><div><strong>{job.state}</strong><span> · {job.result_completeness}</span><p className="or-small">Job {job.job_id}{job.error_code ? ` · ${job.error_code}` : ""}</p></div>{currentRunning && presenter && <button className="or-secondary" disabled={busy} onClick={() => action(async () => { await api(`/jobs/${job.job_id}/cancel`, {}); setNotice("Cancellation requested. The worker will stop the owned computation."); })}>Cancel</button>}{terminal.has(job.state) && ["FAILED", "TIMED_OUT", "CANCELLED", "INTERRUPTED", "EXPIRED"].includes(job.state) && presenter && <button className="or-secondary" disabled={busy} onClick={() => action(async () => { const retry = await api<Wire["JobAccepted"]>(`/jobs/${job.job_id}/retry`, {}); setJobId(retry.job_id); setSavedId(retry.job_id); setJob(null); })}>Retry manually</button>}</div>}
          {methods.length > 0 ? <>
            <div className="or-methods">{["CLASSICAL_GP", "EGP_PI_INSPIRED"].map((name) => <MethodCard key={name} method={methods.find((item) => item.method === name)} name={name} />)}</div>
            <section className="or-card"><h2>Service within the allocation window</h2><p>Compare common quantities by product. Native objective scores use different formulas and do not establish a universal winner.</p>{products.map((product) => {
              const cGoals = classical?.verification?.metrics?.goals.filter((goal) => goal.product_id === product) ?? [];
              const rGoals = research?.verification?.metrics?.goals.filter((goal) => goal.product_id === product) ?? [];
              const goals = cGoals.length ? cGoals : rGoals;
              return <div className="or-product" key={product}><h3>{unitName(product)}</h3><p className="or-small">Scroll horizontally to compare all columns.</p><div className="or-table-scroll" tabIndex={0} role="region" aria-label={`${unitName(product)} service comparison`}><table><caption className="sr-only">Dated allocation-window service in {unitName(product)}</caption><thead><tr><th>Beneficiary</th><th>Target</th><th>Baseline served</th><th>Classical served / unmet</th><th>Research served / unmet</th><th>Research deficit</th></tr></thead><tbody>{goals.map((goal) => {
                const c = cGoals.find((item) => item.site_id === goal.site_id);
                const r = rGoals.find((item) => item.site_id === goal.site_id);
                const before = baseline?.goals.find((item) => item.product_id === product && item.site_id === goal.site_id);
                return <tr key={goal.site_id}><th scope="row">{siteName(goal.site_id)}</th><td>{goal.target}</td><td>{before?.fulfilled ?? "—"}</td><td>{c ? `${c.fulfilled} / ${c.unmet}` : "Unavailable"}</td><td>{r ? `${r.fulfilled} / ${r.unmet}` : "Unavailable"}</td><td>{r ? <>{ratio(r.weighted_deficit)}<span className="or-flags">{r.ap ? "AP" : ""}{r.rp ? " RP" : ""}</span></> : "—"}</td></tr>;
              })}</tbody></table></div></div>;
            })}<p className="or-small">Deficit values include simulated vulnerability weights. AP and RP use strict thresholds on quantized deficits at scale 10,000.</p></section>
            {methods.map((method) => <section key={method.method} className="or-card"><h2>{method.method === "CLASSICAL_GP" ? "Classical" : "Research-inspired"} transfer recommendations</h2>{method.outcome !== "VERIFIED" ? <p className="or-risk">Method unavailable: {method.error_code ?? method.outcome}. No substitute plan is shown.</p> : method.candidate?.assignments.length ? <ul className="or-transfers">{method.candidate.assignments.map((transfer) => <li key={`${transfer.original_lot_id}:${transfer.route_id}`}><strong>{siteName(transfer.source_id)} <ArrowRight size={14} aria-hidden="true" /> {siteName(transfer.destination_id)}</strong><span>{transfer.units} {transfer.unit} · arrives {transfer.arrival}</span><small>Original lot {transfer.original_lot_id.slice(-6)} · expires {transfer.expires_on}. FEFO loading, dated consumption and donor protection checked.</small></li>)}</ul> : <p>Verified zero-transfer plan. No new movement is recommended for this objective and scenario.</p>}{presenter && plans.filter((plan) => plan.result.method === method.method).map((plan) => <div className="or-review" key={plan.id}><span>Review is an audit event; stock is unchanged.</span><button disabled={busy || method.outcome !== "VERIFIED"} onClick={() => review(plan, "REVIEWED")}>Mark reviewed</button><button className="or-secondary" disabled={busy} onClick={() => review(plan, "REJECTED")}>Reject plan</button></div>)}</section>)}
          </> : <section className="or-card or-empty"><FlaskConical size={28} aria-hidden="true" /><h2>{currentRunning ? "The saved job is running" : "Results appear after a verified solve"}</h2><p>{currentRunning ? "The supervisor runs classical first, then the research-inspired method. Valid first-method results remain available if its partner fails." : "Load the simulated network, choose a transfer mode, then freeze and compare. Visitors can open an existing saved job."}</p></section>}
          <details className="or-card or-methodology"><summary>Methodology and limitations</summary><p>CLASSICAL_GP uses equal ordinary goal weights. EGP_PI_INSPIRED adds fixed institutional vulnerability scores and active absolute and relative deprivation goals to a weighted/Chebyshev blend. This is a local adaptation of Rampazo et al., first published September 11, 2026, DOI <a href="https://doi.org/10.1111/itor.70252">10.1111/itor.70252</a>.</p><p>Shipments count as fulfillment only when consumed on the modeled service dates. Loading uses descending route ETA, destination ID, then FEFO lots. This fixed route order restricts feasible loading schedules. Unknown expiry is unavailable; only original free stock can be exported.</p><p>Forecasts and conservative buffers are planning assumptions, not calibrated probabilities. These simulated results establish no observed fairness or poverty reduction. All OR-DEC-001–020 choices remain provisional Draft 1.1.</p></details>
          {presenter && seed && <div className="or-reset"><button className="or-link-button" disabled={busy || currentRunning} onClick={() => action(async () => { await api("/demo/reset", { dataset_id: seed.dataset_id }); setSeed(null); setNetwork(null); setScenario(null); setComparison(null); setPlans([]); setJob(null); setJobId(null); setHistory([]); window.history.replaceState(null, "", "/optimization"); setNotice("The isolated simulated dataset was reset. No physical inventory was changed."); })}>Reset this simulated dataset</button></div>}
        </div>
      </div>
    </main>
  );
}

function MethodCard({ method, name }: { method: Method | undefined; name: string }) {
  const metric = method?.verification?.metrics;
  return <section className="or-card or-method-card"><p className="or-eyebrow">{name === "CLASSICAL_GP" ? "Conventional comparator" : "Research-inspired adaptation"}</p><h2>{name === "CLASSICAL_GP" ? "Classical GP" : "EGP-PI inspired"}</h2><p className={method?.outcome === "VERIFIED" ? "or-ok" : "or-risk"}>{method?.outcome === "VERIFIED" ? <CheckCircle2 size={16} aria-hidden="true" /> : null}{method?.native_status ?? method?.outcome ?? "Waiting"}</p>{method?.outcome === "VERIFIED" ? <dl><div><dt>Native objective</dt><dd>{ratio(method.objective)}</dd></div><div><dt>Worst weighted deficit</dt><dd>{ratio(metric?.Z)}</dd></div><div><dt>AP / RP excess</dt><dd>{ratio(metric?.ap_excess)} / {ratio(metric?.rp_excess)}</dd></div><div><dt>Search duration</dt><dd>{(method.search_seconds ?? 0).toFixed(3)} s</dd></div></dl> : <p>{method?.error_code ?? "This method has no verified saved result yet."}</p>}{method?.native_status === "FEASIBLE" && <p className="or-small">Feasible and independently verified; optimality is unproven.</p>}</section>;
}
