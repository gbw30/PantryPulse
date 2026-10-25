"use client";

import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { MotionConfig } from "motion/react";
import { AppShell } from "@/components/shell/app-shell";
import { Button } from "@/components/ui/button";
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { resolveAtlasLayout } from "./atlas-layout";
import { RiskLegend } from "./risk-legend";
import { SchematicMapRenderer, type MapMarker } from "./schematic-map";
import { SiteInspector } from "./site-inspector";
import { SiteList } from "./site-list";
import { StatusGlyph } from "./status-glyph";
import { overviewSourceFor, STATIC_FIXTURE_LABEL } from "./static-fixture";
import { firstDeficit, formatDay, formatRange, formatUnits, markerAccessibleName, roleLabel, STATUS_LABEL, statusDetail, statusFor } from "./status";
import type { BeneficiaryStatus, MarkerStatus, OverviewSnapshot } from "./types";

type LoadState = { status: "loading" } | { status: "ready"; snapshot: OverviewSnapshot } | { status: "error"; message: string };

function useMediaQuery(query: string, serverValue: boolean) {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
    () => serverValue,
  );
}

const DOI_URL = "https://doi.org/10.1111/itor.70252";

export function NetworkAtlas({ statePreview }: { statePreview?: string }) {
  const { source, preview } = overviewSourceFor(statePreview);
  const [load, setLoad] = useState<LoadState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [productId, setProductId] = useState<string | null>(null);
  const [dayIndex, setDayIndex] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [query, setQuery] = useState("");
  const invokerRef = useRef<HTMLElement | null>(null);
  const afterPopoverClose = useRef<"invoker" | "inspector" | "none">("invoker");
  const inspectorHeadingRef = useRef<HTMLHeadingElement>(null);
  const isDesktop = useMediaQuery("(min-width: 1024px)", true);
  const isWide = useMediaQuery("(min-width: 1400px)", true);

  // Load through the adapter. Aborting on change/unmount means a stale response never replaces newer intent.
  useEffect(() => {
    const controller = new AbortController();
    source.load(controller.signal).then(
      (snapshot) => { if (!controller.signal.aborted) setLoad({ status: "ready", snapshot }); },
      (error: unknown) => {
        if (controller.signal.aborted) return;
        setLoad({ status: "error", message: error instanceof Error ? error.message : "The snapshot could not be loaded." });
      },
    );
    return () => controller.abort();
  }, [source, attempt]);

  const snapshot = load.status === "ready" ? load.snapshot : null;
  const product = snapshot ? snapshot.products.find((item) => item.id === productId) ?? snapshot.products[0] : null;
  const positions = useMemo(() => resolveAtlasLayout(snapshot?.sites ?? []), [snapshot]);

  const rows = useMemo(() => {
    if (!snapshot || !product) return [];
    return snapshot.sites.map((site) => {
      const projection = snapshot.projections[site.id]?.[product.id];
      const status = statusFor(projection, dayIndex);
      const detail = statusDetail(projection, product, snapshot.dates);
      return { site, projection, status, detail };
    });
  }, [snapshot, product, dayIndex]);

  const needle = query.trim().toLowerCase();
  const matches = needle ? rows.filter(({ site }) => `${site.name} ${roleLabel(site)}`.toLowerCase().includes(needle)) : rows;
  const selected = rows.find((row) => row.site.id === selectedId) ?? null;
  const inspectorWidth = isWide ? 340 : 300;
  const reserveRight = isDesktop ? inspectorWidth + 32 : 0;
  const dayLabel = snapshot ? formatDay(snapshot.dates[dayIndex]) : null;
  const horizonLabel = snapshot ? `Next 7 days · ${formatRange(snapshot.dates)}` : undefined;

  function select(siteId: string, invoker: HTMLElement) {
    invokerRef.current = invoker;
    afterPopoverClose.current = "invoker";
    setSelectedId(siteId);
    setPopoverOpen(true);
  }

  function clearSelection() {
    setPopoverOpen(false);
    setSelectedId(null);
    invokerRef.current?.focus();
  }

  function inspect() {
    if (isDesktop) {
      afterPopoverClose.current = "inspector";
      setPopoverOpen(false);
      requestAnimationFrame(() => inspectorHeadingRef.current?.focus());
    } else {
      afterPopoverClose.current = "none";
      setPopoverOpen(false);
      setSheetOpen(true);
    }
  }

  function retry() {
    setLoad({ status: "loading" });
    setAttempt((value) => value + 1);
  }

  const markers: MapMarker[] = rows.map(({ site, status, detail }) => ({ site, status, accessibleName: markerAccessibleName(site, status, detail) }));
  const legendContext = product && dayLabel ? `${product.name} (${product.unitPlural}) on ${dayLabel}` : "Waiting for the network snapshot";

  const counts = rows.reduce<Record<BeneficiaryStatus, number>>((acc, row) => {
    if (row.status !== "hub") acc[row.status] += 1;
    return acc;
  }, { shortfall: 0, watch: 0, covered: 0, not_evaluated: 0 });
  const beneficiaryCount = rows.filter((row) => row.site.role !== "HUB").length;

  const inspectorBody = selected && snapshot && product ? (
    <SiteInspector
      key={`${selected.site.id}-${product.id}`}
      site={selected.site}
      product={product}
      projection={selected.projection}
      dates={snapshot.dates}
      dayIndex={dayIndex}
      renderTitle={(title) =>
        isDesktop ? (
          <h2 ref={inspectorHeadingRef} tabIndex={-1} className="text-lg font-semibold tracking-tight outline-none focus-visible:ring-2 focus-visible:ring-ring">{title}</h2>
        ) : (
          <SheetTitle className="text-lg font-semibold tracking-tight">{title}</SheetTitle>
        )
      }
    />
  ) : null;

  return (
    <MotionConfig reducedMotion="user">
      <AppShell
        active="overview"
        horizonLabel={horizonLabel}
        search={{
          value: query,
          onChange: setQuery,
          onSubmit: (invoker) => { if (matches[0]) select(matches[0].site.id, invoker); },
        }}
      >
        <div className="flex flex-1 flex-col gap-4 px-4 py-4 md:px-6 md:py-5 lg:h-[calc(100svh-3.5rem)] lg:min-h-[620px]">
          <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div className="min-w-0">
              <p className="font-condensed text-xs font-semibold tracking-[0.16em] text-muted-foreground uppercase">Network intelligence</p>
              <h1 className="text-[26px] leading-tight font-semibold tracking-tight md:text-[28px]">Network Atlas</h1>
              <p className="text-sm text-muted-foreground">Where each site runs short, by product and local day, across the simulated network.</p>
              {horizonLabel && <p className="mt-1 text-xs text-foreground md:hidden">{horizonLabel}</p>}
            </div>
            <div className="grid gap-2 sm:flex sm:items-end">
              <div className="grid gap-1">
                <span id="atlas-product-label" className="text-xs font-medium text-muted-foreground">Product</span>
                <Select value={product?.id ?? ""} onValueChange={(value) => setProductId(value)} disabled={!snapshot}>
                  <SelectTrigger aria-labelledby="atlas-product-label" className="h-10 w-full bg-card data-[size=default]:h-10 sm:w-[236px]">
                    <SelectValue placeholder="Loading products…" />
                  </SelectTrigger>
                  <SelectContent>
                    {snapshot?.products.map((item) => <SelectItem key={item.id} value={item.id}>{item.name} ({item.unitPlural})</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-1">
                <span id="atlas-day-label" className="text-xs font-medium text-muted-foreground">Local day</span>
                <Select value={String(dayIndex)} onValueChange={(value) => setDayIndex(Number(value))} disabled={!snapshot}>
                  <SelectTrigger aria-labelledby="atlas-day-label" className="h-10 w-full bg-card data-[size=default]:h-10 sm:w-[160px]">
                    <SelectValue placeholder="Loading dates…" />
                  </SelectTrigger>
                  <SelectContent>
                    {snapshot?.dates.map((date, index) => <SelectItem key={date} value={String(index)}>{formatDay(date)}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </header>

          {preview && (
            <p role="note" className="rounded-lg border border-dashed border-border bg-card px-3 py-2 text-xs text-foreground">
              Design-state preview: <strong>{preview}</strong>. Open /overview without <code>?state=</code> for the static fixture.
            </p>
          )}
          {load.status === "error" && (
            <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-pp-danger bg-card px-3 py-2 text-sm text-foreground">
              <StatusGlyph status="shortfall" />
              <span className="min-w-0 flex-1"><strong>Network snapshot unavailable.</strong> {load.message} No site data is shown.</span>
              <Button variant="outline" size="sm" onClick={retry}>Retry</Button>
            </div>
          )}
          {snapshot?.emptyReason && (
            <p role="status" className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground">
              <StatusGlyph status="not_evaluated" />
              {snapshot.emptyReason}
            </p>
          )}

          {snapshot && <SiteList items={matches} selectedId={selectedId} query={query} onSelect={select} />}

          <section aria-label="Network map" className="relative flex min-h-0 flex-col gap-3 md:block md:min-h-[400px] md:flex-1">
            <RiskLegend
              context={legendContext}
              className="order-2 md:absolute md:top-4 md:left-4 md:z-10"
              style={isDesktop ? { right: reserveRight + 16 } : undefined}
            />
            {load.status === "loading" && (
              <div role="status" className="relative grid h-[55svh] place-items-center overflow-hidden rounded-2xl border border-border bg-pp-surface-muted md:h-full">
                <Skeleton className="absolute inset-6 rounded-xl bg-pp-border/50" />
                <span className="relative rounded-md bg-card px-3 py-1.5 text-sm text-foreground">Loading network snapshot…</span>
              </div>
            )}
            {load.status === "error" && (
              <div className="grid h-[55svh] place-items-center rounded-2xl border border-dashed border-border bg-pp-surface-muted p-6 text-center text-sm text-muted-foreground md:h-full">
                The map stays empty until a snapshot loads.
              </div>
            )}
            {snapshot && product && (
              <SchematicMapRenderer
                className="h-[55svh] md:h-full"
                markers={markers}
                positions={positions}
                selectedId={selectedId}
                onSelect={select}
                reserveRight={reserveRight}
                reserveTop={isDesktop ? 48 : 0}
                renderSelection={(point) => selected && (
                  <Popover open={popoverOpen} onOpenChange={(open) => { if (!open) setPopoverOpen(false); }}>
                    <PopoverAnchor asChild>
                      <span aria-hidden="true" className="pointer-events-none absolute size-px" style={{ left: point.left, top: point.top }} />
                    </PopoverAnchor>
                    <PopoverContent
                      side="right"
                      align="start"
                      sideOffset={30}
                      collisionPadding={12}
                      aria-label={selected.site.name}
                      className="w-72 motion-reduce:animate-none"
                      onCloseAutoFocus={(event) => {
                        event.preventDefault();
                        if (afterPopoverClose.current === "invoker") invokerRef.current?.focus();
                      }}
                    >
                      <PopoverSummary row={selected} product={product} snapshot={snapshot} dayIndex={dayIndex} onInspect={inspect} />
                    </PopoverContent>
                  </Popover>
                )}
              />
            )}
            {snapshot && product && isDesktop && (
              <aside
                aria-label="Site inspector"
                data-testid="site-inspector"
                className="absolute top-4 right-4 bottom-4 z-10 overflow-y-auto rounded-xl border border-border bg-card p-4 shadow-sm"
                style={{ width: inspectorWidth }}
                onKeyDown={(event) => {
                  if (event.key === "Escape" && selected) {
                    event.preventDefault();
                    clearSelection();
                  }
                }}
              >
                {inspectorBody ?? (
                  <div className="grid gap-3 text-sm">
                    <h2 className="text-base font-semibold">Site inspector</h2>
                    <p className="text-muted-foreground">Select a site on the map or in the site list to see its stock, first deficit and outlook.</p>
                    <dl className="grid gap-1.5 rounded-lg bg-muted px-3 py-2.5">
                      <dt className="text-xs text-muted-foreground">{beneficiaryCount} pantries, {legendContext}</dt>
                      {(Object.keys(counts) as BeneficiaryStatus[]).map((status) => (
                        <dd key={status} className="flex items-center justify-between gap-2">
                          <span className="inline-flex items-center gap-2"><StatusGlyph status={status} />{STATUS_LABEL[status]}</span>
                          <span className="font-medium tabular-nums">{counts[status]}</span>
                        </dd>
                      ))}
                    </dl>
                  </div>
                )}
              </aside>
            )}
          </section>

          {!isDesktop && (
            <Sheet open={sheetOpen && !!inspectorBody} onOpenChange={setSheetOpen}>
              <SheetContent
                side="bottom"
                data-testid="site-inspector"
                className="max-h-[85svh] overflow-y-auto rounded-t-2xl p-4 pt-5"
                onCloseAutoFocus={(event) => {
                  event.preventDefault();
                  invokerRef.current?.focus();
                }}
              >
                <SheetDescription className="sr-only">Stock, first deficit and outlook for the selected site.</SheetDescription>
                {inspectorBody}
              </SheetContent>
            </Sheet>
          )}

          <footer className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">{snapshot?.provenance.label ?? STATIC_FIXTURE_LABEL}</span>
            {snapshot && <span>Fixture {snapshot.provenance.fixtureId}; sites and products from {snapshot.provenance.sourceDataset}</span>}
            {snapshot && <span>Local dates {formatRange(snapshot.dates)} ({snapshot.timezone})</span>}
            <span>
              Allocation engines are not implemented yet. Planned method: EGP-PI-inspired allocation, after{" "}
              <a className="text-foreground underline underline-offset-2 outline-none focus-visible:ring-2 focus-visible:ring-ring" href={DOI_URL}>Rampazo et al., published Sep 11, 2026</a>.
            </span>
          </footer>
        </div>
      </AppShell>
    </MotionConfig>
  );
}

type Row = { site: OverviewSnapshot["sites"][number]; projection: OverviewSnapshot["projections"][string][string] | undefined; status: MarkerStatus; detail: string };

function PopoverSummary({ row, product, snapshot, dayIndex, onInspect }: { row: Row; product: OverviewSnapshot["products"][number]; snapshot: OverviewSnapshot; dayIndex: number; onInspect: () => void }) {
  const deficit = firstDeficit(row.projection);
  const day = formatDay(snapshot.dates[dayIndex]);
  let deficitLine: string;
  if (row.status === "hub") deficitLine = "Hub has no demand forecast.";
  else if (row.projection?.kind === "insufficient_data") deficitLine = "Insufficient data: no projection.";
  else if (row.status === "not_evaluated") deficitLine = "Not evaluated: no projection.";
  else deficitLine = deficit ? `First deficit ${formatDay(snapshot.dates[deficit.dayIndex])} · ${formatUnits(deficit.unmetUnits, product)} unmet` : "No projected deficit";

  return (
    <div className="grid gap-2.5">
      <div>
        <p className="text-[15px] font-semibold">{row.site.name}</p>
        <p className="text-xs text-muted-foreground first-letter:uppercase">{roleLabel(row.site)}</p>
      </div>
      <p className="inline-flex items-center gap-2 text-sm">
        <StatusGlyph status={row.status} />
        <span><strong className="font-semibold">{STATUS_LABEL[row.status]}</strong>{row.status !== "hub" && <> on {day}</>}</span>
      </p>
      <p className="text-xs text-muted-foreground">{product.name} ({product.unitPlural})</p>
      <p className="text-sm">{deficitLine}</p>
      <Button onClick={onInspect} className="w-full">
        Inspect site
      </Button>
    </div>
  );
}
