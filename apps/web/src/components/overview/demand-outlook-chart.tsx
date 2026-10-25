import { useId, useState } from "react";
import { useReducedMotion } from "motion/react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button } from "@/components/ui/button";
import { formatDay, formatRange, formatShortDate, formatUnits } from "./status";
import type { BeneficiaryProjection, HubProjection, Product } from "./types";

type Props = {
  projection: BeneficiaryProjection | HubProjection;
  product: Product;
  dates: string[];
  /** Caption source, e.g. "Static fixture outlook" or "Live projection (SEASONAL_NAIVE)". */
  sourceNote: string;
};

function sum(values: number[]) {
  return values.reduce((total, value) => total + value, 0);
}

/**
 * Demand outlook for one site and one product, against the donation outlook when the data has one
 * (static fixture) or against projected served units when it does not (live shortage projection:
 * demand and physical eligible stock only). Series are never added to stock.
 */
export function DemandOutlookChart({ projection, product, dates, sourceNote }: Props) {
  const [showTable, setShowTable] = useState(false);
  const tableId = useId();
  // Lines draw in on mount (the inspector remounts the chart per site and product).
  const animateLines = !useReducedMotion();
  const isHub = projection.kind === "hub";
  const donations = projection.donationOutlook;
  const servedMode = donations === null && !isHub;
  const second = servedMode ? { key: "served", label: "Projected served" } : { key: "donation", label: "Donation outlook" };
  const data = dates.map((date, index) => ({
    day: formatShortDate(date),
    demand: isHub ? undefined : projection.demandOutlook[index],
    donation: donations ? donations[index] : undefined,
    served: projection.kind === "projected" ? projection.servedUnits[index] : undefined,
  }));
  const range = formatRange(dates);
  const summary = (() => {
    if (projection.kind === "hub") {
      return donations
        ? `Donation outlook totals ${formatUnits(sum(donations), product)} over ${range}. The hub has no demand forecast.`
        : "Donation outlook: Not in this projection. The hub has no demand forecast.";
    }
    const unmet = sum(projection.unmetUnits);
    const first = projection.unmetUnits.findIndex((value) => value > 0);
    const unmetText = unmet > 0 ? ` Projected unmet: ${formatUnits(unmet, product)}, first on ${formatDay(dates[first])}.` : " No projected unmet units.";
    const secondText = donations ? `donation outlook ${formatUnits(sum(donations), product)}` : `projected served ${formatUnits(sum(projection.servedUnits), product)}`;
    const donationText = donations ? "" : " Donation outlook: Not in this projection.";
    return `Demand outlook totals ${formatUnits(sum(projection.demandOutlook), product)} and ${secondText} over ${range}.${donationText}${unmetText}`;
  })();

  return (
    <div className="grid gap-2">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        {!isHub && (
          <span className="inline-flex items-center gap-1.5"><svg width="18" height="6" aria-hidden="true"><line x1="0" y1="3" x2="18" y2="3" stroke="var(--pp-forecast)" strokeWidth="2.5" /></svg>Demand outlook</span>
        )}
        <span className="inline-flex items-center gap-1.5"><svg width="18" height="6" aria-hidden="true"><line x1="0" y1="3" x2="18" y2="3" stroke="var(--pp-teal)" strokeWidth="2.5" strokeDasharray="4 3" /></svg>{second.label}</span>
      </div>
      <figure className="m-0" aria-label={`${product.name} outlook chart, ${product.unitPlural} per day`}>
        <div className="h-40 w-full" aria-hidden="true">
          <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 300, height: 160 }}>
            <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }} accessibilityLayer={false}>
              <CartesianGrid vertical={false} stroke="var(--pp-border)" />
              <XAxis dataKey="day" tickLine={false} axisLine={{ stroke: "var(--pp-border)" }} tick={{ fill: "var(--pp-ink-muted)", fontSize: 11 }} interval="preserveStartEnd" minTickGap={8} />
              <YAxis tickLine={false} axisLine={false} width={44} tick={{ fill: "var(--pp-ink-muted)", fontSize: 11 }} allowDecimals={false} />
              {!isHub && <Line dataKey="demand" name="Demand outlook" type="linear" stroke="var(--pp-forecast)" strokeWidth={2.5} dot={{ r: 2.5, fill: "var(--pp-forecast)", strokeWidth: 0 }} isAnimationActive={animateLines} animationDuration={600} />}
              <Line dataKey={second.key} name={second.label} type="linear" stroke="var(--pp-teal)" strokeWidth={2.5} strokeDasharray="5 4" dot={false} isAnimationActive={animateLines} animationDuration={600} />
              <Tooltip formatter={(value) => `${Number(value).toLocaleString("en-US")} ${product.unitPlural}`} contentStyle={{ borderRadius: 8, borderColor: "var(--pp-border)", fontSize: 12 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <figcaption className="mt-1 text-[11px] text-muted-foreground">
          Daily {product.unitPlural}, {range}. {sourceNote}; no interval available.{servedMode ? " Donations and confirmed supply are not in this projection." : ""}
        </figcaption>
      </figure>
      <p className="text-sm">{summary}</p>
      <Button variant="outline" size="sm" className="justify-self-start" aria-expanded={showTable} aria-controls={tableId} onClick={() => setShowTable((value) => !value)}>
        {showTable ? "Hide data table" : "Show data table"}
      </Button>
      <div id={tableId} hidden={!showTable} className="overflow-x-auto rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" role="region" aria-label={`${product.name} daily outlook table`} tabIndex={showTable ? 0 : -1}>
        {showTable && (
          <table className="w-full table-fixed border-collapse text-left text-xs tabular-nums">
            {/* Short visible headers keep the table inside a 300px inspector; units sit in the caption and each header's accessible name. */}
            <caption className="caption-top pb-1 text-left text-[11px] text-muted-foreground">
              All values in {product.unitPlural} per day, {range}{servedMode ? ". Donation outlook: not in this projection" : ""}
            </caption>
            <thead>
              <tr className="border-b border-border text-muted-foreground">
                <th scope="col" className={isHub ? "w-1/2 py-1 font-medium" : servedMode ? "w-[22%] py-1 font-medium" : "w-[17%] py-1 font-medium"}><span data-col-label>Date</span></th>
                {!isHub && <th scope="col" className={servedMode ? "w-[26%] py-1 text-right font-medium" : "w-[20%] py-1 text-right font-medium"}><span data-col-label>Demand</span><span className="sr-only"> outlook ({product.unitPlural})</span></th>}
                {donations && <th scope="col" className={isHub ? "py-1 text-right font-medium" : "w-[25%] py-1 text-right font-medium"}><span data-col-label>Donation</span><span className="sr-only"> outlook ({product.unitPlural})</span></th>}
                {!isHub && <th scope="col" className={servedMode ? "w-[26%] py-1 text-right font-medium" : "w-[19%] py-1 text-right font-medium"}><span data-col-label>Served</span><span className="sr-only"> (projected, {product.unitPlural})</span></th>}
                {!isHub && <th scope="col" className={servedMode ? "w-[26%] py-1 text-right font-medium" : "w-[19%] py-1 text-right font-medium"}><span data-col-label>Unmet</span><span className="sr-only"> (projected, {product.unitPlural})</span></th>}
              </tr>
            </thead>
            <tbody>
              {dates.map((date, index) => (
                <tr key={date} className="border-b border-border/70">
                  <th scope="row" className="py-1 font-normal whitespace-nowrap"><span className="sr-only">{formatDay(date).split(",")[0]}, </span>{formatShortDate(date)}</th>
                  {projection.kind === "projected" && <td className="py-1 text-right">{projection.demandOutlook[index].toLocaleString("en-US")}</td>}
                  {donations && <td className="py-1 text-right">{donations[index].toLocaleString("en-US")}</td>}
                  {projection.kind === "projected" && <td className="py-1 text-right">{projection.servedUnits[index].toLocaleString("en-US")}</td>}
                  {projection.kind === "projected" && <td className={projection.unmetUnits[index] > 0 ? "py-1 text-right font-semibold" : "py-1 text-right"}>{projection.unmetUnits[index].toLocaleString("en-US")}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
