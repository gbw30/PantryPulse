"use client";

import { useId, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDay, formatNumber, formatRange, formatShortDate, formatUnits, providerLabel } from "./format";
import { beneficiaries, cellKey, chartSeries, runMethods, type ChartRow } from "./metrics";
import type { ExplorerSnapshot, Product } from "./types";

// Series identity is carried by line style and marker shape as well as colour (the token palette is
// too close in hue to separate series by colour alone): demand dashed with circles, stock solid with
// squares, donations dotted.
const DEMAND_DASH = "6 4";
const DONATION_DASH = "2 3";

function Square({ cx, cy, index }: { cx?: number; cy?: number; index?: number }) {
  if (cx === undefined || cy === undefined) return <g key={`s-${index}`} />;
  return <rect key={`s-${index}`} x={cx - 3} y={cy - 3} width={6} height={6} fill="var(--card)" stroke="var(--pp-teal)" strokeWidth={1.5} />;
}

function LegendLine({ dash, color, marker }: { dash?: string; color: string; marker?: "circle" | "square" }) {
  return (
    <svg width="22" height="10" aria-hidden="true" className="shrink-0">
      <line x1="0" y1="5" x2="22" y2="5" stroke={color} strokeWidth="2" strokeDasharray={dash} />
      {marker === "circle" && <circle cx="11" cy="5" r="3" fill={color} />}
      {marker === "square" && <rect x="8" y="2" width="6" height="6" fill="var(--card)" stroke={color} strokeWidth="1.5" />}
    </svg>
  );
}

function donationNote(snapshot: ExplorerSnapshot, donationSites: number, scope: string) {
  const detail = snapshot.forecastDetail;
  if (detail.kind === "unavailable") {
    if (detail.reason === "visitor") return "Donation outlook unavailable for visitors (presenter sign-in required).";
    if (detail.reason === "no_forecast") return "No planning-ready forecast, so no donation outlook.";
    return `Donation outlook unavailable (${detail.code ?? "error"}).`;
  }
  if (donationSites === 0) return scope === "network" ? "No donation forecast for this product." : "No donation forecast for this site and product.";
  return null;
}

/**
 * ForecastBandChart for the Data Explorer: seven forecast days of demand, projected eligible stock and
 * forecast donations for one product (one unit, one axis). A p10–p90 band appears only for one site
 * whose demand series carries model quantiles.
 */
export function NetworkDemandChart({ snapshot, product }: { snapshot: ExplorerSnapshot | null; product: Product | null }) {
  const [scope, setScope] = useState("network");
  const [showTable, setShowTable] = useState(false);
  const tableId = useId();

  if (!snapshot || !product) {
    return (
      <section data-chart="network-demand" aria-labelledby="chart-title" className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 md:p-5">
        <h2 id="chart-title" className="text-base font-semibold">Network Demand Forecast</h2>
        <Skeleton data-loading-slot className="h-[280px] w-full" />
      </section>
    );
  }

  const sites = beneficiaries(snapshot);
  const series = chartSeries(snapshot, product.id, scope);
  const range = formatRange(snapshot.dates);
  const scopeSite = sites.find((site) => site.id === scope) ?? null;
  const scopeLabel = scopeSite ? scopeSite.name : "All beneficiaries";
  const donations = donationNote(snapshot, series.donationSites, scope);
  const hasBand = series.band === "quantiles";
  const data = series.rows.map((row) => ({ ...row, label: formatShortDate(row.date), band: hasBand && row.low !== null && row.high !== null ? [row.low, row.high] : null }));
  const projection = scopeSite ? snapshot.projections[cellKey(scopeSite.id, product.id)] : undefined;
  const methods = runMethods(snapshot);
  const methodLine = scopeSite
    ? projection?.kind === "projected" && projection.method
      ? `Forecast method: ${providerLabel(projection.method.provider)}${projection.method.fallbackUsed ? " (fallback)" : ""}`
      : "Forecast method: no series for this site and product"
    : methods.providers.length + methods.fallbacks.length > 0
      ? `Forecast method: ${methods.providers.map(providerLabel).join(", ") || "none"}${methods.fallbacks.length > 0 ? `; ${methods.fallbacks.length} fallback series` : ""}`
      : null;

  const demandDays = series.rows.filter((row) => row.demand !== null);
  const peak = demandDays.reduce<ChartRow | null>((best, row) => (best === null || (row.demand ?? 0) > (best.demand ?? 0) ? row : best), null);
  const firstStock = series.rows[0]?.eligibleEnd ?? null;
  const lastStock = series.rows[series.rows.length - 1]?.eligibleEnd ?? null;
  const coverage = scopeSite ? null : series.excluded.length > 0
    ? `Sum over ${series.included.length} of ${sites.length} beneficiaries; no series for ${series.excluded.map((site) => site.shortName).join(", ")}.`
    : `Sum over all ${sites.length} beneficiaries.`;

  return (
    <section data-chart="network-demand" aria-labelledby="chart-title" className="flex min-w-0 flex-col gap-3 rounded-xl border border-border bg-card p-4 md:p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 id="chart-title" className="text-base font-semibold">Network Demand Forecast</h2>
          <p className="text-xs text-muted-foreground">{product.name} ({product.unitPlural}) · {scopeLabel} · {range}</p>
        </div>
        <div className="grid gap-1">
          <span id="chart-scope-label" className="text-xs font-medium text-muted-foreground">Chart scope</span>
          <Select value={scope} onValueChange={setScope}>
            <SelectTrigger aria-labelledby="chart-scope-label" className="h-10 w-full bg-card data-[size=default]:h-10 sm:w-[210px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="network">All beneficiaries</SelectItem>
              {sites.map((site) => <SelectItem key={site.id} value={site.id}>{site.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      {snapshot.dates.length === 0 ? (
        <p role="note" className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-sm text-foreground">No projection to chart in this snapshot. Inventory below is still current.</p>
      ) : (
        <>
          <ul aria-label="Chart legend" className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-foreground">
            <li className="flex items-center gap-1.5"><LegendLine dash={DEMAND_DASH} color="var(--pp-forecast)" marker="circle" />Demand forecast ({product.unitPlural} per day)</li>
            <li className="flex items-center gap-1.5"><LegendLine color="var(--pp-teal)" marker="square" />Projected eligible stock at day end, no transfers</li>
            {!donations && <li className="flex items-center gap-1.5"><LegendLine dash={DONATION_DASH} color="var(--pp-ink-muted)" />Forecast donations, not confirmed arrivals</li>}
            {hasBand && <li data-band className="flex items-center gap-1.5"><span aria-hidden="true" className="h-2.5 w-5 rounded-sm bg-pp-forecast/25" />p10–p90 model quantiles, not a calibrated interval</li>}
          </ul>
          <figure className="m-0" aria-label={`${product.name} demand forecast chart, ${product.unitPlural} per day, ${scopeLabel}`}>
            <p className="mb-1 text-xs text-muted-foreground">History not available from the API; the chart starts at the forecast&apos;s first day.</p>
            <div className="h-[240px] md:h-[260px]">
              <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 240 }}>
                <ComposedChart data={data} margin={{ top: 12, right: 12, bottom: 0, left: 4 }} accessibilityLayer={false}>
                  <CartesianGrid stroke="var(--pp-border)" strokeDasharray="2 4" vertical={false} />
                  <XAxis dataKey="label" tick={{ fill: "var(--pp-ink-muted)", fontSize: 12 }} tickLine={false} axisLine={{ stroke: "var(--pp-border)" }} />
                  <YAxis
                    width={64}
                    tick={{ fill: "var(--pp-ink-muted)", fontSize: 12 }}
                    tickLine={false}
                    axisLine={false}
                    allowDecimals={false}
                    label={{ value: `${product.unitPlural} per day`, angle: -90, position: "insideLeft", offset: 0, style: { fill: "var(--pp-ink-muted)", fontSize: 12, textAnchor: "middle" } }}
                  />
                  <ReferenceLine x={data[0]?.label} stroke="var(--pp-ink-muted)" strokeDasharray="3 3" label={{ value: "Forecast starts", position: "insideTopLeft", fill: "var(--pp-ink-muted)", fontSize: 11 }} />
                  {hasBand && <Area dataKey="band" stroke="none" fill="var(--pp-forecast)" fillOpacity={0.18} isAnimationActive={false} connectNulls={false} />}
                  <Line dataKey="demand" name="Demand forecast" stroke="var(--pp-forecast)" strokeWidth={2} strokeDasharray={DEMAND_DASH} dot={{ r: 3, fill: "var(--pp-forecast)", strokeWidth: 0 }} isAnimationActive={false} connectNulls={false} />
                  <Line dataKey="eligibleEnd" name="Eligible stock at day end" stroke="var(--pp-teal)" strokeWidth={2} dot={(props) => <Square {...props} />} isAnimationActive={false} connectNulls={false} />
                  {!donations && <Line dataKey="donations" name="Forecast donations" stroke="var(--pp-ink-muted)" strokeWidth={2} strokeDasharray={DONATION_DASH} dot={false} isAnimationActive={false} connectNulls={false} />}
                  <Tooltip
                    contentStyle={{ borderRadius: 8, borderColor: "var(--pp-border)", fontSize: 12, color: "var(--pp-ink)" }}
                    formatter={(value, name) => [Array.isArray(value) ? `${formatNumber(Number(value[0]))}–${formatNumber(Number(value[1]))} ${product.unitPlural}` : value === null || value === undefined ? "Missing" : formatUnits(Number(value), product), name === "band" ? "p10–p90 model quantiles" : name]}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <figcaption className="mt-2 grid gap-1 text-xs text-foreground">
              <span>
                {demandDays.length === series.rows.length && peak
                  ? `Demand forecast totals ${formatUnits(demandDays.reduce((sum, row) => sum + (row.demand ?? 0), 0), product)} over ${range}; peak ${formatUnits(peak.demand, product)} on ${formatDay(peak.date)}.`
                  : `${demandDays.length} of ${series.rows.length} days have a demand value; missing days are gaps, not zero.`}
                {firstStock !== null && lastStock !== null && ` Eligible stock goes from ${formatUnits(firstStock, product)} at the end of ${formatDay(series.rows[0].date)} to ${formatUnits(lastStock, product)} by ${formatDay(series.rows[series.rows.length - 1].date)}.`}
              </span>
              {coverage && <span className="text-muted-foreground">{coverage}</span>}
              {donations && <span className="text-muted-foreground">{donations}</span>}
              <span className="text-muted-foreground">
                {series.band === "network" && "No uncertainty band: model quantiles do not add across sites. Choose one site to see its band."}
                {series.band === "none" && "Point forecast only; no interval."}
                {series.band === "unknown" && "Interval information unavailable."}
                {hasBand && "Band shows raw model quantiles; it is not a probability of shortage."}
              </span>
              {methodLine && <span className="text-muted-foreground">{methodLine}</span>}
            </figcaption>
          </figure>
          <div>
            <Button type="button" variant="outline" size="sm" aria-expanded={showTable} aria-controls={tableId} onClick={() => setShowTable((open) => !open)}>
              {showTable ? "Hide data table" : "Show data table"}
            </Button>
          </div>
          <div id={tableId} hidden={!showTable} className="overflow-x-auto">
            {showTable && (
              <table className="w-full min-w-[520px] text-left text-sm tabular-nums">
                <caption className="pb-2 text-left text-xs text-muted-foreground">{product.name} ({product.unitPlural}) by local day, {scopeLabel}. Missing means no value in the projection.</caption>
                <thead className="text-xs text-muted-foreground">
                  <tr className="border-b border-border">
                    <th scope="col" className="py-1.5 pr-3 font-medium">Date</th>
                    <th scope="col" className="py-1.5 pr-3 font-medium">Demand forecast ({product.unitPlural})</th>
                    <th scope="col" className="py-1.5 pr-3 font-medium">Eligible stock at day end ({product.unitPlural})</th>
                    {!donations && <th scope="col" className="py-1.5 pr-3 font-medium">Forecast donations ({product.unitPlural})</th>}
                    {hasBand && <th scope="col" className="py-1.5 font-medium">p10–p90 ({product.unitPlural})</th>}
                  </tr>
                </thead>
                <tbody>
                  {series.rows.map((row) => (
                    <tr key={row.date} className="border-b border-border last:border-0">
                      <th scope="row" className="py-1.5 pr-3 font-normal">{formatDay(row.date)}</th>
                      <td className="py-1.5 pr-3">{row.demand === null ? "Missing" : formatNumber(row.demand)}</td>
                      <td className="py-1.5 pr-3">{row.eligibleEnd === null ? "Missing" : formatNumber(row.eligibleEnd)}</td>
                      {!donations && <td className="py-1.5 pr-3">{row.donations === null ? "Missing" : formatNumber(row.donations)}</td>}
                      {hasBand && <td className="py-1.5">{row.low === null || row.high === null ? "Missing" : `${formatNumber(row.low)}–${formatNumber(row.high)}`}</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </section>
  );
}
