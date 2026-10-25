"use client";

import { Gauge, Trash2, Users } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { FlipCard } from "./flip-card";
import { formatPercent, formatRange, formatUnits } from "./format";
import { expiredOnHand, itemsAtRisk, networkFill, sitesAtRisk } from "./metrics";
import type { ExplorerSnapshot, Product } from "./types";

const CARD_HEIGHT = "h-[220px] lg:h-[184px]";
const VALUE = "text-[26px] leading-tight font-semibold tracking-tight tabular-nums text-foreground";
const DETAIL = "text-xs leading-snug text-muted-foreground";

function KpiCard({ name, title, icon: Icon, children }: { name: string; title: string; icon: React.ComponentType<{ className?: string }>; children: React.ReactNode }) {
  return (
    <section data-kpi={name} aria-labelledby={`kpi-${name}`} className={cn("flex flex-col gap-1.5 overflow-hidden rounded-xl border border-border bg-card p-4", CARD_HEIGHT)}>
      <h2 id={`kpi-${name}`} className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        {title}
      </h2>
      {children}
    </section>
  );
}

function Loading() {
  return (
    <div data-loading-slot className="grid gap-2 pt-1">
      <Skeleton className="h-7 w-24" />
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-2/3" />
    </div>
  );
}

/** "Unavailable — reason": the value and why it is unavailable, read as one sentence. */
function Unavailable({ reason }: { reason: string }) {
  return (
    <p className="leading-tight">
      <span className={VALUE}>Unavailable</span>{" "}
      <span className="block text-xs text-muted-foreground">— {reason}</span>
    </p>
  );
}

/**
 * Four fixed-size KPI cards: Households Served, Predicted Fill Rate, the Items ↔ Sites at Risk flip and
 * Food Waste Rate. Every quantity is for one product and names its unit and window.
 */
export function KpiRow({ snapshot, product }: { snapshot: ExplorerSnapshot | null; product: Product | null }) {
  const ready = snapshot && product ? { snapshot, product } : null;
  const range = ready ? formatRange(ready.snapshot.dates) : "";
  const evaluated = ready && ready.snapshot.dates.length > 0;

  const fill = ready ? networkFill(ready.snapshot, ready.product.id) : null;
  const items = ready ? itemsAtRisk(ready.snapshot) : null;
  const sites = ready ? sitesAtRisk(ready.snapshot, ready.product.id) : null;

  const riskFace = (count: number, total: number, noun: string, notEvaluated: number, criterion: string) =>
    !ready ? <Loading /> : !evaluated || notEvaluated === total ? (
      <div className="grid gap-1 pt-1">
        <p className={VALUE}>Not evaluated</p>
        <p className={DETAIL}>No projection in this snapshot.</p>
      </div>
    ) : (
      <div className="grid gap-1 pt-1">
        <p><span className={VALUE}>{count}</span> <span className="text-sm text-foreground">of {total} {noun}</span></p>
        <p className={DETAIL}>{criterion}</p>
        {notEvaluated > 0 && <p className="text-xs font-medium text-foreground">{notEvaluated} not evaluated</p>}
      </div>
    );

  return (
    <section aria-label="Key measures" className="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
      <KpiCard name="households" title="Households Served" icon={Users}>
        {!ready ? <Loading /> : <Unavailable reason="household data not supplied; never derived from meal or bottle counts." />}
      </KpiCard>

      <KpiCard name="fill-rate" title="Predicted Fill Rate" icon={Gauge}>
        {!ready || !fill ? <Loading /> : !evaluated || fill.evaluated === 0 ? (
          <div className="grid gap-1">
            <p className={VALUE}>Not evaluated</p>
            <p className={DETAIL}>{ready.product.name}: no complete projection in this snapshot.</p>
          </div>
        ) : (
          <div className="grid gap-1">
            <p className={VALUE}>{formatPercent(fill.served, fill.target)}</p>
            <p className="text-xs text-foreground">{fill.served.toLocaleString("en-US")} of {formatUnits(fill.target, ready.product)} served</p>
            <p className={DETAIL}>{range} · {fill.evaluated} of {fill.total} beneficiaries evaluated</p>
          </div>
        )}
      </KpiCard>

      <FlipCard
        name="risk"
        rootProps={{ "data-kpi": "risk" }}
        className={CARD_HEIGHT}
        faceClassName="gap-1.5 p-4"
        control="bottom"
        duration={0.3}
        disabled={!ready}
        front={{
          title: "Items at Risk",
          content: riskFace(items?.atRisk ?? 0, items?.total ?? 0, "products", items?.notEvaluated ?? 0, `Products with ≥1 projected unmet day at any beneficiary, ${range}.`),
        }}
        back={{
          title: "Sites at Risk",
          content: riskFace(sites?.atRisk ?? 0, sites?.total ?? 0, "beneficiaries", sites?.notEvaluated ?? 0, ready ? `≥1 day with unmet ${ready.product.unitPlural}, ${range}.` : ""),
        }}
      />

      <KpiCard name="waste" title="Food Waste Rate" icon={Trash2}>
        {!ready ? <Loading /> : (
          <div className="grid gap-1.5">
            <Unavailable reason="waste accounting not supplied" />
            <div className="text-xs text-foreground">
              <p className="text-muted-foreground">Expired on hand now (evidence, not a rate):</p>
              {ready.snapshot.inventoryRows === 0 ? <p>No inventory rows.</p> : (
                <ul className="grid gap-0.5">
                  {ready.snapshot.products.map((item) => {
                    const expired = expiredOnHand(ready.snapshot, item.id);
                    return <li key={item.id} className="tabular-nums">{item.name}: {expired.rows === 0 ? "no inventory rows" : formatUnits(expired.units, item)}</li>;
                  })}
                </ul>
              )}
            </div>
          </div>
        )}
      </KpiCard>
    </section>
  );
}
