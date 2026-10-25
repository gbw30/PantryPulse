"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { formatDay, formatRange, formatUnits, STATUS_LABEL } from "./format";
import { ExplorerTabLink } from "./header";
import { StatusChip } from "./marks";
import { beneficiaries, cellKey, hubs, seriesTotals, siteStatus } from "./metrics";
import { explorerTab } from "./tabs";
import type { ExplorerSnapshot, InventoryCell, LotTally, Product, Site } from "./types";

function lotLine(label: string, tally: LotTally, product: Product) {
  if (tally.lots === 0) return `${label}: none`;
  return `${label}: ${tally.lots} ${tally.lots === 1 ? "lot" : "lots"} · ${formatUnits(tally.units, product)}`;
}

function Lots({ cell, product }: { cell: InventoryCell | undefined; product: Product }) {
  if (!cell) return <p className="text-xs text-foreground">No inventory row for this site and product.</p>;
  return (
    <ul aria-label={`${product.name} lots`} className="grid gap-0.5 text-xs text-foreground tabular-nums">
      <li>{lotLine("Eligible", cell.eligible, product)}</li>
      <li>{lotLine("Held", cell.held, product)}</li>
      <li>{lotLine("Expired", cell.expired, product)}</li>
      {cell.otherExcluded.lots > 0 && <li>{lotLine("Other excluded", cell.otherExcluded, product)}</li>}
    </ul>
  );
}

/** SiteRiskCard: one beneficiary, every product, each with its own unit, deficit and lot status. */
function SiteRiskCard({ snapshot, site, productId }: { snapshot: ExplorerSnapshot; site: Site; productId: string | null }) {
  const range = formatRange(snapshot.dates);
  return (
    <article data-site-card data-role="BENEFICIARY" aria-labelledby={`card-${site.id}`} className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4">
      <div>
        <h2 id={`card-${site.id}`} className="text-base font-semibold">{site.name}</h2>
        <p className="text-xs text-muted-foreground">Beneficiary pantry · {range} · latest forecast projection</p>
      </div>
      {snapshot.products.map((product) => {
        const projection = snapshot.projections[cellKey(site.id, product.id)];
        const totals = seriesTotals(projection);
        const status = siteStatus(projection);
        const cell = snapshot.inventory[cellKey(site.id, product.id)];
        return (
          <section key={product.id} data-product-panel aria-label={`${product.name} at ${site.name}`} className="grid gap-1.5 rounded-lg border border-border px-3 py-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold">{product.name} <span className="font-normal text-muted-foreground">({product.unitPlural})</span></h3>
              <StatusChip status={status}>{STATUS_LABEL[status]}</StatusChip>
            </div>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs tabular-nums">
              <dt className="text-muted-foreground">Eligible now</dt>
              <dd className="text-foreground">{cell ? formatUnits(cell.usable, product) : "No inventory row"}</dd>
              <dt className="text-muted-foreground">First deficit</dt>
              <dd className="text-foreground">
                {totals?.firstDeficit !== null && totals?.firstDeficit !== undefined
                  ? `${formatDay(snapshot.dates[totals.firstDeficit])} · ${formatUnits(totals.firstDeficitUnits, product)} unmet`
                  : totals?.complete ? `None, ${range}` : projection?.kind === "not_evaluated" ? `Not evaluated: ${projection.reason}` : "Not evaluated: a day is missing"}
              </dd>
            </dl>
            <Lots cell={cell} product={product} />
          </section>
        );
      })}
      <p className="text-xs text-muted-foreground">Incoming: confirmed arrivals and transfers are not in this projection.</p>
      <ExplorerTabLink tab={explorerTab("inventory")} productId={productId} className="h-9 self-start text-xs" />
    </article>
  );
}

function HubCard({ snapshot, site }: { snapshot: ExplorerSnapshot; site: Site }) {
  return (
    <article data-site-card data-role="HUB" aria-labelledby={`card-${site.id}`} className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id={`card-${site.id}`} className="text-base font-semibold">{site.name}</h2>
        <StatusChip status="hub" />
      </div>
      <p className="text-xs text-muted-foreground">Distribution hub: a source with no demand target. Stock shown now; no plan is applied.</p>
      {snapshot.products.map((product) => {
        const cell = snapshot.inventory[cellKey(site.id, product.id)];
        return (
          <section key={product.id} data-product-panel aria-label={`${product.name} at ${site.name}`} className="grid gap-1.5 rounded-lg border border-border px-3 py-2.5">
            <h3 className="text-sm font-semibold">{product.name} <span className="font-normal text-muted-foreground">({product.unitPlural})</span></h3>
            <p className="text-xs text-foreground">Eligible now: {cell ? formatUnits(cell.usable, product) : "No inventory row"}</p>
            <Lots cell={cell} product={product} />
          </section>
        );
      })}
    </article>
  );
}

/** Operations Board: six beneficiary cards × every product, then hubs as sources. */
export function OperationsBoard({ snapshot, productId }: { snapshot: ExplorerSnapshot | null; productId: string | null }) {
  if (!snapshot) {
    return (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {[0, 1, 2].map((index) => <Skeleton key={index} data-loading-slot className="h-[320px] w-full rounded-xl" />)}
      </div>
    );
  }
  return (
    <section aria-label="Operations Board" className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {beneficiaries(snapshot).map((site) => <SiteRiskCard key={site.id} snapshot={snapshot} site={site} productId={productId} />)}
      {hubs(snapshot).map((site) => <HubCard key={site.id} snapshot={snapshot} site={site} />)}
    </section>
  );
}
