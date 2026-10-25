"use client";

import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import { FlipCard } from "./flip-card";
import { formatDay, formatPercent, formatRange, formatUnits } from "./format";
import { beneficiaries, cellKey, itemRisk, seriesTotals } from "./metrics";
import type { ExplorerSnapshot, Product } from "./types";

function Loading() {
  return <Skeleton data-loading-slot className="mt-2 h-full min-h-[200px] w-full" />;
}

/** Front face: sites carry no region metadata, so the fallback compares fill rate per site. */
function FillBySite({ snapshot, product }: { snapshot: ExplorerSnapshot; product: Product }) {
  const range = formatRange(snapshot.dates);
  const rows = beneficiaries(snapshot).map((site) => {
    const totals = seriesTotals(snapshot.projections[cellKey(site.id, product.id)]);
    const complete = totals?.complete && totals.target > 0;
    return { site, totals, pct: complete ? Math.min(100, (totals.served / totals.target) * 100) : null, label: complete ? formatPercent(totals.served, totals.target) : null };
  });
  const plotted = rows.filter((row) => row.pct !== null).map((row) => ({ name: row.site.shortName, pct: row.pct as number, label: row.label as string }));
  const notEvaluated = rows.filter((row) => row.pct === null);
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <p className="text-xs text-muted-foreground">Predicted fill rate, {product.name} ({product.unitPlural}), {range}</p>
      <p role="note" className="rounded-md border border-dashed border-border px-2.5 py-1.5 text-xs text-foreground">Regional grouping unavailable: sites carry no region metadata.</p>
      <h3 className="text-xs font-semibold text-foreground">By site (no regions)</h3>
      {plotted.length === 0 ? (
        <p className="text-sm text-foreground">No site has a complete projection for this product.</p>
      ) : (
        <div className="min-h-0 flex-1" aria-hidden="true">
          <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 320, height: 180 }}>
            <BarChart data={plotted} layout="vertical" margin={{ top: 0, right: 44, bottom: 0, left: 0 }} barCategoryGap={6} accessibilityLayer={false}>
              <CartesianGrid stroke="var(--pp-border)" strokeDasharray="2 4" horizontal={false} />
              <XAxis type="number" domain={[0, 100]} ticks={[0, 50, 100]} tickFormatter={(value) => `${value}%`} tick={{ fill: "var(--pp-ink-muted)", fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="name" width={104} tick={{ fill: "var(--pp-ink)", fontSize: 12 }} tickLine={false} axisLine={false} />
              <Bar dataKey="pct" fill="var(--pp-teal)" radius={[0, 4, 4, 0]} maxBarSize={18} isAnimationActive={false}>
                <LabelList dataKey="label" position="right" style={{ fill: "var(--pp-ink)", fontSize: 12 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <table className="sr-only">
        <caption>Predicted fill rate by site, {product.name} ({product.unitPlural}), {range}</caption>
        <thead><tr><th scope="col">Site</th><th scope="col">Predicted fill rate</th><th scope="col">Served of target</th></tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.site.id}>
              <th scope="row">{row.site.name}</th>
              <td>{row.label ?? "Not evaluated"}</td>
              <td>{row.label && row.totals ? `${row.totals.served.toLocaleString("en-US")} of ${formatUnits(row.totals.target, product)}` : "Not evaluated"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {notEvaluated.length > 0 && <p className="text-xs text-foreground">Not evaluated: {notEvaluated.map((row) => row.site.shortName).join(", ")}</p>}
    </div>
  );
}

/** Back face: one row per product (two in the demo); each in its own unit. */
function ItemRiskOverview({ snapshot }: { snapshot: ExplorerSnapshot }) {
  const range = formatRange(snapshot.dates);
  const rows = itemRisk(snapshot);
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <p className="text-xs text-muted-foreground">Every product, {range}. Ordered by first projected deficit: a display sort only, not a priority or procurement policy.</p>
      <ul className="grid gap-2">
        {rows.map((row) => (
          <li key={row.product.id} data-item-row className="rounded-lg border border-border px-3 py-2">
            <p className="text-sm font-semibold text-foreground">{row.product.name} <span className="font-normal text-muted-foreground">({row.product.unitPlural})</span></p>
            <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs tabular-nums">
              <dt className="text-muted-foreground">First projected deficit</dt>
              <dd className="text-foreground">{row.firstDeficit === null ? (snapshot.dates.length === 0 ? "Not evaluated" : `None, ${range}`) : formatDay(snapshot.dates[row.firstDeficit])}</dd>
              <dt className="text-muted-foreground">Demand vs served</dt>
              <dd className="text-foreground">{row.evaluated === 0 ? "Not evaluated" : `${formatUnits(row.target, row.product)} vs ${formatUnits(row.served, row.product)}`}</dd>
              <dt className="text-muted-foreground">Unmet</dt>
              <dd className="text-foreground">{row.evaluated === 0 ? "Not evaluated" : `${formatUnits(row.unmet, row.product)} over ${row.evaluated} of ${row.total} beneficiaries`}</dd>
            </dl>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Fixed-footprint analytics flip beside the forecast chart: Fill Rate by Region ↔ Item Risk Overview. */
export function AnalyticsPanel({ snapshot, product }: { snapshot: ExplorerSnapshot | null; product: Product | null }) {
  const ready = snapshot && product ? { snapshot, product } : null;
  return (
    <FlipCard
      name="analytics"
      className="h-[500px] sm:h-[420px] lg:h-[400px]"
      faceClassName="gap-2 p-4 max-sm:pb-14 md:p-5"
      control="top"
      duration={0.38}
      disabled={!ready}
      front={{ title: "Fill Rate by Region", content: ready ? <FillBySite snapshot={ready.snapshot} product={ready.product} /> : <Loading /> }}
      back={{ title: "Item Risk Overview", content: ready ? <ItemRiskOverview snapshot={ready.snapshot} /> : <Loading /> }}
    />
  );
}
