import { useId, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button } from "@/components/ui/button";
import { formatDay, formatRange, formatShortDate, formatUnits } from "./status";
import type { BeneficiaryProjection, HubProjection, Product } from "./types";

type Props = { projection: BeneficiaryProjection | HubProjection; product: Product; dates: string[] };

function sum(values: number[]) {
  return values.reduce((total, value) => total + value, 0);
}

/** Demand vs donation outlook for one site and one product. Two separate series; never added to stock. */
export function DemandOutlookChart({ projection, product, dates }: Props) {
  const [showTable, setShowTable] = useState(false);
  const tableId = useId();
  const isHub = projection.kind === "hub";
  const data = dates.map((date, index) => ({
    day: formatShortDate(date),
    demand: isHub ? undefined : projection.demandOutlook[index],
    donation: projection.donationOutlook[index],
  }));
  const range = formatRange(dates);
  const summary = isHub
    ? `Donation outlook totals ${formatUnits(sum(projection.donationOutlook), product)} over ${range}. The hub has no demand forecast.`
    : (() => {
        const unmet = sum(projection.unmetUnits);
        const first = projection.unmetUnits.findIndex((value) => value > 0);
        const unmetText = unmet > 0 ? ` Projected unmet: ${formatUnits(unmet, product)}, first on ${formatDay(dates[first])}.` : " No projected unmet units.";
        return `Demand outlook totals ${formatUnits(sum(projection.demandOutlook), product)} and donation outlook ${formatUnits(sum(projection.donationOutlook), product)} over ${range}.${unmetText}`;
      })();

  return (
    <div className="grid gap-2">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        {!isHub && (
          <span className="inline-flex items-center gap-1.5"><svg width="18" height="6" aria-hidden="true"><line x1="0" y1="3" x2="18" y2="3" stroke="var(--pp-forecast)" strokeWidth="2.5" /></svg>Demand outlook</span>
        )}
        <span className="inline-flex items-center gap-1.5"><svg width="18" height="6" aria-hidden="true"><line x1="0" y1="3" x2="18" y2="3" stroke="var(--pp-teal)" strokeWidth="2.5" strokeDasharray="4 3" /></svg>Donation outlook</span>
      </div>
      <figure className="m-0" aria-label={`${product.name} outlook chart, ${product.unitPlural} per day`}>
        <div className="h-40 w-full" aria-hidden="true">
          <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 300, height: 160 }}>
            <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }} accessibilityLayer={false}>
              <CartesianGrid vertical={false} stroke="var(--pp-border)" />
              <XAxis dataKey="day" tickLine={false} axisLine={{ stroke: "var(--pp-border)" }} tick={{ fill: "var(--pp-ink-muted)", fontSize: 11 }} interval="preserveStartEnd" minTickGap={8} />
              <YAxis tickLine={false} axisLine={false} width={44} tick={{ fill: "var(--pp-ink-muted)", fontSize: 11 }} allowDecimals={false} />
              {!isHub && <Line dataKey="demand" name="Demand outlook" type="linear" stroke="var(--pp-forecast)" strokeWidth={2.5} dot={{ r: 2.5, fill: "var(--pp-forecast)", strokeWidth: 0 }} isAnimationActive={false} />}
              <Line dataKey="donation" name="Donation outlook" type="linear" stroke="var(--pp-teal)" strokeWidth={2.5} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
              <Tooltip formatter={(value) => `${Number(value).toLocaleString("en-US")} ${product.unitPlural}`} contentStyle={{ borderRadius: 8, borderColor: "var(--pp-border)", fontSize: 12 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <figcaption className="mt-1 text-[11px] text-muted-foreground">
          Daily {product.unitPlural}, {range}. Static fixture outlook; no interval available.
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
            <caption className="caption-top pb-1 text-left text-[11px] text-muted-foreground">All values in {product.unitPlural} per day, {range}</caption>
            <thead>
              <tr className="border-b border-border text-muted-foreground">
                <th scope="col" className="w-[22%] py-1 font-medium">Date</th>
                {!isHub && <th scope="col" className="py-1 text-right font-medium">Demand<span className="sr-only"> outlook ({product.unitPlural})</span></th>}
                <th scope="col" className="py-1 text-right font-medium">Donation<span className="sr-only"> outlook ({product.unitPlural})</span></th>
                {!isHub && <th scope="col" className="py-1 text-right font-medium">Served<span className="sr-only">, projected ({product.unitPlural})</span></th>}
                {!isHub && <th scope="col" className="py-1 text-right font-medium">Unmet<span className="sr-only">, projected ({product.unitPlural})</span></th>}
              </tr>
            </thead>
            <tbody>
              {dates.map((date, index) => (
                <tr key={date} className="border-b border-border/70">
                  <th scope="row" className="py-1 font-normal whitespace-nowrap"><span className="sr-only">{formatDay(date).split(",")[0]}, </span>{formatShortDate(date)}</th>
                  {!isHub && <td className="py-1 text-right">{projection.demandOutlook[index].toLocaleString("en-US")}</td>}
                  <td className="py-1 text-right">{projection.donationOutlook[index].toLocaleString("en-US")}</td>
                  {!isHub && <td className="py-1 text-right">{projection.servedUnits[index].toLocaleString("en-US")}</td>}
                  {!isHub && <td className={projection.unmetUnits[index] > 0 ? "py-1 text-right font-semibold" : "py-1 text-right"}>{projection.unmetUnits[index].toLocaleString("en-US")}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
