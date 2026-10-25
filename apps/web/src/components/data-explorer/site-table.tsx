"use client";

import { useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { formatDay, formatPercent, formatRange, formatUnits, providerLabel, STATUS_LABEL } from "./format";
import { StatusChip } from "./marks";
import { beneficiaries, cellKey, hubs, seriesTotals, siteStatus } from "./metrics";
import type { ExplorerSnapshot, Product, Quantity, SeriesProjection } from "./types";

type SortKey = "site" | "fill" | "deficit" | "unmet";
type Sort = { key: SortKey; direction: "ascending" | "descending" } | null;

const HEAD = "px-3 py-2 text-left text-xs font-medium whitespace-nowrap text-muted-foreground";
const CELL = "px-3 py-2 align-top tabular-nums whitespace-nowrap";

/** Seven-day unmet sparkline; gaps for missing days. Decorative: the row says the same in text. */
function Trend({ values }: { values: Quantity[] }) {
  const known = values.filter((value): value is number => value !== null);
  const max = Math.max(1, ...known);
  const step = 64 / Math.max(1, values.length - 1);
  const segments: string[][] = [[]];
  values.forEach((value, index) => {
    if (value === null) { segments.push([]); return; }
    segments[segments.length - 1].push(`${(index * step + 2).toFixed(1)},${(18 - (value / max) * 14).toFixed(1)}`);
  });
  return (
    <svg width="68" height="20" aria-hidden="true">
      <line x1="2" y1="18" x2="66" y2="18" stroke="var(--pp-border)" strokeWidth="1" />
      {segments.filter((points) => points.length > 0).map((points, index) => (
        points.length === 1
          ? <circle key={index} cx={points[0].split(",")[0]} cy={points[0].split(",")[1]} r="1.5" fill="var(--pp-ink-muted)" />
          : <polyline key={index} points={points.join(" ")} fill="none" stroke="var(--pp-ink-muted)" strokeWidth="1.5" />
      ))}
    </svg>
  );
}

function unmetValues(projection: SeriesProjection | undefined): Quantity[] {
  return projection?.kind === "projected" ? projection.days.map((day) => day?.unmet ?? null) : [];
}

/** SitePerformanceTable: all six beneficiaries for the selected product, plus hubs labelled as sources. */
export function SitePerformanceTable({ snapshot, product }: { snapshot: ExplorerSnapshot | null; product: Product | null }) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>(null);

  if (!snapshot || !product) {
    return (
      <section data-site-table aria-labelledby="site-table-title" className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 md:p-5">
        <h2 id="site-table-title" className="text-base font-semibold">Site Performance</h2>
        <Skeleton data-loading-slot className="h-[240px] w-full" />
      </section>
    );
  }

  const range = formatRange(snapshot.dates);
  const needle = query.trim().toLowerCase();
  const rows = beneficiaries(snapshot).map((site) => {
    const projection = snapshot.projections[cellKey(site.id, product.id)];
    const totals = seriesTotals(projection);
    const status = siteStatus(projection);
    const fill = totals?.complete && totals.target > 0 ? totals.served / totals.target : null;
    return { site, projection, totals, status, fill };
  }).filter((row) => !needle || row.site.name.toLowerCase().includes(needle));
  const hubRows = hubs(snapshot).filter((site) => !needle || `${site.name} hub source`.toLowerCase().includes(needle));

  if (sort) {
    const factor = sort.direction === "ascending" ? 1 : -1;
    const value = (row: (typeof rows)[number]) => {
      if (sort.key === "site") return row.site.name;
      if (sort.key === "fill") return row.fill ?? Infinity;
      if (sort.key === "deficit") return row.totals?.firstDeficit ?? Infinity;
      return row.totals?.complete ? row.totals.unmet : -Infinity;
    };
    rows.sort((a, b) => {
      const left = value(a);
      const right = value(b);
      return (typeof left === "string" ? left.localeCompare(right as string) : (left as number) - (right as number)) * factor;
    });
  }

  function sortBy(key: SortKey) {
    setSort((current) => (current?.key === key ? { key, direction: current.direction === "ascending" ? "descending" : "ascending" } : { key, direction: "ascending" }));
  }

  const header = (key: SortKey, label: string) => {
    const active = sort?.key === key;
    const Icon = !active ? ArrowUpDown : sort.direction === "ascending" ? ArrowUp : ArrowDown;
    return (
      <th scope="col" aria-sort={active ? sort.direction : undefined} className={HEAD}>
        <button type="button" onClick={() => sortBy(key)} className="inline-flex min-h-8 items-center gap-1 rounded-sm font-medium outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
          {label}<Icon className="size-3.5" aria-hidden="true" />
        </button>
      </th>
    );
  };

  return (
    <section data-site-table aria-labelledby="site-table-title" className="flex min-w-0 flex-col gap-3 rounded-xl border border-border bg-card p-4 md:p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <h2 id="site-table-title" className="text-base font-semibold">Site Performance</h2>
          <p className="text-xs text-muted-foreground">{product.name} ({product.unitPlural}), {range}. Projection assumes no transfers. Region and households are not in the data, so those columns are omitted.</p>
        </div>
        <div className="relative w-full sm:w-[240px]">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input type="search" aria-label="Search sites" placeholder="Search sites…" value={query} onChange={(event) => setQuery(event.target.value)} className="h-10 bg-background pl-9" />
        </div>
      </div>
      <p className="text-xs text-muted-foreground md:hidden">Scroll sideways for more columns.</p>
      <div role="region" aria-label={`Site performance table, ${product.name}`} tabIndex={0} className="overflow-x-auto rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring">
        <table className="w-full min-w-[860px] text-sm text-foreground">
          <caption className="sr-only">Site performance for {product.name} ({product.unitPlural}), {range}</caption>
          <thead className="border-b border-border bg-muted/50">
            <tr>
              {header("site", "Site")}
              <th scope="col" className={HEAD}>Status</th>
              {header("fill", "Predicted fill rate")}
              <th scope="col" className={HEAD}>Served / target</th>
              {header("deficit", "First deficit")}
              {header("unmet", "Unmet (7 days)")}
              <th scope="col" className={HEAD}>Unmet trend</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && hubRows.length === 0 && (
              <tr><td colSpan={7} className="px-3 py-4 text-center text-sm">No site matches “{query}”.</td></tr>
            )}
            {rows.map(({ site, projection, totals, status, fill }) => {
              const method = projection?.kind === "projected" ? projection.method : null;
              const note = projection?.kind === "not_evaluated"
                ? projection.reason
                : totals && !totals.complete ? `${totals.missingDays} ${totals.missingDays === 1 ? "day" : "days"} missing from the projection` : null;
              const unmet = unmetValues(projection);
              return (
                <tr key={site.id} data-site-row data-role="BENEFICIARY" className="border-b border-border last:border-0">
                  <th scope="row" className={cn(CELL, "text-left font-medium whitespace-normal")}>
                    <span className="block">{site.name}</span>
                    {method?.fallbackUsed && <span className="block text-xs font-normal text-muted-foreground">Fallback forecast: {providerLabel(method.provider)}</span>}
                    {note && <span className="block max-w-[260px] text-xs font-normal text-muted-foreground">{note}</span>}
                  </th>
                  <td className={CELL}><StatusChip status={status}>{STATUS_LABEL[status]}</StatusChip></td>
                  <td className={CELL}>{fill === null || !totals ? "—" : formatPercent(totals.served, totals.target)}</td>
                  <td className={CELL}>{totals?.complete ? `${totals.served.toLocaleString("en-US")} / ${formatUnits(totals.target, product)}` : "—"}</td>
                  <td className={CELL}>{totals?.firstDeficit !== null && totals?.firstDeficit !== undefined ? formatDay(snapshot.dates[totals.firstDeficit]) : totals?.complete ? "None in 7 days" : "—"}</td>
                  <td className={CELL}>{totals?.complete ? formatUnits(totals.unmet, product) : "—"}</td>
                  <td className={CELL}>
                    {unmet.length > 0 ? (
                      <>
                        <Trend values={unmet} />
                        <span className="sr-only">Unmet by day: {unmet.map((value) => (value === null ? "missing" : value)).join(", ")} {product.unitPlural}</span>
                      </>
                    ) : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
          {hubRows.length > 0 && (
            <tbody className="border-t-2 border-border">
              <tr><th scope="rowgroup" colSpan={7} className="px-3 pt-3 pb-1 text-left text-xs font-medium text-muted-foreground">Sources (not demand sites)</th></tr>
              {hubRows.map((site) => {
                const cell = snapshot.inventory[cellKey(site.id, product.id)];
                return (
                  <tr key={site.id} data-site-row data-role="HUB">
                    <th scope="row" className={cn(CELL, "text-left font-medium")}>{site.name}</th>
                    <td className={CELL}><StatusChip status="hub" /></td>
                    <td colSpan={5} className={cn(CELL, "text-muted-foreground")}>
                      <span className="text-foreground">{cell ? `${formatUnits(cell.usable, product)} eligible now` : "No inventory row"}</span> · no demand target (source)
                    </td>
                  </tr>
                );
              })}
            </tbody>
          )}
        </table>
      </div>
    </section>
  );
}
