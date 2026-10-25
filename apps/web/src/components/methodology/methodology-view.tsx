"use client";

import { useEffect, useState } from "react";
import { ExternalLink } from "lucide-react";
import { AppShell } from "@/components/shell/app-shell";
import { usePresenter } from "@/components/shell/presenter-session";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, planningApi, type Methodology } from "@/lib/planning-api";

// Methodology & audit (blueprint §7). Research attribution is static text checked against
// .claude/skills/research-claims-check; live solver settings come from GET /allocation-methodology
// (presenter only). Nothing here runs a forecast or a solve.

const DOI = "10.1111/itor.70252";

const ADAPTED = [
  "Absolute-poverty (AP) and relative-poverty (RP) goals with reified thresholds",
  "Normalized institutional vulnerability attributes (simulated, for fictional institutions)",
  "A weighted plus Chebyshev blend of goal deviations",
  "First-expiry-first-out (FEFO) lot constraints",
];

const NOT_REPRODUCED = [
  "Endogenous vulnerability weights",
  "The paper's multi-period model",
  "The paper's full equations (8)–(20) and (21)–(38)",
  "The paper's reported results",
];

const LOGIC: [string, string][] = [
  ["r[i,p]", "forecast-derived integer target for beneficiary i, product p"],
  ["f[i,p]", "feasible service, 0 ≤ f ≤ r"],
  ["u[i,p]", "unmet units, r − f"],
  ["δ[i,p]", "normalized shortfall u / r (positive targets only; zero target is N/A)"],
  ["v[i]", "vulnerability weight from prepared institution attributes"],
  ["z[i,p]", "weighted shortfall v × δ"],
  ["W, Z", "sum and maximum of z across positive-target goals"],
  ["AP flag", "weighted shortfall strictly above the absolute threshold"],
  ["RP flag", "weighted shortfall minus the same-product group mean strictly above the relative threshold"],
];

const MODE_LABEL: Record<string, string> = { HUB_ONLY: "Hub to pantry only", HUB_AND_PANTRY: "Hub and pantry-to-pantry" };

function LiveSettings() {
  const { state, expired } = usePresenter();
  const [value, setValue] = useState<Methodology | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (state !== "presenter") return;
    let active = true;
    planningApi.methodology().then((result) => { if (active) setValue(result); }).catch((e) => {
      if (!active) return;
      if (e instanceof ApiError && e.status === 401) { expired(); return; }
      setError(e instanceof ApiError ? `Live settings unavailable (${e.code}).` : "Live settings unavailable.");
    });
    return () => { active = false; };
  }, [state, expired]);

  if (state === "checking") return <p role="status" className="text-sm text-muted-foreground">Checking presenter session…</p>;
  if (state === "visitor") return <p className="text-sm text-muted-foreground">Live solver settings are read from the planning API after presenter sign-in (sidebar). The research description on this page does not depend on it.</p>;
  if (error) return <p role="alert" className="text-sm">{error}</p>;
  if (!value) return <p role="status" className="text-sm text-muted-foreground">Loading live settings…</p>;
  const rows: [string, React.ReactNode][] = [
    ["Methods compared", value.methods.join(" · ")],
    ["Transfer modes", <>{value.transfer_modes.map((m) => MODE_LABEL[m] ?? m).join(" · ")}<span className="text-muted-foreground"> — {value.default_transfer_mode === null ? "no default; the presenter must choose" : `default ${value.default_transfer_mode}`}</span></>],
    ["Allocation window", `${value.planning_window_days.join(", ")} day(s), inside a 7-day projection`],
    ["Native search per method", `${value.search_seconds.default} s default, ${value.search_seconds.maximum} s maximum`],
    ["Donor protection", `${value.donor_protection_days} local days of the sending site's own service and reserve`],
    ["Expiry rule", value.expiry],
    ["Stock effect", value.stock_effect === "NONE_SIMULATION_ONLY" ? "None — simulation only (no reservation, dispatch or purchase)" : value.stock_effect],
    ["Decision records", value.decision_ids.length ? value.decision_ids.join(", ") : "None listed"],
  ];
  return (
    <div className="grid gap-3">
      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[minmax(10rem,auto)_1fr]">
        {rows.map(([term, detail]) => (
          <div key={term} className="contents">
            <dt className="font-medium">{term}</dt>
            <dd className="text-foreground">{detail}</dd>
          </div>
        ))}
      </dl>
      {value.limitations.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold">Limitations reported by the API</h3>
          <ul className="mt-1 list-disc pl-5 text-sm">{value.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      )}
    </div>
  );
}

export function MethodologyView() {
  return (
    <AppShell active="methodology">
      <div className="flex flex-1 flex-col gap-4 px-4 pt-3 pb-6 md:gap-6 md:px-6 md:py-5">
        <header>
          <p className="font-condensed text-xs font-semibold tracking-[0.16em] text-muted-foreground uppercase">Research &amp; audit</p>
          <h1 className="text-[26px] leading-tight font-semibold tracking-tight md:text-[28px]">Methodology</h1>
          <p className="text-sm text-muted-foreground">How PantryPulse projects shortages and compares two allocation methods. All network data is simulated; results are decision support only.</p>
        </header>

        <Card>
          <CardHeader>
            <CardTitle>Research source</CardTitle>
            <CardDescription>First published online 11 September 2026 · International Transactions in Operational Research</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm">
            <p>
              Rampazo, R. C., Jones, D. F., Godoi, L. F., Iamamoto, M. O., &amp; Cantane, D. R. (2026). <cite>An extended goal programming framework incorporating poverty measures: application to food bank logistics.</cite> International Transactions in Operational Research.{" "}
              <a className="inline-flex items-center gap-1 font-medium underline underline-offset-2" href={`https://doi.org/${DOI}`} target="_blank" rel="noreferrer">
                DOI {DOI}<ExternalLink className="size-3.5" aria-hidden="true" /><span className="sr-only"> (opens in a new tab)</span>
              </a>
            </p>
            <p><Badge variant="outline">EGP_PI_INSPIRED</Badge> is a bounded, research-inspired subset of this framework. It is not a reproduction of the paper&apos;s model, and the paper&apos;s reported results are not claimed here.</p>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <h3 className="font-semibold">Adapted</h3>
                <ul className="mt-1 list-disc pl-5">{ADAPTED.map((item) => <li key={item}>{item}</li>)}</ul>
              </div>
              <div>
                <h3 className="font-semibold">Not reproduced</h3>
                <ul className="mt-1 list-disc pl-5">{NOT_REPRODUCED.map((item) => <li key={item}>{item}</li>)}</ul>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 lg:grid-cols-2 lg:gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Two methods, one controlled comparison</CardTitle>
              <CardDescription>Classical goal programming (CLASSICAL_GP) and EGP_PI_INSPIRED</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-2 text-sm">
              <p>Both methods receive the same frozen scenario: the same forecast run, inventory lots, transfer mode, candidate routes, hard constraints and solver settings. Only the objective differs, so a change in who is served comes from the objective, not from different inputs.</p>
              <p>Hard rules are never preferences: integer units are conserved, lots are used first-expiry-first-out, sending sites keep their dated reserve, and receiving and handling capacities hold. An independent replay re-checks every saved plan.</p>
              <p>A <strong>FEASIBLE</strong> solver status is not proof of optimality, and UNKNOWN or MODEL_INVALID is never shown as an allocation. A different result for one institution is a trade-off in this simulated scenario, not evidence that either method is better in general.</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Research logic summary</CardTitle>
              <CardDescription>Explanatory only; the solver and the independent checker own these calculations</CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="grid gap-x-4 gap-y-1.5 text-sm sm:grid-cols-[6rem_1fr]">
                {LOGIC.map(([symbol, meaning]) => (
                  <div key={symbol} className="contents">
                    <dt className="font-mono tabular-nums">{symbol}</dt>
                    <dd>{meaning}</dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 lg:grid-cols-2 lg:gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Forecasts and shortage projection</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-2 text-sm">
              <p>Seven-day demand and donation forecasts are projections. The demo baseline is seasonal naive with an explicitly enabled, labeled fallback; Chronos-2 and OR-Tools are supporting technology. Each screen shows the provider that actually ran.</p>
              <p>Missing demand stays missing; it is never turned into zero. Raw quantiles, when a model produces them, are not calibrated intervals or stockout probabilities. Predicted donations never count as stock; only confirmed arrivals do.</p>
              <p>Each product (for example meals and bottled water) keeps its own unit; quantities are never added across products.</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Live solver settings</CardTitle>
              <CardDescription>GET /api/v1/allocation-methodology</CardDescription>
            </CardHeader>
            <CardContent><LiveSettings /></CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Data, review and audit</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm">
            <p>The six beneficiary pantries, the hub, their vulnerability attributes and all demand, donation and inventory records are <strong>simulated</strong>. Attributes describe fictional institutions, never individuals or protected traits.</p>
            <p>&ldquo;Mark reviewed — simulation&rdquo; records a review marker on a saved plan. It reserves no stock and dispatches or purchases nothing. Saved scenarios, forecasts and comparisons are immutable; edits create new versions.</p>
            <p className="text-muted-foreground">An event/audit log view is not exposed by the API yet.</p>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
