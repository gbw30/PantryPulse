import { Route } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DemandOutlookChart } from "./demand-outlook-chart";
import { ProvenancePill } from "./provenance-pill";
import { StatusGlyph } from "./status-glyph";
import { formatDay, formatUnits, nextDeficitLine, roleLabel, STATUS_LABEL, statusFor } from "./status";
import type { Product, Site, SiteProductProjection } from "./types";

type Props = {
  site: Site;
  product: Product;
  projection: SiteProductProjection | undefined;
  dates: string[];
  dayIndex: number;
  /** Renders the heading so the desktop card and the mobile sheet can supply their own element. */
  renderTitle: (title: string) => React.ReactNode;
};

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-0.5 border-b border-border py-1.5 last:border-b-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium text-foreground">{children}</dd>
    </div>
  );
}

function routesNote(status: ReturnType<typeof statusFor>) {
  if (status === "shortfall" || status === "watch") return "A deficit here has no proposed transfer.";
  if (status === "covered") return "No projected deficit, so no transfer is needed in this view.";
  if (status === "not_evaluated") return "No projection, so transfers can't be assessed.";
  return "";
}

function NetworkFacts({ product, projection, dates, dayIndex }: Omit<Props, "renderTitle">) {
  const status = statusFor(projection, dayIndex);
  const day = formatDay(dates[dayIndex]);
  const end = formatDay(dates[dates.length - 1]);
  const statusLine = status === "hub" ? "Hub · source (no beneficiary status)" : `${STATUS_LABEL[status]} on ${day}`;

  return (
    <>
    <dl className="grid">
      <Fact label="Status">
        <span className="inline-flex items-center gap-1.5"><StatusGlyph status={status} />{statusLine}</span>
      </Fact>
      {(!projection || projection.kind === "not_evaluated") && (
        <Fact label="Projection">Not evaluated: {projection?.reason ?? "no projection for this product."}</Fact>
      )}
      {projection?.kind === "insufficient_data" && (
        <>
          <Fact label="Projection">Insufficient data. {projection.reason}</Fact>
          <Fact label="Eligible stock now">{projection.eligibleStockNow === null ? "Unknown" : formatUnits(projection.eligibleStockNow, product)}</Fact>
        </>
      )}
      {(projection?.kind === "projected" || projection?.kind === "hub") && (
        <Fact label={projection.kind === "hub" ? "Eligible stock, no transfers assumed" : "Eligible stock"}>
          {formatUnits(projection.eligibleStockNow, product)} now → {formatUnits(projection.eligibleStockAtHorizonEnd, product)} by {end}
        </Fact>
      )}
      {projection?.kind === "projected" && (() => {
        const target = projection.targetUnits[dayIndex];
        return (
          <>
            <Fact label={`Served / target on ${day}`}>
              {target === 0 ? "N/A (target is 0)" : `${projection.servedUnits[dayIndex].toLocaleString("en-US")} / ${formatUnits(target, product)}`}
            </Fact>
            <Fact label={`Next deficit from ${day}`}>{nextDeficitLine(projection, product, dates, dayIndex)}</Fact>
          </>
        );
      })()}
      {projection?.kind === "hub" && <Fact label="Demand">Not applicable: the hub has no demand forecast.</Fact>}
      {(projection?.kind === "projected" || projection?.kind === "hub") && (
        <Fact label="Eligible lots expiring by horizon end">
          {projection.expiringLots.count === 0 ? "None" : `${projection.expiringLots.count} ${projection.expiringLots.count === 1 ? "lot" : "lots"} · ${formatUnits(projection.expiringLots.units, product)}`}
        </Fact>
      )}
    </dl>
      <div className="mt-2 flex items-start gap-2 rounded-lg bg-muted px-2.5 py-2 text-xs">
        <Route className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
        <span><span className="font-medium">Routes hidden — no saved plan</span><span className="block text-muted-foreground">Transfers appear only after an allocation plan is saved. {routesNote(status)}</span></span>
      </div>
    </>
  );
}

/** SiteInspector: Network and Demand tabs for one site, product and local day. */
export function SiteInspector(props: Props) {
  const { site, product, projection, dates, dayIndex, renderTitle } = props;
  const hasOutlook = projection?.kind === "projected" || projection?.kind === "hub";

  return (
    <div className="grid gap-3">
      {/* Sticky so site, product/unit, day and provenance stay visible while the tab content scrolls. */}
      <div className="sticky -top-4 z-10 -mx-4 -mt-4 grid gap-1 border-b border-border bg-card px-4 pt-4 pb-3">
        {renderTitle(site.name)}
        <p className="text-xs text-muted-foreground first-letter:uppercase">{roleLabel(site)}</p>
        <p className="text-xs text-foreground">
          {product.name} · {product.unitPlural} · {formatDay(dates[dayIndex])}
        </p>
        <ProvenancePill className="justify-self-start">Static fixture · simulated</ProvenancePill>
      </div>
      <Tabs defaultValue="network">
        <TabsList className="w-full">
          <TabsTrigger value="network" className="text-muted-foreground">Network</TabsTrigger>
          <TabsTrigger value="demand" className="text-muted-foreground">Demand</TabsTrigger>
        </TabsList>
        <TabsContent value="network">
          <NetworkFacts site={site} product={product} projection={projection} dates={dates} dayIndex={dayIndex} />
        </TabsContent>
        <TabsContent value="demand">
          {hasOutlook ? (
            <DemandOutlookChart projection={projection} product={product} dates={dates} />
          ) : (
            <p className="py-2 text-sm">No outlook for {product.name.toLowerCase()} at this site: {projection?.kind === "insufficient_data" ? "insufficient data." : "not evaluated."}</p>
          )}
        </TabsContent>
      </Tabs>
      <div className="grid gap-1">
        <Button variant="outline" disabled aria-describedby={`${site.id}-detail-note`}>Go to Site Details</Button>
        <p id={`${site.id}-detail-note`} className="text-center text-xs text-muted-foreground">Site detail not built yet</p>
      </div>
    </div>
  );
}
