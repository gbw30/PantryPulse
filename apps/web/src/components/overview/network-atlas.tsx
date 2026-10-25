"use client";

import { useEffect, useEffectEvent, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { AnimatePresence, motion, MotionConfig, useReducedMotion } from "motion/react";
import Link from "next/link";
import { AppShell } from "@/components/shell/app-shell";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { resolveAtlasLayout, withSavedPositions } from "./atlas-layout";
import { PRESS, SPRING } from "./atlas-motion";
import { isCustomized, resetLayout, saveNodePosition, savePanelOffset, useSavedLayout, type PanelId, type PanelOffset } from "./layout-store";
import { PanelGrip, PanelGripHint } from "./panel-grip";
import { RiskLegend } from "./risk-legend";
import { SchematicMapRenderer, type MapMarker } from "./schematic-map";
import { SelectionCard } from "./selection-card";
import { SiteInspector } from "./site-inspector";
import { SiteList } from "./site-list";
import { StatusGlyph } from "./status-glyph";
import { FallbackNote, fallbackNameFragment, methodSummary, providerLabel } from "./forecast-method";
import { LiveNoticeBanner, NOTICE_LINK, NoticeMeta } from "./live-notice";
import { LIVE_LABEL } from "./live-source";
import { ProvenancePill } from "./provenance-pill";
import { overviewSourceFor } from "./sources";
import { STATIC_FIXTURE_LABEL } from "./static-fixture";
import { formatDay, formatInstant, formatRange, formatUnits, markerAccessibleName, nextDeficitFrom, nextDeficitLine, roleLabel, STATUS_LABEL, statusDetail, statusFor, statusLine } from "./status";
import type { BeneficiaryStatus, ForecastMethod, MarkerStatus, OverviewSnapshot } from "./types";

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

// Header pill per source: where the numbers on screen come from.
const SOURCE_PILL = {
  visitor: "Static fixture · visitor view",
  unavailable: "Static fixture · live data unavailable",
  preview: "Static fixture · design preview",
} as const;

/** Tracks whether a scroll container has content below its visible area (drives the "More below" cue). */
function useOverflowBelow(element: HTMLElement | null, contentKey: string) {
  const [below, setBelow] = useState(false);
  useEffect(() => {
    if (!element) return;
    const update = () => setBelow(element.scrollTop + element.clientHeight < element.scrollHeight - 4);
    const observer = new ResizeObserver(update);
    observer.observe(element);
    for (const child of element.children) observer.observe(child);
    element.addEventListener("scroll", update, { passive: true });
    return () => {
      observer.disconnect();
      element.removeEventListener("scroll", update);
    };
  }, [element, contentKey]);
  return below;
}

// Zero-height sticky anchor with an absolutely positioned overlay: showing or hiding the cue never
// changes the scroll height, so content cannot jump (e.g. under a pointer) when it toggles at the bottom.
function ScrollCue({ className }: { className?: string }) {
  return (
    <div aria-hidden="true" className={`pointer-events-none sticky -bottom-4 z-20 h-0 ${className ?? ""}`}>
      <div className="absolute inset-x-0 bottom-0 flex h-10 items-end justify-center bg-linear-to-t from-card via-card/90 to-transparent pb-1">
        <span className="rounded-full border border-border bg-card px-2 py-0.5 text-[11px] text-foreground">More below</span>
      </div>
    </div>
  );
}

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
  const invokerSiteRef = useRef<string | null>(null);
  const [inspectorPanel, setInspectorPanel] = useState<HTMLElement | null>(null);
  const [sheetPanel, setSheetPanel] = useState<HTMLElement | null>(null);
  const afterPopoverClose = useRef<"invoker" | "inspector" | "none">("invoker");
  const inspectorHeadingRef = useRef<HTMLHeadingElement | null>(null);
  // While the old inspector body exits (AnimatePresence), its heading unmounts after the new one mounts;
  // only clear the ref if it still points at the heading being removed.
  const setInspectorHeading = (element: HTMLHeadingElement | null) => {
    if (element) inspectorHeadingRef.current = element;
    return () => {
      if (inspectorHeadingRef.current === element) inspectorHeadingRef.current = null;
    };
  };
  // Per-browser layout (PP-52): dragged nodes and panels. A panel's live drag offset is held here and
  // saved when the drag or key step ends.
  const layout = useSavedLayout();
  const [livePanel, setLivePanel] = useState<{ id: PanelId; offset: PanelOffset } | null>(null);
  const [liftedPanel, setLiftedPanel] = useState<PanelId | null>(null);
  const [legend, setLegend] = useState<HTMLDivElement | null>(null);
  const [legendHeight, setLegendHeight] = useState(0);
  const isDesktop = useMediaQuery("(min-width: 1024px)", true);
  const reduced = useReducedMotion();
  const isWide = useMediaQuery("(min-width: 1400px)", true);

  // Load through the adapter. Aborting on change/unmount means a stale response never replaces newer intent.
  useEffect(() => {
    const controller = new AbortController();
    source.load(controller.signal).then(
      (snapshot) => {
        if (controller.signal.aborted) return;
        setLoad({ status: "ready", snapshot });
        // Live and fixture snapshots can have different horizons; keep the selected day in range.
        setDayIndex((current) => Math.min(current, Math.max(0, snapshot.dates.length - 1)));
      },
      (error: unknown) => {
        if (controller.signal.aborted) return;
        setLoad({ status: "error", message: error instanceof Error ? error.message : "The snapshot could not be loaded." });
      },
    );
    return () => controller.abort();
  }, [source, attempt]);

  // Markers start below the floating legend, whose height depends on width and wrapping.
  useEffect(() => {
    if (!legend) return;
    const observer = new ResizeObserver(([entry]) => setLegendHeight(entry.borderBoxSize?.[0]?.blockSize ?? entry.contentRect.height));
    observer.observe(legend);
    return () => observer.disconnect();
  }, [legend]);

  const snapshot = load.status === "ready" ? load.snapshot : null;
  const product = snapshot ? snapshot.products.find((item) => item.id === productId) ?? snapshot.products[0] : null;
  const positions = useMemo(() => withSavedPositions(resolveAtlasLayout(snapshot?.sites ?? []), layout.nodes), [snapshot, layout.nodes]);
  // Panels move only on desktop; at narrow widths the legend, sheet and docked card keep their places.
  const offsetOf = (id: PanelId): PanelOffset => (!isDesktop ? { dx: 0, dy: 0 } : livePanel?.id === id ? livePanel.offset : layout.panels[id] ?? { dx: 0, dy: 0 });
  const panelGrip = (id: PanelId, label: string, element: () => HTMLElement | null, orientation?: "horizontal") => (
    <PanelGrip
      label={label}
      panel={element}
      offset={offsetOf(id)}
      orientation={orientation}
      onLift={(lifted) => setLiftedPanel(lifted ? id : null)}
      onChange={(offset, phase) => {
        if (phase === "move") {
          setLivePanel({ id, offset });
          return;
        }
        setLivePanel(null);
        savePanelOffset(id, offset);
      }}
    />
  );
  const translateOf = (id: PanelId) => {
    const { dx, dy } = offsetOf(id);
    return dx === 0 && dy === 0 ? undefined : `${dx}px ${dy}px`;
  };

  const rows = useMemo(() => {
    if (!snapshot || !product) return [];
    return snapshot.sites.map((site) => {
      const projection = snapshot.projections[site.id]?.[product.id];
      const status = statusFor(projection, dayIndex);
      const detail = statusDetail(projection, product, snapshot.dates, dayIndex);
      const method = projection?.kind === "projected" ? projection.method : undefined;
      return { site, projection, status, detail, method, fallbackNote: fallbackNameFragment(method), statusLine: statusLine(status, projection, dayIndex, snapshot.dates) };
    });
  }, [snapshot, product, dayIndex]);

  const needle = query.trim().toLowerCase();
  const matches = needle ? rows.filter(({ site }) => `${site.name} ${roleLabel(site)}`.toLowerCase().includes(needle)) : rows;
  const selected = rows.find((row) => row.site.id === selectedId) ?? null;
  // Products match by name or unit ("water", "bottle", "meal"); there is no region data to search.
  const productMatches = needle && snapshot ? snapshot.products.filter((item) => [item.name, item.unit, item.unitPlural].some((text) => text.toLowerCase().includes(needle))) : [];
  const inspectorWidth = isWide ? 340 : 300;
  const reserveRight = isDesktop ? inspectorWidth + 32 : 0;
  const dayLabel = snapshot ? formatDay(snapshot.dates[dayIndex]) : null;
  const horizonLabel = snapshot ? (snapshot.dates.length > 1 ? `Next ${snapshot.dates.length} days · ${formatRange(snapshot.dates)}` : `Inventory · ${formatRange(snapshot.dates)}`) : undefined;
  const live = snapshot?.source.kind === "live" ? snapshot.source : null;
  const fallback = snapshot?.fallback ?? null;
  const sourceLabel = live ? LIVE_LABEL : fallback ? SOURCE_PILL[fallback.kind] : SOURCE_PILL.preview;
  const sourceTone: "live" | "fixture" | "degraded" = live ? "live" : fallback?.kind === "unavailable" ? "degraded" : "fixture";
  const selectedMethod = selected?.method;
  const methodText = selectedMethod ? `${providerLabel(selectedMethod.provider)}${selectedMethod.fallbackUsed ? " (fallback)" : ""}` : null;
  const provenance = live
    ? {
        label: sourceLabel,
        tone: sourceTone,
        detail: `${selectedMethod ? `Forecast method: ${providerLabel(selectedMethod.provider)} · ` : ""}observed ${formatInstant(live.observedAt, snapshot?.timezone ?? "UTC")}`,
        chartNote: `Live projection${methodText ? `, ${methodText}` : ""}`,
        method: selectedMethod,
      }
    : { label: sourceLabel, tone: sourceTone, chartNote: "Static fixture outlook" };
  const methodLine = live && snapshot ? methodSummary(live.methods, snapshot.sites, snapshot.products) : null;

  // Return focus to the control that opened the selection. If it was remounted (e.g. while other
  // routes compile in development), fall back to the site's marker found by its stable id.
  function restoreFocus() {
    const invoker = invokerRef.current;
    if (invoker?.isConnected) {
      invoker.focus();
      return;
    }
    const siteId = invokerSiteRef.current;
    if (siteId) document.querySelector<HTMLElement>(`[data-site-id="${siteId}"]`)?.focus();
  }

  function select(siteId: string, invoker: HTMLElement) {
    invokerRef.current = invoker;
    invokerSiteRef.current = siteId;
    afterPopoverClose.current = "invoker";
    setSelectedId(siteId);
    setPopoverOpen(true);
    // The map can sit partly below the fold (notices above it, short viewports); bring all of it, and so the
    // docked card, into view. A no-op when it is already visible.
    document.querySelector("[data-atlas-map]")?.scrollIntoView({ block: "nearest" });
  }

  function clearSelection() {
    setPopoverOpen(false);
    setSelectedId(null);
    restoreFocus();
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

  // While a site is selected and no popover/sheet is open (those handle Escape themselves), Escape
  // anywhere clears the selection. The inspector's own onKeyDown only worked while focus was inside
  // it, so a remounted or blurred control left Escape unhandled.
  const onDocumentEscape = useEffectEvent((event: KeyboardEvent) => {
    if (event.key !== "Escape" || event.defaultPrevented) return;
    const target = event.target instanceof Element ? event.target : null;
    if (target?.closest('[role="listbox"], [role="menu"], [data-radix-popper-content-wrapper]')) return;
    event.preventDefault();
    clearSelection();
  });
  useEffect(() => {
    if (!selectedId || popoverOpen || sheetOpen) return;
    document.addEventListener("keydown", onDocumentEscape);
    return () => document.removeEventListener("keydown", onDocumentEscape);
  }, [selectedId, popoverOpen, sheetOpen]);

  function chooseProductFromSearch(productIdToShow: string) {
    setProductId(productIdToShow);
    setQuery("");
  }

  function retry() {
    setLoad({ status: "loading" });
    setAttempt((value) => value + 1);
  }

  const contentKey = `${selectedId ?? "none"}-${product?.id ?? ""}-${dayIndex}`;
  const inspectorBelow = useOverflowBelow(inspectorPanel, contentKey);
  const sheetBelow = useOverflowBelow(sheetPanel, `${contentKey}-${sheetOpen}`);
  const markers: MapMarker[] = rows.map(({ site, status, detail, fallbackNote, statusLine: line }) => ({ site, status, statusLine: line, accessibleName: markerAccessibleName(site, status, detail, fallbackNote) }));
  const deficits = rows
    .map((row) => ({ row, next: nextDeficitFrom(row.projection, dayIndex) }))
    .filter((item): item is { row: (typeof rows)[number]; next: { dayIndex: number; unmetUnits: number } } => item.next !== null)
    .sort((a, b) => a.next.dayIndex - b.next.dayIndex || b.next.unmetUnits - a.next.unmetUnits);

  // Focus returns to the marker, which outlives the list button that triggered the selection.
  function selectFromList(siteId: string, button: HTMLElement) {
    const markerButton = document.querySelector<HTMLElement>(`[data-site-id="${siteId}"]`);
    select(siteId, markerButton ?? button);
  }
  const legendContext = product && dayLabel ? `${product.name} (${product.unitPlural}) on ${dayLabel}` : "Waiting for the network snapshot";

  const counts = rows.reduce<Record<BeneficiaryStatus, number>>((acc, row) => {
    if (row.status !== "hub") acc[row.status] += 1;
    return acc;
  }, { shortfall: 0, watch: 0, covered: 0, not_evaluated: 0 });
  const beneficiaryCount = rows.filter((row) => row.site.role !== "HUB").length;

  // Inspector content crossfades when the site or product changes (keyed remount).
  const inspectorBody = selected && snapshot && product ? (
    <motion.div
      key={`${selected.site.id}-${product.id}`}
      initial={reduced ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={reduced ? { opacity: 0, transition: { duration: 0 } } : { opacity: 0, transition: { duration: 0.12 } }}
      transition={SPRING}
    >
    <SiteInspector
      site={selected.site}
      product={product}
      projection={selected.projection}
      dates={snapshot.dates}
      dayIndex={dayIndex}
      provenance={provenance}
      renderTitle={(title) =>
        isDesktop ? (
          <h2 ref={setInspectorHeading} tabIndex={-1} className="text-lg font-semibold tracking-tight outline-none focus-visible:ring-2 focus-visible:ring-ring">{title}</h2>
        ) : (
          <SheetTitle className="text-lg font-semibold tracking-tight">{title}</SheetTitle>
        )
      }
    />
    </motion.div>
  ) : null;

  return (
    <MotionConfig reducedMotion="user">
      <AppShell
        active="overview"
        horizonLabel={horizonLabel}
        search={{
          value: query,
          onChange: setQuery,
          onSubmit: (invoker) => {
            if (matches[0]) select(matches[0].site.id, invoker);
            else if (productMatches[0]) chooseProductFromSearch(productMatches[0].id);
          },
        }}
      >
        <div className="flex flex-1 flex-col gap-3 px-4 pt-3 pb-4 md:gap-4 md:px-6 md:py-5 lg:min-h-[calc(100svh-3.5rem)] lg:gap-6">
          <header data-atlas-header className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between md:gap-3">
            <div className="min-w-0">
              <p className="font-condensed text-xs font-semibold tracking-[0.16em] text-muted-foreground uppercase">Network intelligence</p>
              <h1 className="text-[26px] leading-tight font-semibold tracking-tight md:text-[28px]">Network Atlas</h1>
              <p className="text-sm text-muted-foreground">Where each site runs short, by product and local day, across the simulated network.</p>
              {snapshot && (
                // Says which source is showing; on narrow layouts it shares the line with the horizon.
                <p data-overview-source={snapshot.source.kind} className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-foreground">
                  {horizonLabel && <span className="md:hidden">{horizonLabel} ·</span>}
                  <ProvenancePill tone={sourceTone}>{sourceLabel}</ProvenancePill>
                  {live && <span className="text-muted-foreground">Presenter data, observed {formatInstant(live.observedAt, snapshot.timezone)}</span>}
                </p>
              )}
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
          {fallback?.kind === "visitor" && (
            // Compact below md: the source pill already says "Static fixture · visitor view", so the long
            // wording stays available to screen readers without pushing the map below the first viewport.
            <div data-live-notice="visitor" role="status" className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border border-border bg-card px-3 py-1.5 text-sm text-foreground md:py-2">
              <span><strong className="font-semibold">Sign in for live data.</strong><span className="max-md:sr-only"> You are viewing the static design fixture.</span>{" "}
                <Link className={NOTICE_LINK} href="/optimization">Sign in<span className="max-md:sr-only"> through the optimization workspace</span></Link></span>
            </div>
          )}
          {fallback?.kind === "unavailable" && (
            // A failure, so an alert; plain sentence first and the code as secondary text. Retry stays beside
            // the text (no wrap) and the second sentence is visually hidden below md, where the source pill
            // already says "live data unavailable", so the map keeps its first-viewport markers.
            <div role="alert" className="flex items-center gap-x-3 rounded-lg border border-pp-danger bg-card px-3 py-1.5 text-sm text-foreground md:py-2">
              <div className="grid min-w-0 flex-1 gap-0.5">
                <p><strong className="font-semibold">Live data is unavailable right now.</strong><span className="max-md:sr-only"> Showing the static design fixture.</span></p>
                <NoticeMeta code={fallback.code} />
              </div>
              <Button variant="outline" size="sm" className="max-md:h-11 max-md:px-4" onClick={retry}>Retry</Button>
            </div>
          )}
          {live?.notice && <LiveNoticeBanner notice={live.notice} timeZone={snapshot?.timezone ?? "UTC"} />}
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

          {productMatches.length > 0 && (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="text-xs font-medium text-muted-foreground">Products</span>
              <ul aria-label="Matching products" className="flex flex-wrap gap-2">
                {productMatches.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => chooseProductFromSearch(item.id)}
                      className="min-h-10 rounded-lg border border-border bg-card px-3 text-left text-sm text-foreground outline-none hover:border-foreground/40 focus-visible:ring-2 focus-visible:ring-ring max-md:min-h-11"
                    >
                      Show {item.name} ({item.unitPlural}){item.id === product?.id ? <span className="text-muted-foreground"> · selected</span> : null}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {snapshot && <SiteList items={matches} selectedId={selectedId} query={query} onSelect={select} />}

          <section aria-label="Network map" className="relative flex min-h-0 flex-col gap-3 md:gap-4 lg:block lg:min-h-[540px] lg:flex-1">
            <RiskLegend
              ref={setLegend}
              context={legendContext}
              className="lg:absolute lg:top-4 lg:left-4 lg:z-10 lg:w-max"
              style={isDesktop ? { maxWidth: `calc(100% - ${reserveRight + 32}px)`, translate: translateOf("legend") } : undefined}
              grip={isDesktop && snapshot ? panelGrip("legend", "Move legend", () => legend) : undefined}
              lifted={liftedPanel === "legend"}
            />
            {load.status === "loading" && (
              <div role="status" className="relative grid h-[60svh] place-items-center overflow-hidden rounded-2xl border border-border bg-pp-surface-muted lg:h-full">
                <Skeleton className="absolute inset-6 rounded-xl bg-pp-border/50" />
                <span className="relative rounded-md bg-card px-3 py-1.5 text-sm text-foreground">Loading network snapshot…</span>
              </div>
            )}
            {load.status === "error" && (
              <div className="grid h-[60svh] place-items-center rounded-2xl border border-dashed border-border bg-pp-surface-muted p-6 text-center text-sm text-muted-foreground lg:h-full">
                The map stays empty until a snapshot loads.
              </div>
            )}
            {snapshot && product && (
              <SchematicMapRenderer
                className="h-[60svh] lg:h-full"
                compact={!isDesktop}
                markers={markers}
                positions={positions}
                selectedId={selectedId}
                onSelect={select}
                reserveRight={reserveRight}
                reserveTop={isDesktop && legendHeight > 0 ? 16 + legendHeight : 0}
                onMoveNode={saveNodePosition}
                onResetLayout={resetLayout}
                layoutCustomized={isCustomized(layout)}
                renderSelection={(dock) => selected && (
                  // Docked along the bottom of the map so the card never hides other sites (desktop) and
                  // sits above the zoom row on narrow layouts. Desktop: movable by its grip.
                  <SelectionCard
                    open={popoverOpen}
                    onClose={() => setPopoverOpen(false)}
                    dock={dock}
                    offset={offsetOf("card")}
                    contentKey={selected.site.id}
                    label={selected.site.name}
                    lifted={liftedPanel === "card"}
                    onCloseAutoFocus={(event) => {
                      event.preventDefault();
                      if (afterPopoverClose.current === "invoker") restoreFocus();
                    }}
                  >
                    <PopoverSummary
                      row={selected}
                      product={product}
                      snapshot={snapshot}
                      dayIndex={dayIndex}
                      onInspect={inspect}
                      grip={isDesktop ? panelGrip("card", "Move selection card", () => document.querySelector<HTMLElement>("[data-selection-card]")) : undefined}
                    />
                  </SelectionCard>
                )}
              />
            )}
            {snapshot && product && isDesktop && (
              // The frame moves (grip on its top edge); the aside inside it scrolls.
              <div
                data-inspector-frame
                data-atlas-obstacle
                className="absolute top-4 right-4 bottom-4 z-10"
                style={{ width: inspectorWidth, translate: translateOf("inspector") }}
              >
              <div className="absolute -top-3 left-1/2 z-30 -translate-x-1/2 rounded-full border border-border bg-card shadow-sm">
                {panelGrip("inspector", "Move inspector", () => document.querySelector<HTMLElement>("[data-inspector-frame]"), "horizontal")}
              </div>
              <aside
                ref={setInspectorPanel}
                aria-label="Site inspector"
                data-testid="site-inspector"
                className={`relative h-full overflow-y-auto rounded-xl border border-border bg-card p-4 transition-shadow duration-150 ${liftedPanel === "inspector" ? "shadow-xl ring-1 ring-primary/40" : "shadow-sm"}`}
              >
                <AnimatePresence initial={false} mode="popLayout">
                {inspectorBody ?? (
                  <motion.div
                    key="unselected"
                    className="grid gap-4 text-sm"
                    initial={reduced ? false : { opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={reduced ? { opacity: 0, transition: { duration: 0 } } : { opacity: 0, transition: { duration: 0.12 } }}
                    transition={SPRING}
                  >
                    <div className="grid gap-0.5">
                      <h2 className="text-base font-semibold">Site inspector</h2>
                      <p className="text-[13px] text-muted-foreground">Select a site for stock, deficits and outlook.</p>
                    </div>
                    <div className="grid gap-1.5 border-t border-border pt-4">
                      <h3 className="text-xs font-medium text-muted-foreground">Next deficits from {dayLabel}, earliest first</h3>
                      {deficits.length === 0 ? (
                        // Not evaluated is never reported as "no deficit".
                        <p>
                          {counts.not_evaluated === beneficiaryCount
                            ? "No statuses to list: every pantry is Not evaluated."
                            : `No projected deficits from ${dayLabel} through ${formatDay(snapshot.dates[snapshot.dates.length - 1])}${counts.not_evaluated > 0 ? " among evaluated pantries" : ""}.`}
                        </p>
                      ) : (
                        <ul aria-label="Projected deficits" className="grid gap-1.5">
                          {deficits.map(({ row, next }, index) => (
                            // Re-keyed per product and day so the list staggers in after a filter change.
                            <motion.li
                              key={`${row.site.id}-${product.id}-${dayIndex}`}
                              initial={reduced ? false : { opacity: 0, y: 6 }}
                              animate={{ opacity: 1, y: 0 }}
                              transition={{ ...SPRING, delay: index * 0.05 }}
                            >
                              <motion.button
                                type="button"
                                {...PRESS}
                                onClick={(event) => selectFromList(row.site.id, event.currentTarget)}
                                className="flex min-h-10 w-full items-center gap-2 rounded-lg border border-border bg-card px-2.5 py-1 text-left leading-tight outline-none transition-[border-color,background-color,box-shadow] duration-150 hover:border-foreground/40 hover:bg-pp-surface-muted/60 focus-visible:ring-2 focus-visible:ring-ring"
                              >
                                <StatusGlyph status={row.status} />
                                <span className="min-w-0">
                                  <span className="block text-[13px] font-semibold">{row.site.shortName}<span className="sr-only"> · </span></span>
                                  <span className="block text-xs">{formatDay(snapshot.dates[next.dayIndex])} · {formatUnits(next.unmetUnits, product)} unmet</span>
                                </span>
                              </motion.button>
                            </motion.li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <dl className="grid gap-1 rounded-lg bg-muted px-3 py-2.5">
                      <dt className="text-xs text-muted-foreground">{beneficiaryCount} pantries on {dayLabel}</dt>
                      {(Object.keys(counts) as BeneficiaryStatus[]).map((status) => (
                        <dd key={status} className="flex items-center justify-between gap-2">
                          <span className="inline-flex items-center gap-2"><StatusGlyph status={status} />{STATUS_LABEL[status]}</span>
                          <span className="font-medium tabular-nums">{counts[status]}</span>
                        </dd>
                      ))}
                    </dl>
                  </motion.div>
                )}
                </AnimatePresence>
                {inspectorBelow && <ScrollCue className="-mx-4" />}
              </aside>
              </div>
            )}
          </section>

          {!isDesktop && (
            <Sheet open={sheetOpen && !!inspectorBody} onOpenChange={setSheetOpen}>
              <SheetContent
                ref={setSheetPanel}
                side="bottom"
                data-testid="site-inspector"
                className="max-h-[85svh] overflow-y-auto rounded-t-2xl bg-card p-4 [&>button:last-child]:z-20"
                onCloseAutoFocus={(event) => {
                  event.preventDefault();
                  restoreFocus();
                }}
              >
                <SheetDescription className="sr-only">Stock, first deficit and outlook for the selected site.</SheetDescription>
                {inspectorBody}
                {sheetBelow && <ScrollCue className="-mx-4 -mt-4" />}
              </SheetContent>
            </Sheet>
          )}

          {isDesktop && <PanelGripHint />}
          <footer className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">{snapshot?.provenance.label ?? STATIC_FIXTURE_LABEL}</span>
            {snapshot && live && (
              <>
                <span>Observed {formatInstant(live.observedAt, snapshot.timezone)}</span>
                {live.forecastRunId && (
                  <span className="min-w-0">Forecast run <code className="font-mono text-[11px] break-all text-foreground">{live.forecastRunId}</code>, recorded {formatInstant(live.forecastRecordedAt, snapshot.timezone)}</span>
                )}
                {methodLine && <span>{methodLine}</span>}
              </>
            )}
            {snapshot && !live && <span>Fixture {snapshot.provenance.fixtureId}; sites and products from {snapshot.provenance.sourceDataset}</span>}
            {snapshot && <span>Local dates {formatRange(snapshot.dates)} ({snapshot.timezone})</span>}
            {live && live.warnings.length > 0 && (
              <div className="basis-full">
                <span className="font-medium text-foreground">API warnings</span>
                <ul className="mt-0.5 list-disc pl-4">
                  {live.warnings.map((warning) => <li key={warning}>{warning}</li>)}
                </ul>
              </div>
            )}
            <span>
              Method comparisons on frozen simulated scenarios run in the{" "}
              <Link className="text-foreground underline underline-offset-2 outline-none focus-visible:ring-2 focus-visible:ring-ring" href="/optimization">optimization workspace</Link>;
              this map shows {live ? "live presenter data (demand and physical eligible stock only)" : "a static fixture"}, not a saved plan. Method: EGP-PI-inspired allocation, after{" "}
              <a className="text-foreground underline underline-offset-2 outline-none focus-visible:ring-2 focus-visible:ring-ring" href={DOI_URL}>Rampazo et al., published Sep 11, 2026</a>.
            </span>
          </footer>
        </div>
      </AppShell>
    </MotionConfig>
  );
}

type Row = { site: OverviewSnapshot["sites"][number]; projection: OverviewSnapshot["projections"][string][string] | undefined; status: MarkerStatus; detail: string; method?: ForecastMethod };

function PopoverSummary({ row, product, snapshot, dayIndex, onInspect, grip }: { row: Row; product: OverviewSnapshot["products"][number]; snapshot: OverviewSnapshot; dayIndex: number; onInspect: () => void; grip?: React.ReactNode }) {
  const day = formatDay(snapshot.dates[dayIndex]);
  let deficitLine: string;
  if (row.status === "hub") deficitLine = "Hub has no demand forecast.";
  else if (row.projection?.kind === "insufficient_data") deficitLine = "Insufficient data: no projection.";
  else if (row.status === "not_evaluated") deficitLine = "Not evaluated: no projection.";
  else {
    const next = nextDeficitFrom(row.projection, dayIndex);
    deficitLine = next ? `Next deficit ${nextDeficitLine(row.projection, product, snapshot.dates, dayIndex)}` : nextDeficitLine(row.projection, product, snapshot.dates, dayIndex);
  }

  // Nothing truncates: name and role wrap on their own lines; the day and unit stay together.
  return (
    <div className="grid gap-1.5">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm leading-snug font-semibold">{row.site.name}</p>
          <p className="text-xs text-muted-foreground first-letter:uppercase">{roleLabel(row.site)}</p>
        </div>
        <Button asChild size="sm" className="shrink-0 max-md:h-11">
          <motion.button type="button" onClick={onInspect} {...PRESS}>Inspect site</motion.button>
        </Button>
        {grip && <span className="inline-flex self-center">{grip}</span>}
      </div>
      <p className="flex items-center gap-1.5 text-[13px]">
        <StatusGlyph status={row.status} />
        <span>
          <strong className="font-semibold">{STATUS_LABEL[row.status]}</strong>{" "}
          <span className="whitespace-nowrap">{row.status === "hub" ? `· ${product.unitPlural}` : `on ${day} · ${product.unitPlural}`}</span>
        </span>
      </p>
      <p className="text-xs">{deficitLine}</p>
      {row.method && (row.method.fallbackUsed ? <FallbackNote method={row.method} /> : <p className="text-xs text-muted-foreground">Forecast method: {providerLabel(row.method.provider)}</p>)}
    </div>
  );
}
