"use client";

import { useState } from "react";
import { useReducedMotion } from "motion/react";
import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Methodology, Schema } from "@/lib/planning-api";
import { cn } from "@/lib/utils";
import { SCROLL } from "./evidence";
import {
  METHOD_LABEL, METHODS, count, coverage, expired, flagged, methodOutcome, pct, ratio, shortId, solverStatusText, tradeoffs, unmet, units,
  usableMetrics, when, type GoalRow, type Method, type Metrics, type ProductInfo, type SiteInfo,
} from "./model";

type Comparison = Schema["SavedComparison"];
type Common = { comparison: Comparison; rows: GoalRow[]; sites: SiteInfo[]; products: ProductInfo[] };

const OUTCOME_LABEL: Record<Schema["ComparisonResult"]["outcome"], string> = { SUCCEEDED: "Both methods verified", PARTIAL: "Partially available", FAILED: "Comparison failed" };

/** MethodPairHeader + SolverStatus: one frozen scenario, two method statuses, never substituted. */
export function MethodPairHeader({ comparison }: { comparison: Comparison }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <Badge variant="outline" className="border-foreground/30 font-semibold">{OUTCOME_LABEL[comparison.result.outcome]}</Badge>
      {METHODS.map((method) => {
        const outcome = methodOutcome(comparison, method);
        const ok = !!usableMetrics(outcome);
        return (
          <span key={method} className={cn("inline-flex items-center gap-1.5 rounded-md border px-2 py-1", ok ? "border-border" : "border-pp-danger/60")}>
            <MethodSwatch method={method} />
            <span className="font-medium">{METHOD_LABEL[method]}</span>
            <span className="text-muted-foreground">{solverStatusText(outcome)}{ok ? " · replay passed" : ""}</span>
          </span>
        );
      })}
      <span className="text-muted-foreground">Saved {when(comparison.recorded_at)} · comparison <code>{shortId(comparison.id)}</code>{comparison.stale && " · STALE sources"}{comparison.historical && " · HISTORICAL"}</span>
    </div>
  );
}

/** Classical: hatched slate; EGP-PI-inspired: solid teal; baseline: outline. Identity never relies on colour alone. */
export function MethodSwatch({ method }: { method: Method | "BASELINE" }) {
  return (
    <svg width="14" height="10" aria-hidden="true" className="shrink-0">
      {method === "BASELINE" ? <rect x="0.75" y="0.75" width="12.5" height="8.5" rx="1.5" fill="none" stroke="var(--pp-ink-muted)" strokeWidth="1.5" />
        : method === "CLASSICAL_GP" ? <><rect width="14" height="10" rx="2" style={{ fill: "url(#pp-hatch)" }} /><rect x="0.5" y="0.5" width="13" height="9" rx="1.5" fill="none" stroke="var(--pp-neutral)" /></>
          : <rect width="14" height="10" rx="2" style={{ fill: "var(--pp-teal)" }} />}
    </svg>
  );
}

export function HatchDefs() {
  return (
    <svg width="0" height="0" aria-hidden="true" className="absolute">
      <defs>
        <pattern id="pp-hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="5" height="5" style={{ fill: "var(--pp-surface-muted)" }} />
          <line x1="0" y1="0" x2="0" y2="5" style={{ stroke: "var(--pp-neutral)" }} strokeWidth="3" />
        </pattern>
      </defs>
    </svg>
  );
}

type Column = { key: Method | "BASELINE"; label: string; metrics: Metrics | null; reason: string };
function columns(comparison: Comparison): Column[] {
  const baseline = comparison.result.baseline_metrics ?? null;
  return [
    { key: "BASELINE", label: "Baseline", metrics: baseline, reason: "No baseline" },
    ...METHODS.map((m) => {
      const outcome = methodOutcome(comparison, m);
      return { key: m, label: METHOD_LABEL[m], metrics: usableMetrics(outcome), reason: outcome?.error_code ?? (outcome ? solverStatusText(outcome) : "Not run") };
    }),
  ];
}

function MetricCard({ title, basis, comparison, products, read }: {
  title: string; basis: string; comparison: Comparison; products: ProductInfo[]; read: (metrics: Metrics, product: ProductInfo) => string;
}) {
  const cols = columns(comparison);
  return (
    <article className="rounded-lg border border-border bg-card p-3">
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="mb-2 text-xs text-muted-foreground">{basis}</p>
      <div className={cn(SCROLL, "border-0")} tabIndex={0} role="region" aria-label={`${title} table`}>
      <Table className="text-xs">
        <TableCaption className="sr-only">{title} by product: baseline, Classical GP and EGP-PI-inspired</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead scope="col" className="h-7 px-1">Product</TableHead>
            {cols.map((c) => <TableHead key={c.key} scope="col" className="h-7 px-1 text-right"><span className="inline-flex items-center gap-1"><MethodSwatch method={c.key} />{c.label}</span></TableHead>)}
          </TableRow>
        </TableHeader>
        <TableBody>
          {products.map((p) => (
            <TableRow key={p.id}>
              <TableHead scope="row" className="h-7 px-1">{p.name}</TableHead>
              {cols.map((c) => <TableCell key={c.key} className="px-1 py-1 text-right tabular-nums">{c.metrics ? read(c.metrics, p) : <span className="text-muted-foreground">{c.reason}</span>}</TableCell>)}
            </TableRow>
          ))}
        </TableBody>
      </Table>
      </div>
    </article>
  );
}

/** R4 ScenarioResultsSummary (Q-55-5): coverage, unmet, AP/RP flags and simulated cost/expiry — per product, both methods. */
export function ScenarioResultsSummary({ comparison, products }: { comparison: Comparison; products: ProductInfo[] }) {
  const cols = columns(comparison);
  return (
    <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-1 min-[1700px]:grid-cols-2">
      <MetricCard title="Service coverage" basis="Σ served ÷ Σ target over positive-target goals, allocation window" comparison={comparison} products={products}
        read={(m, p) => pct(coverage(m, p.id))} />
      <MetricCard title="Unmet units" basis="Target not served in the allocation window, per product unit" comparison={comparison} products={products}
        read={(m, p) => units(unmet(m, p.id), p.unit)} />
      <MetricCard title="AP / RP flagged goals" basis="Research measures: absolute / relative poverty flags of the product group" comparison={comparison} products={products}
        read={(m, p) => { const f = flagged(m, p.id); return `AP ${f.ap} · RP ${f.rp} of ${f.size}`; }} />
      <article className="rounded-lg border border-border bg-card p-3">
        <h3 className="text-sm font-semibold">Simulated cost points</h3>
        <p className="mb-2 text-xs text-muted-foreground">Simulated transport cost points (not currency) and projected expired units over 7 days</p>
        <ul className="grid gap-1 text-xs">
          {cols.map((c) => (
            <li key={c.key} className="flex flex-wrap items-baseline justify-between gap-x-2">
              <span className="inline-flex items-center gap-1 font-medium"><MethodSwatch method={c.key} />{c.label}</span>
              {c.metrics ? <span className="tabular-nums">{count(c.metrics.cost_minor)} points · expired {products.map((p) => {
                const n = expired(c.metrics!, p.id);
                return n === null ? `${p.name} N/A` : units(n, p.unit);
              }).join(", ")}</span> : <span className="text-muted-foreground">{c.reason}</span>}
            </li>
          ))}
        </ul>
      </article>
    </div>
  );
}

type FillDatum = { site: string; tick: string; target: number | null; baseline: number | null; classical: number | null; egp: number | null };

/** R5 ProjectedFillRateBySite: service ratio per beneficiary for one product; N/A for a zero target. */
export function ProjectedFillRateBySite({ comparison, rows, sites, products, productId, onProduct }: Common & { productId: string; onProduct: (id: string) => void }) {
  const reduce = useReducedMotion();
  const product = products.find((p) => p.id === productId) ?? products[0];
  const classicalOk = !!usableMetrics(methodOutcome(comparison, "CLASSICAL_GP"));
  const egpOk = !!usableMetrics(methodOutcome(comparison, "EGP_PI_INSPIRED"));
  const beneficiaries = sites.filter((s) => rows.some((r) => r.siteId === s.id));
  const data: FillDatum[] = beneficiaries.map((site) => {
    const row = rows.find((r) => r.siteId === site.id && r.productId === product?.id);
    const target = (row?.classical ?? row?.egp ?? row?.baseline)?.target ?? null;
    const value = (g?: Schema["GoalMetric"], ok = true) => (ok && g ? ratio(g.service_ratio) : null);
    return { site: site.name, tick: target === 0 ? `${site.name} · N/A` : site.name, target,
      baseline: value(row?.baseline), classical: value(row?.classical, classicalOk), egp: value(row?.egp, egpOk) };
  });
  const asPct = (d: FillDatum, key: "baseline" | "classical" | "egp") => (d[key] === null ? null : Math.round(d[key]! * 1000) / 10);
  const chartData = data.map((d) => ({ ...d, baselinePct: asPct(d, "baseline"), classicalPct: asPct(d, "classical"), egpPct: asPct(d, "egp") }));
  if (!product) return null;
  return (
    <section aria-labelledby="fill-heading" className="rounded-lg border border-border bg-card p-3 md:p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 id="fill-heading" className="text-base font-semibold">Projected fill rate by site</h2>
        <Select value={product.id} onValueChange={onProduct}>
          <SelectTrigger aria-label="Fill-rate product" className="h-9 w-56"><SelectValue /></SelectTrigger>
          <SelectContent>{products.map((p) => <SelectItem key={p.id} value={p.id}>{p.name} ({p.unit})</SelectItem>)}</SelectContent>
        </Select>
      </div>
      <p className="mb-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
        {(["BASELINE", ...METHODS] as const).map((m) => <span key={m} className="inline-flex items-center gap-1"><MethodSwatch method={m} />{m === "BASELINE" ? "Baseline (no transfers)" : METHOD_LABEL[m]}</span>)}
        <span>Served ÷ target, {product.name} ({product.unit}s), allocation window</span>
      </p>
      <div className="h-72 w-full" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 480, height: 288 }}>
          <BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 12, bottom: 4, left: 4 }} barGap={2} barCategoryGap="22%" accessibilityLayer={false}>
            <CartesianGrid horizontal={false} stroke="var(--pp-border)" />
            <XAxis type="number" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11, fill: "var(--pp-ink-muted)" }} stroke="var(--pp-border)" />
            <YAxis type="category" dataKey="tick" width={132} tick={{ fontSize: 11, fill: "var(--pp-ink)" }} stroke="var(--pp-border)" />
            <Bar dataKey="baselinePct" name="Baseline" fill="transparent" stroke="var(--pp-ink-muted)" strokeWidth={1.25} radius={[0, 3, 3, 0]} isAnimationActive={false} />
            <Bar dataKey="classicalPct" name="Classical GP" fill="url(#pp-hatch)" stroke="var(--pp-neutral)" radius={[0, 3, 3, 0]} isAnimationActive={!reduce} animationDuration={320} />
            <Bar dataKey="egpPct" name="EGP-PI-inspired" fill="var(--pp-teal)" radius={[0, 3, 3, 0]} isAnimationActive={!reduce} animationDuration={320} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className={cn(SCROLL, "mt-2 border-0")} tabIndex={0} role="region" aria-label="Fill-rate data table">
      <Table className="text-xs">
        <TableCaption className="mt-0 caption-top pb-1 text-left text-xs text-muted-foreground">Projected fill rate by site, {product.name} ({product.unit}s): served of target</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead scope="col" className="h-7 px-1">Site</TableHead>
            <TableHead scope="col" className="h-7 px-1 text-right">Target</TableHead>
            <TableHead scope="col" className="h-7 px-1 text-right">Baseline</TableHead>
            <TableHead scope="col" className="h-7 px-1 text-right">Classical GP</TableHead>
            <TableHead scope="col" className="h-7 px-1 text-right">EGP-PI-inspired</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((d) => (
            <TableRow key={d.site}>
              <TableHead scope="row" className="h-7 px-1">{d.site}</TableHead>
              <TableCell className="px-1 py-1 text-right">{d.target === null ? "N/A" : units(d.target, product.unit)}</TableCell>
              <TableCell className="px-1 py-1 text-right">{pct(d.baseline)}</TableCell>
              <TableCell className="px-1 py-1 text-right">{classicalOk ? pct(d.classical) : "Not verified"}</TableCell>
              <TableCell className="px-1 py-1 text-right">{egpOk ? pct(d.egp) : "Not verified"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      </div>
    </section>
  );
}

/** ScenarioDelta: EGP-PI-inspired minus Classical GP, direction by arrow and sign, never by colour. */
export function ScenarioDelta({ value, unit }: { value: number | null; unit: string }) {
  if (value === null) return <span className="text-muted-foreground">N/A</span>;
  const Icon = value > 0 ? ArrowUp : value < 0 ? ArrowDown : Minus;
  return (
    <span className="inline-flex items-center gap-1 tabular-nums">
      <Icon className="size-3.5" aria-hidden="true" />
      {value > 0 ? "+" : value < 0 ? "−" : ""}{Math.abs(value).toLocaleString("en-US", { maximumFractionDigits: 1 })} {unit}
    </span>
  );
}

type RailMetric = "coverage" | "unmet" | "ap" | "cost";
const RAIL_LABEL: Record<RailMetric, string> = { coverage: "Service coverage", unmet: "Unmet units", ap: "AP-flagged goals", cost: "Simulated cost points" };

/** R6 ComparisonRail: Methods (same scenario) only (Q-55-2). */
export function ComparisonRail({ comparison, products, productId }: { comparison: Comparison; products: ProductInfo[]; productId: string }) {
  const [metric, setMetric] = useState<RailMetric>("coverage");
  const product = products.find((p) => p.id === productId) ?? products[0];
  const read = (m: Metrics | null): number | null => {
    if (!m || !product) return null;
    if (metric === "coverage") { const c = coverage(m, product.id); return c === null ? null : c * 100; }
    if (metric === "unmet") return unmet(m, product.id);
    if (metric === "ap") return flagged(m, product.id).ap;
    return m.cost_minor;
  };
  const unit = metric === "coverage" ? "pts" : metric === "unmet" ? `${product?.unit ?? "unit"}s` : metric === "ap" ? "goals" : "points";
  const format = (v: number | null) => (v === null ? "N/A" : metric === "coverage" ? `${v.toFixed(1)}%` : metric === "unmet" ? units(v, product?.unit ?? "unit") : count(v));
  const cols = columns(comparison);
  const c = read(cols[1].metrics), e = read(cols[2].metrics);
  return (
    <section aria-labelledby="rail-heading" className="rounded-lg border border-border bg-card p-3 md:p-4">
      <h2 id="rail-heading" className="text-base font-semibold">Comparison</h2>
      <p className="mb-2 text-xs text-muted-foreground">Comparison mode: Methods (same scenario) · scenario <code>{shortId(comparison.scenario_id)}</code></p>
      <Select value={metric} onValueChange={(v) => setMetric(v as RailMetric)}>
        <SelectTrigger aria-label="Comparison metric" className="mb-2 h-9 w-full"><SelectValue /></SelectTrigger>
        <SelectContent>{(Object.keys(RAIL_LABEL) as RailMetric[]).map((k) => <SelectItem key={k} value={k}>{RAIL_LABEL[k]}{k !== "cost" && product ? ` · ${product.name}` : ""}</SelectItem>)}</SelectContent>
      </Select>
      <ul className="grid gap-1.5 text-sm">
        {cols.map((col) => (
          <li key={col.key} className="flex items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1.5"><MethodSwatch method={col.key} />{col.label}</span>
            <span className="tabular-nums">{col.metrics ? format(read(col.metrics)) : <span className="text-xs text-muted-foreground">{col.reason}</span>}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 flex items-center justify-between border-t border-border pt-2 text-xs">
        <span className="text-muted-foreground">EGP-PI-inspired vs Classical GP</span>
        <ScenarioDelta value={c === null || e === null ? null : e - c} unit={unit} />
      </p>
    </section>
  );
}

/** R7 KeyTradeoffs: deterministic, evidence-linked bullets; no causal or universal claim. */
export function KeyTradeoffs({ comparison, rows, sites, products, methodology }: Common & { methodology: Methodology | null }) {
  const classical = usableMetrics(methodOutcome(comparison, "CLASSICAL_GP"));
  const egp = usableMetrics(methodOutcome(comparison, "EGP_PI_INSPIRED"));
  const items = classical && egp ? tradeoffs(rows, sites, products, classical, egp) : null;
  return (
    <section aria-labelledby="tradeoffs-heading" className="rounded-lg border border-border bg-card p-3 md:p-4">
      <h2 id="tradeoffs-heading" className="mb-2 text-base font-semibold">Key trade-offs</h2>
      {items ? (
        <ul className="grid list-disc gap-2 pl-4 text-sm">
          {items.map((item) => (
            <li key={item.id}>{item.anchor ? <a href={`#${item.anchor}`} className="font-medium text-primary underline underline-offset-2">{item.linkText}</a> : null}{item.text}</li>
          ))}
        </ul>
      ) : <p className="text-sm text-muted-foreground">Trade-offs need both methods verified. A failed method is shown separately and never replaced.</p>}
      <p className="mt-3 border-t border-border pt-2 text-xs text-muted-foreground">
        EGP-PI-inspired is a bounded adaptation inspired by Rampazo et al., “An extended goal programming framework incorporating poverty measures”,
        International Transactions in Operational Research, first published online 11 September 2026 (<a className="underline" href="https://doi.org/10.1111/itor.70252">DOI 10.1111/itor.70252</a>).
        It does not reproduce the paper’s full model or results. Vulnerability attributes and all data are simulated.
        {methodology?.limitations.length ? ` ${methodology.limitations.join(" ")}` : ""}
      </p>
    </section>
  );
}
