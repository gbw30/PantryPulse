"use client";

import { useState } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { formatDay, formatRange, formatShortDate, formatUnits } from "./format";
import { StatusGlyph } from "./marks";
import { beneficiaries, cellKey } from "./metrics";
import type { ExplorerSnapshot, Product, ProjectedDay, SeriesProjection, Site } from "./types";

type CellState = "shortfall" | "covered" | "zero" | "missing" | "not_evaluated";

function cellState(projection: SeriesProjection | undefined, index: number): { state: CellState; day: ProjectedDay | null } {
  if (!projection || projection.kind !== "projected") return { state: "not_evaluated", day: null };
  const day = projection.days[index];
  if (!day || day.target === null || day.served === null || day.unmet === null) return { state: "missing", day: null };
  if (day.unmet > 0) return { state: "shortfall", day };
  if (day.target === 0) return { state: "zero", day };
  return { state: "covered", day };
}

const STATE_STYLE: Record<CellState, string> = {
  shortfall: "border-pp-danger/60 bg-pp-danger/10",
  covered: "border-pp-teal/40 bg-pp-teal-soft",
  zero: "border-border bg-card",
  missing: "border-dashed border-pp-neutral bg-[repeating-linear-gradient(135deg,transparent_0_5px,var(--pp-surface-muted)_5px_7px)]",
  not_evaluated: "border-dashed border-pp-neutral bg-card",
};

function shortText(state: CellState, day: ProjectedDay | null) {
  if (state === "shortfall" && day) return `${day.unmet!.toLocaleString("en-US")} unmet`;
  if (state === "zero") return "0 target";
  if (state === "covered") return "Covered";
  if (state === "missing") return "Missing";
  return "Not evaluated";
}

function fullText(state: CellState, day: ProjectedDay | null, product: Product) {
  if (state === "shortfall" && day) return `Shortfall, ${formatUnits(day.unmet, product)} unmet`;
  if (state === "zero") return `observed zero target, 0 ${product.unitPlural}`;
  if (state === "covered" && day) return `Covered, ${formatUnits(day.served, product)} served`;
  if (state === "missing") return "Missing from the projection";
  return "Not evaluated";
}

const LEGEND: { state: CellState; label: string }[] = [
  { state: "shortfall", label: "Shortfall: unmet units that day" },
  { state: "covered", label: "Covered: target fully served" },
  { state: "zero", label: "0 target: observed zero demand" },
  { state: "missing", label: "Missing: no value in the series" },
  { state: "not_evaluated", label: "Not evaluated: no series" },
];

/** ShortageTimeline as a site × seven-local-date grid; each cell opens its detail below. */
export function SevenDayPulse({ snapshot, product }: { snapshot: ExplorerSnapshot | null; product: Product | null }) {
  const [selected, setSelected] = useState<{ siteId: string; index: number } | null>(null);

  if (!snapshot || !product) {
    return (
      <section aria-labelledby="pulse-title" className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 md:p-5">
        <h2 id="pulse-title" className="text-base font-semibold">Seven-Day Pulse</h2>
        <Skeleton data-loading-slot className="h-[320px] w-full" />
      </section>
    );
  }

  const sites = beneficiaries(snapshot);
  const range = formatRange(snapshot.dates);
  const chosenSite: Site | undefined = selected ? sites.find((site) => site.id === selected.siteId) : undefined;
  const chosen = chosenSite && selected ? { site: chosenSite, date: snapshot.dates[selected.index], ...cellState(snapshot.projections[cellKey(chosenSite.id, product.id)], selected.index), projection: snapshot.projections[cellKey(chosenSite.id, product.id)] } : null;

  return (
    <section aria-labelledby="pulse-title" className="flex min-w-0 flex-col gap-3 rounded-xl border border-border bg-card p-4 md:p-5">
      <div>
        <h2 id="pulse-title" className="text-base font-semibold">Seven-Day Pulse</h2>
        <p className="text-xs text-muted-foreground">Projected coverage by beneficiary and local day, {product.name} ({product.unitPlural}), {range}. Physical stock only, no transfers; not a probability.</p>
      </div>
      <ul aria-label="Cell legend" className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-foreground">
        {LEGEND.map((item) => (
          <li key={item.state} className="flex items-center gap-1.5">
            <span aria-hidden="true" className={cn("size-3.5 rounded-sm border", STATE_STYLE[item.state])} />
            {item.label}
          </li>
        ))}
      </ul>
      {snapshot.dates.length === 0 ? (
        <p role="note" className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-sm text-foreground">No projection in this snapshot, so there is no seven-day grid.</p>
      ) : (
        <>
          <p className="text-xs text-muted-foreground md:hidden">Scroll sideways for all seven days.</p>
          <div role="region" aria-label={`Seven-Day Pulse grid, ${product.name}`} tabIndex={0} className="overflow-x-auto rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <table className="w-full min-w-[760px] border-separate border-spacing-1 text-sm">
              <caption className="sr-only">Seven-Day Pulse grid: rows are beneficiaries, columns are local days. Each cell is a button that shows its detail.</caption>
              <thead>
                <tr>
                  <th scope="col" className="w-[150px] px-1 text-left text-xs font-medium text-muted-foreground">Site</th>
                  {snapshot.dates.map((date) => <th key={date} scope="col" className="px-1 text-left text-xs font-medium text-muted-foreground">{formatDay(date)}</th>)}
                </tr>
              </thead>
              <tbody>
                {sites.map((site) => {
                  const projection = snapshot.projections[cellKey(site.id, product.id)];
                  return (
                    <tr key={site.id}>
                      <th scope="row" className="px-1 text-left text-sm font-medium text-foreground">{site.name}</th>
                      {snapshot.dates.map((date, index) => {
                        const { state, day } = cellState(projection, index);
                        const isSelected = selected?.siteId === site.id && selected.index === index;
                        return (
                          <td key={date} className="p-0">
                            <button
                              type="button"
                              data-pulse-cell
                              data-cell-state={state}
                              aria-pressed={isSelected}
                              aria-label={`${site.name}, ${formatDay(date)}: ${fullText(state, day, product)}`}
                              onClick={() => setSelected({ siteId: site.id, index })}
                              className={cn("flex min-h-11 w-full items-center gap-1.5 rounded-md border px-2 py-1.5 text-left text-xs text-foreground tabular-nums outline-none focus-visible:ring-2 focus-visible:ring-ring", STATE_STYLE[state], isSelected && "ring-2 ring-foreground")}
                            >
                              {state === "shortfall" && <StatusGlyph status="shortfall" size={11} />}
                              {state === "covered" && <StatusGlyph status="covered" size={11} />}
                              {state === "not_evaluated" && <StatusGlyph status="not_evaluated" size={11} />}
                              <span aria-hidden="true">{shortText(state, day)}</span>
                            </button>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
      <section data-pulse-detail aria-live="polite" aria-label="Selected day detail" className="rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground">
        {!chosen ? (
          <p className="text-muted-foreground">Select a cell to see its target, eligible stock, service and unmet units.</p>
        ) : (
          <>
            <h3 className="font-semibold">{chosen.site.name} · {formatDay(chosen.date)}</h3>
            {chosen.state === "missing" ? (
              <p className="mt-1">Missing from the projection: this day has no value in the site&apos;s series, so nothing is shown in its place.</p>
            ) : chosen.state === "not_evaluated" || !chosen.day ? (
              <p className="mt-1">Not evaluated. {chosen.projection?.kind === "not_evaluated" ? chosen.projection.reason : ""}</p>
            ) : (
              <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5 tabular-nums sm:grid-cols-[auto_1fr_auto_1fr]">
                <dt className="text-muted-foreground">Target (forecast-derived)</dt><dd>{formatUnits(chosen.day.target, product)}</dd>
                <dt className="text-muted-foreground">Projected served</dt><dd>{formatUnits(chosen.day.served, product)}</dd>
                <dt className="text-muted-foreground">Unmet</dt><dd>{formatUnits(chosen.day.unmet, product)}</dd>
                <dt className="text-muted-foreground">Eligible stock at day end</dt><dd>{formatUnits(chosen.day.eligibleEnd, product)}</dd>
              </dl>
            )}
            <p className="mt-1 text-xs text-muted-foreground">Confirmed arrivals are not in this projection. {formatShortDate(chosen.date)} is a local date.</p>
          </>
        )}
      </section>
    </section>
  );
}
