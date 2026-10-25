import { CheckCircle2, CircleDashed } from "lucide-react";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Schema } from "@/lib/planning-api";
import { cn } from "@/lib/utils";
import {
  METHOD_LABEL, METHODS, decimal, diffAssignments, goalAnchor, methodOutcome, pct, ratio, shortId, solverStatusText, units, usableMetrics,
  type Goal, type GoalRow, type ProductInfo, type SiteInfo,
} from "./model";

// R8 detail evidence and R9 enforced constraints. Every value is read from the saved comparison.

/** The focusable wrapper scrolls; the Table primitive's own container is told not to, so keyboard users can scroll it. */
export const SCROLL = "overflow-x-auto rounded-lg border border-border focus-visible:ring-2 focus-visible:ring-ring outline-none [&>[data-slot=table-container]]:overflow-visible";

type Props = { comparison: Schema["SavedComparison"]; scenario: Schema["ScenarioResult"] | null; rows: GoalRow[]; sites: SiteInfo[]; products: ProductInfo[] };

const siteName = (sites: SiteInfo[], id: string) => sites.find((s) => s.id === id)?.name ?? `Site ${shortId(id)}`;
const productOf = (products: ProductInfo[], id: string) => products.find((p) => p.id === id) ?? { id, name: `Product ${shortId(id)}`, unit: "unit" };

function Flag({ goal, kind, method, verified }: { goal?: Goal; kind: "ap" | "rp"; method: "classical" | "egp"; verified: boolean }) {
  const text = !verified ? "Not verified" : !goal ? "N/A" : goal[kind] ? kind.toUpperCase() : "—";
  return <span data-flag={`${kind}-${method}`} className={cn("whitespace-nowrap", text === kind.toUpperCase() && "rounded border border-pp-warning px-1 font-semibold")}>{text}</span>;
}

/** Side-by-side per-goal table: the method difference for each institution × product, with AP/RP. */
export function MethodGoalTable({ comparison, rows, sites, products }: Props) {
  const classicalOk = !!usableMetrics(methodOutcome(comparison, "CLASSICAL_GP"));
  const egpOk = !!usableMetrics(methodOutcome(comparison, "EGP_PI_INSPIRED"));
  const cell = (goal: Goal | undefined, ok: boolean, read: (g: Goal) => string) => (!ok ? "Not verified" : goal ? read(goal) : "N/A");
  return (
    <div className={SCROLL} tabIndex={0} role="region" aria-label="Goals table, scrolls horizontally">
      <Table className="text-xs">
        <TableCaption className="mt-0 caption-top px-3 py-2 text-left text-sm text-foreground">
          Goals by site and product — Classical GP (C) and EGP-PI-inspired (E) on the same frozen scenario
        </TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead scope="col">Site · product</TableHead>
            <TableHead scope="col" className="text-right">Target</TableHead>
            <TableHead scope="col" className="text-right">Baseline served</TableHead>
            <TableHead scope="col" className="text-right">Served C</TableHead>
            <TableHead scope="col" className="text-right">Served E</TableHead>
            <TableHead scope="col" className="text-right">Unmet C</TableHead>
            <TableHead scope="col" className="text-right">Unmet E</TableHead>
            <TableHead scope="col" className="text-right">Service C</TableHead>
            <TableHead scope="col" className="text-right">Service E</TableHead>
            <TableHead scope="col" className="text-right">Deficit C / E</TableHead>
            <TableHead scope="col" className="text-right">Vulnerability</TableHead>
            <TableHead scope="col" className="text-right">Weighted deficit C / E</TableHead>
            <TableHead scope="col">AP C</TableHead>
            <TableHead scope="col">AP E</TableHead>
            <TableHead scope="col">RP C</TableHead>
            <TableHead scope="col">RP E</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => {
            const product = productOf(products, row.productId);
            const any = row.classical ?? row.egp ?? row.baseline;
            const target = any?.target ?? null;
            const amount = (g: Goal, field: "fulfilled" | "unmet") => units(g[field], product.unit);
            const changed = row.classical && row.egp && row.classical.fulfilled !== row.egp.fulfilled;
            return (
              <TableRow key={row.key} id={goalAnchor(row.siteId, row.productId)} tabIndex={-1}
                className={cn("scroll-mt-20 outline-none target:bg-accent focus-visible:ring-2 focus-visible:ring-ring", changed && "font-medium")}>
                <TableHead scope="row" className="whitespace-nowrap">{siteName(sites, row.siteId)} · {product.name}{changed && <span className="ml-1 text-muted-foreground">(differs)</span>}</TableHead>
                <TableCell className="text-right">{target === null ? "N/A" : units(target, product.unit)}</TableCell>
                <TableCell className="text-right">{row.baseline ? amount(row.baseline, "fulfilled") : "N/A"}</TableCell>
                <TableCell className="text-right">{cell(row.classical, classicalOk, (g) => amount(g, "fulfilled"))}</TableCell>
                <TableCell className="text-right">{cell(row.egp, egpOk, (g) => amount(g, "fulfilled"))}</TableCell>
                <TableCell className="text-right">{cell(row.classical, classicalOk, (g) => amount(g, "unmet"))}</TableCell>
                <TableCell className="text-right">{cell(row.egp, egpOk, (g) => amount(g, "unmet"))}</TableCell>
                <TableCell className="text-right">{cell(row.classical, classicalOk, (g) => pct(ratio(g.service_ratio)))}</TableCell>
                <TableCell className="text-right">{cell(row.egp, egpOk, (g) => pct(ratio(g.service_ratio)))}</TableCell>
                <TableCell className="text-right whitespace-nowrap">{cell(row.classical, classicalOk, (g) => decimal(ratio(g.deficit)))} / {cell(row.egp, egpOk, (g) => decimal(ratio(g.deficit)))}</TableCell>
                <TableCell className="text-right">{any ? decimal(ratio(any.vulnerability)) : "N/A"}</TableCell>
                <TableCell className="text-right whitespace-nowrap">{cell(row.classical, classicalOk, (g) => decimal(ratio(g.weighted_deficit)))} / {cell(row.egp, egpOk, (g) => decimal(ratio(g.weighted_deficit)))}</TableCell>
                <TableCell><Flag goal={row.classical} kind="ap" method="classical" verified={classicalOk} /></TableCell>
                <TableCell><Flag goal={row.egp} kind="ap" method="egp" verified={egpOk} /></TableCell>
                <TableCell><Flag goal={row.classical} kind="rp" method="classical" verified={classicalOk} /></TableCell>
                <TableCell><Flag goal={row.egp} kind="rp" method="egp" verified={egpOk} /></TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

const KIND_LABEL = { added: "Only EGP-PI-inspired", removed: "Only Classical GP", changed: "Quantity differs", same: "Same in both" };

/** Transfers that differ between the methods; no per-transfer benefit is claimed (OPEN-02). */
export function TransferDiffTable({ comparison, sites, products }: Props) {
  const classical = methodOutcome(comparison, "CLASSICAL_GP");
  const egp = methodOutcome(comparison, "EGP_PI_INSPIRED");
  if (!usableMetrics(classical) || !usableMetrics(egp)) {
    return <p className="text-sm text-muted-foreground">Transfer changes need both methods verified; no difference is shown for a failed method.</p>;
  }
  const changes = diffAssignments(classical?.candidate?.assignments ?? [], egp?.candidate?.assignments ?? []);
  if (!changes.length) return <p className="text-sm text-muted-foreground">Neither verified method selected any transfer.</p>;
  return (
    <div className={SCROLL} tabIndex={0} role="region" aria-label="Transfer changes table, scrolls horizontally">
      <Table className="text-xs">
        <TableCaption className="mt-0 caption-top px-3 py-2 text-left text-sm text-foreground">Transfer changes between methods (Classical GP → EGP-PI-inspired)</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead scope="col">Route</TableHead>
            <TableHead scope="col">Change</TableHead>
            <TableHead scope="col">Units</TableHead>
            <TableHead scope="col">Product</TableHead>
            <TableHead scope="col">Departs / arrives</TableHead>
            <TableHead scope="col">Lot</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {changes.map((change) => (
            <TableRow key={change.key}>
              <TableHead scope="row" className="whitespace-nowrap">{siteName(sites, change.sourceId)} → {siteName(sites, change.destinationId)}</TableHead>
              <TableCell>{KIND_LABEL[change.kind]}</TableCell>
              <TableCell className="whitespace-nowrap">{change.classical === null ? "none" : change.classical} → {change.egp === null ? "none" : change.egp} {change.unit}s</TableCell>
              <TableCell>{productOf(products, change.productId).name}</TableCell>
              <TableCell className="whitespace-nowrap">{change.departure} / {change.arrival}</TableCell>
              <TableCell><code>{shortId(change.lotId)}</code></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

/** `result.common_differences` exactly as the API reports it: keys and values, no interpretation. */
export function CommonDifferences({ comparison }: Props) {
  const entries = Object.entries(comparison.result.common_differences ?? {});
  if (!entries.length) return <p className="text-sm text-muted-foreground">The comparison reported no common differences.</p>;
  return (
    <ul aria-label="Common differences as reported" className="grid gap-1 text-xs">
      {entries.map(([key, value]) => (
        <li key={key} className="flex flex-wrap gap-2 border-b border-border py-1 last:border-0">
          <code className="font-semibold">{key}</code>
          <span className="break-all text-muted-foreground">{typeof value === "string" || typeof value === "number" || typeof value === "boolean" ? String(value) : JSON.stringify(value)}</span>
        </li>
      ))}
    </ul>
  );
}

/** SolverStatus per method: native status, verification, objective, bound, gap and time. */
export function SolverStatusTable({ comparison }: Props) {
  return (
    <div className={SCROLL} tabIndex={0} role="region" aria-label="Solver status table, scrolls horizontally">
      <Table className="text-xs">
        <TableCaption className="mt-0 caption-top px-3 py-2 text-left text-sm text-foreground">Solver status and independent replay, per method</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead scope="col">Method</TableHead><TableHead scope="col">Outcome</TableHead><TableHead scope="col">Native status</TableHead>
            <TableHead scope="col">Replay</TableHead><TableHead scope="col">Objective</TableHead><TableHead scope="col">Bound / gap</TableHead><TableHead scope="col">Search / total</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {METHODS.map((method) => {
            const m = methodOutcome(comparison, method);
            return (
              <TableRow key={method}>
                <TableHead scope="row">{METHOD_LABEL[method]}</TableHead>
                <TableCell>{m ? m.outcome : "Not run"}{m?.error_code ? ` · ${m.error_code}` : ""}</TableCell>
                <TableCell>{solverStatusText(m)}</TableCell>
                <TableCell>{m?.verification ? (m.verification.passed ? `Passed (${m.verification.verifier_version})` : `Failed: ${m.verification.violations.join(", ") || "no detail"}`) : "Not verified"}</TableCell>
                <TableCell>{m?.objective ? decimal(ratio(m.objective), 5) : "Unavailable"}</TableCell>
                <TableCell>{m?.native_bound == null ? "Unavailable" : m.native_bound.toFixed(5)} / {m?.gap == null ? "Unavailable" : `${(m.gap * 100).toFixed(3)}%`}</TableCell>
                <TableCell className="whitespace-nowrap">{m ? `${m.search_seconds.toFixed(2)}s / ${m.total_seconds.toFixed(2)}s` : "—"}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      <p className="px-3 py-2 text-xs text-muted-foreground">Native objectives use different scales and are not a shared score. Feasible is not proven optimal.</p>
    </div>
  );
}

export function Provenance({ comparison, scenario }: Props) {
  if (!scenario) return <p className="text-sm text-muted-foreground">The frozen scenario for this comparison could not be read.</p>;
  const forecasts = scenario.payload.package.forecasts;
  const distinct = (values: string[]) => [...new Set(values)].join(", ") || "none reported";
  return (
    <dl className="grid gap-x-4 gap-y-1 text-xs sm:grid-cols-[max-content_1fr]">
      <dt className="text-muted-foreground">Comparison</dt><dd><code>{comparison.id}</code></dd>
      <dt className="text-muted-foreground">Frozen scenario</dt><dd><code>{scenario.id}</code></dd>
      <dt className="text-muted-foreground">Forecast run</dt><dd><code>{scenario.forecast_run_id}</code></dd>
      <dt className="text-muted-foreground">Assumptions</dt><dd><code>{scenario.assumptions_id}</code> (simulated)</dd>
      <dt className="text-muted-foreground">Operational hash</dt><dd className="break-all"><code>{scenario.payload.operational_hash}</code></dd>
      <dt className="text-muted-foreground">Policy hash</dt><dd className="break-all"><code>{scenario.payload.policy_hash}</code> · {scenario.payload.policy.version}</dd>
      <dt className="text-muted-foreground">Forecast method</dt><dd>{distinct(forecasts.map((f) => f.actual_provider))} · interval {distinct(forecasts.map((f) => f.interval_method))} · {distinct(forecasts.map((f) => f.source_classification))}</dd>
      <dt className="text-muted-foreground">Source kind</dt><dd>{scenario.payload.package.source_kind}</dd>
      <dt className="text-muted-foreground">Settings</dt><dd>{Object.entries(comparison.settings).map(([k, v]) => `${k}: ${v}`).join(" · ") || "none"}</dd>
      <dt className="text-muted-foreground">Warnings</dt><dd>{[...scenario.payload.package.provenance_warnings, ...comparison.result.warnings].join(" · ") || "none"}</dd>
    </dl>
  );
}

// What independent-replay-v2 checks (apps/api/app/services/optimization/verify.py).
const REPLAY_CHECKS = [
  "Lot conservation: no stock created",
  "FEFO lot lineage (earliest expiry first)",
  "Donor reserve protection",
  "Route, handling, receiving and storage capacity",
  "Simulated transport cost budget",
  "Claimed metrics match the replay",
];

/** R9: constraints listed as checked only when the independent replay passed for every verified method. */
export function EnforcedConstraints({ comparison }: { comparison: Schema["SavedComparison"] | null }) {
  const verified = comparison ? METHODS.filter((m) => usableMetrics(methodOutcome(comparison, m))) : [];
  return (
    <section aria-labelledby="constraints-heading" className="rounded-lg border border-border bg-card p-3 text-xs">
      <h3 id="constraints-heading" className="mb-2 text-sm font-semibold">Enforced constraints</h3>
      {verified.length ? (
        <>
          <p className="mb-2 text-muted-foreground">Checked by independent replay for {verified.map((m) => METHOD_LABEL[m]).join(" and ")}.</p>
          <ul className="grid gap-1">
            {REPLAY_CHECKS.map((item) => <li key={item} className="flex items-start gap-1.5"><CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-pp-teal" aria-hidden="true" />{item}</li>)}
          </ul>
        </>
      ) : (
        <p className="flex items-center gap-1.5 text-muted-foreground"><CircleDashed className="size-3.5" aria-hidden="true" />Not verified: no independently replayed result is loaded.</p>
      )}
    </section>
  );
}
