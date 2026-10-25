import { useEffect, useRef, useState, type PointerEvent } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Focus, Minus, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { ResolvedPosition } from "./atlas-layout";
import { StatusGlyph } from "./status-glyph";
import type { MarkerStatus, Site } from "./types";

/**
 * NetworkMap boundary: stable site ids, roles, resolved schematic positions, status and selection.
 * SchematicMapRenderer draws it as SVG + HTML markers. A future geographic renderer can take the
 * same props once validated coordinates exist; until then positions are illustrative only.
 */
/** `statusLine` is the short visible status, e.g. "Watch · Oct 27". */
export type MapMarker = { site: Site; status: MarkerStatus; statusLine: string; accessibleName: string };

/**
 * Where the selection card docks, in map pixels. `top` is the anchor line and `side` the side of it the
 * card opens on. Desktop: a band along the bottom of the map that markers never enter. Compact: above
 * the zoom row, or below the caption at the top when the selected marker sits in the lower half, so the
 * card never covers the site it describes. Position only; nothing pans.
 */
export type SelectionContext = { left: number; top: number; width: number; side: "top" | "bottom" };

export type NetworkMapProps = {
  markers: MapMarker[];
  positions: Map<string, ResolvedPosition>;
  selectedId: string | null;
  onSelect: (siteId: string, invoker: HTMLElement) => void;
  /** Width covered by a floating panel on the right; markers fit in the remaining space. */
  reserveRight: number;
  /** Bottom edge of a floating panel along the top (the legend on desktop); markers start below it. */
  reserveTop?: number;
  /** Narrow layout: controls in a row along the bottom, caption at the top. */
  compact?: boolean;
  /** Rendered at the selected marker's point (used to anchor the popover). */
  renderSelection?: (context: SelectionContext) => React.ReactNode;
  className?: string;
};

const ZOOM_MIN = 0.7;
const ZOOM_MAX = 1.8;
// Marker box: 104px wide, ~82px tall. Its glyph centre sits 22px from the box top (label below)
// or 59px from the top (label above).
const GLYPH_FROM_TOP_LABEL_BELOW = 22;
const GLYPH_FROM_TOP_LABEL_ABOVE = 59;
const PAD_X = 60;
// Top clearance for labels drawn above the top row (and, on narrow layouts, the caption).
const PAD_TOP = 84;
const LABEL_ABOVE_CLEARANCE = 74;
// Desktop markers stay above a ~120px selection band along the bottom of the map.
const PAD_BOTTOM = 192;
const CAPTION_WIDTH = 232;
// Leaves >= 8px between the bottom marker label and the 46px control row.
const PAD_BOTTOM_COMPACT = 112;
const DOCK_INSET = 16;

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

type Point = { left: number; top: number };

/**
 * Supply link geometry, hub -> beneficiary only (permitted in both transfer modes, so no mode is implied).
 * The curve leaves the hub horizontally and meets the pantry vertically, so it never crosses a label:
 * labels sit above the glyph for sites level with or above the hub, below it for sites below the hub.
 * Same-height links bow slightly downward, away from labels drawn above.
 */
export function supplyLinkPath(hub: Point, site: Point) {
  const dx = site.left - hub.left;
  const dy = site.top - hub.top;
  if (Math.abs(dy) < 1) {
    const bow = Math.min(28, Math.abs(dx) * 0.08);
    return `M ${hub.left} ${hub.top} Q ${hub.left + dx / 2} ${hub.top + bow} ${site.left} ${site.top}`;
  }
  return `M ${hub.left} ${hub.top} C ${hub.left + dx * 0.6} ${hub.top}, ${site.left} ${site.top - dy * 0.35}, ${site.left} ${site.top}`;
}

// Decorative, abstract contour texture. Not geography: no coastlines, roads or place names.
const CONTOURS = [
  { x: 230, y: 170, scales: [1, 0.78, 0.56, 0.34] },
  { x: 760, y: 430, scales: [1.2, 0.95, 0.7, 0.45, 0.22] },
  { x: 560, y: 120, scales: [0.7, 0.5, 0.3] },
  { x: 180, y: 520, scales: [0.9, 0.66, 0.42] },
];
const BLOB = "M -150 -10 C -150 -90 -60 -120 20 -110 C 110 -100 160 -40 150 30 C 140 100 60 125 -20 115 C -100 105 -150 60 -150 -10 Z";

function MapTexture() {
  return (
    <svg className="absolute inset-0 size-full" viewBox="0 0 1000 620" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs>
        <pattern id="atlas-grid" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M 40 0 L 0 0 0 40" fill="none" stroke="var(--pp-border)" strokeWidth="0.6" opacity="0.55" />
        </pattern>
      </defs>
      <rect width="1000" height="620" fill="url(#atlas-grid)" />
      {CONTOURS.map((contour) => (
        <g key={`${contour.x}-${contour.y}`} transform={`translate(${contour.x} ${contour.y})`}>
          {contour.scales.map((scale, index) => (
            <path
              key={scale}
              d={BLOB}
              transform={`scale(${scale}) rotate(${index * 9})`}
              fill={index === 0 ? "var(--pp-canvas)" : "none"}
              stroke="var(--pp-border)"
              strokeWidth={1.2 / scale}
              opacity={0.9}
            />
          ))}
        </g>
      ))}
    </svg>
  );
}

type MarkerProps = {
  marker: MapMarker;
  point: Point;
  labelAbove: boolean;
  selected: boolean;
  index: number;
  animate: boolean;
  onSelect: NetworkMapProps["onSelect"];
};

/** AtlasMarker: one site as a keyboard-operable button. Status is shape + text, not colour alone. */
function AtlasMarker({ marker, point, labelAbove, selected, index, animate, onSelect }: MarkerProps) {
  const { site, status } = marker;
  const isHub = site.role === "HUB";
  const glyph = (
    <motion.span
      className={cn("relative grid size-10 place-items-center rounded-full border bg-card shadow-sm transition-colors duration-200", selected ? "border-primary" : "border-border group-hover:border-foreground/40")}
      animate={{ scale: selected ? 1.1 : 1 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      {selected && (
        <motion.span
          aria-hidden="true"
          className="absolute -inset-1.5 rounded-full border-2 border-primary"
          initial={animate ? { opacity: 0, scale: 0.7 } : false}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
        />
      )}
      {animate ? (
        <AnimatePresence initial={false} mode="wait">
          <motion.span key={status} className="grid place-items-center" initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.6 }} transition={{ duration: 0.22 }}>
            <StatusGlyph status={status} size={isHub ? 22 : 20} />
          </motion.span>
        </AnimatePresence>
      ) : (
        <StatusGlyph status={status} size={isHub ? 22 : 20} />
      )}
    </motion.span>
  );
  const label = (
    <span className="max-w-full rounded-md bg-card/95 px-1.5 py-0.5 text-center leading-tight shadow-xs">
      <span className="block font-condensed text-xs font-semibold whitespace-nowrap text-foreground">{site.shortName}</span>
      {animate ? (
        <AnimatePresence initial={false} mode="wait">
          <motion.span key={marker.statusLine} className="block text-[11px] whitespace-nowrap text-foreground" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
            {marker.statusLine}
          </motion.span>
        </AnimatePresence>
      ) : (
        <span className="block text-[11px] whitespace-nowrap text-foreground">{marker.statusLine}</span>
      )}
    </span>
  );
  return (
    <motion.button
      type="button"
      data-marker-role={isHub ? "hub" : "beneficiary"}
      data-site-id={site.id}
      data-status={status}
      data-label={labelAbove ? "above" : "below"}
      aria-label={marker.accessibleName}
      aria-pressed={selected}
      onClick={(event) => onSelect(site.id, event.currentTarget)}
      className="group absolute flex w-26 -translate-x-1/2 flex-col items-center gap-1 rounded-lg p-0.5 outline-none transition-[translate] duration-150 hover:-translate-y-0.5 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background active:translate-y-0"
      style={{ left: point.left, top: point.top - (labelAbove ? GLYPH_FROM_TOP_LABEL_ABOVE : GLYPH_FROM_TOP_LABEL_BELOW) }}
      initial={animate ? { opacity: 0, scale: 0.85 } : false}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.25, delay: 0.1 + index * 0.06, ease: "easeOut" }}
    >
      {labelAbove ? <>{label}{glyph}</> : <>{glyph}{label}</>}
    </motion.button>
  );
}

export function SchematicMapRenderer({ markers, positions, selectedId, onSelect, reserveRight, reserveTop = 0, compact = false, renderSelection, className }: NetworkMapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);
  // First-load reveals and status transitions explain change; they are skipped under reduced motion.
  const animate = !useReducedMotion();

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const observer = new ResizeObserver(([entry]) => setSize({ width: entry.contentRect.width, height: entry.contentRect.height }));
    observer.observe(map);
    return () => observer.disconnect();
  }, []);

  const top = reserveTop > 0 ? reserveTop + LABEL_ABOVE_CLEARANCE : PAD_TOP;
  const bottom = compact ? PAD_BOTTOM_COMPACT : PAD_BOTTOM;
  const area = {
    left: PAD_X,
    top,
    width: Math.max(1, size.width - reserveRight - PAD_X * 2),
    height: Math.max(1, size.height - top - bottom),
  };
  const center = { x: area.left + area.width / 2, y: area.top + area.height / 2 };

  function project(position: ResolvedPosition) {
    const baseX = area.left + position.x * area.width;
    const baseY = area.top + position.y * area.height;
    return { left: center.x + (baseX - center.x) * zoom + pan.x, top: center.y + (baseY - center.y) * zoom + pan.y };
  }

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    if ((event.target as HTMLElement).closest("button")) return;
    drag.current = { x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!drag.current) return;
    setPan({ x: drag.current.panX + event.clientX - drag.current.x, y: drag.current.panY + event.clientY - drag.current.y });
  }

  function onPointerUp(event: PointerEvent<HTMLDivElement>) {
    drag.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }

  const selectedPosition = selectedId ? positions.get(selectedId) : undefined;
  const ready = size.width > 0;
  const hubs = markers.filter((marker) => marker.site.role === "HUB");
  const hubY = positions.get(hubs[0]?.site.id ?? "")?.y ?? 0.5;
  // One link per hub -> beneficiary pair; never pantry <-> pantry (that topology needs a transfer mode).
  const links = ready
    ? hubs.flatMap((hub) => {
        const hubPosition = positions.get(hub.site.id);
        if (!hubPosition) return [];
        return markers
          .filter((marker) => marker.site.role !== "HUB")
          .flatMap((marker) => {
            const position = positions.get(marker.site.id);
            return position ? [{ hubId: hub.site.id, siteId: marker.site.id, d: supplyLinkPath(project(hubPosition), project(position)) }] : [];
          });
      })
    : [];
  const selectedIsHub = hubs.some((hub) => hub.site.id === selectedId);
  const emphasized = (link: { hubId: string; siteId: string }) => selectedIsHub ? link.hubId === selectedId : link.siteId === selectedId;

  return (
    <div
      ref={mapRef}
      data-atlas-map
      className={cn("relative touch-none overflow-hidden rounded-2xl border border-border bg-pp-surface-muted select-none", className)}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
    >
      <div className="absolute inset-0" style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, transformOrigin: `${center.x}px ${center.y}px` }}>
        <MapTexture />
      </div>
      {/* Supply links: what the hub can send to, not a planned route or shipment. Drawn under markers. */}
      <svg className="pointer-events-none absolute inset-0 size-full" aria-hidden="true">
        {links.map((link, index) => {
          const isEmphasized = emphasized(link);
          return (
            <motion.path
              key={`${link.hubId}-${link.siteId}`}
              data-supply-link={link.siteId}
              data-from={link.hubId}
              data-emphasis={String(isEmphasized)}
              d={link.d}
              fill="none"
              strokeLinecap="round"
              stroke="var(--pp-ink-muted)"
              strokeWidth={1.5}
              initial={animate ? { pathLength: 0, opacity: 0 } : false}
              animate={{ pathLength: 1, opacity: selectedId && !isEmphasized ? 0.25 : 0.55 }}
              transition={{ pathLength: { duration: 0.7, delay: 0.1 + index * 0.04, ease: "easeInOut" }, opacity: { duration: 0.2 } }}
            />
          );
        })}
        {/* The selected site's link (or every link for the hub) re-draws in teal; keyed so it re-runs per selection. */}
        {links.filter(emphasized).map((link) => (
          <motion.path
            key={`emphasis-${selectedId}-${link.siteId}`}
            data-supply-emphasis={link.siteId}
            d={link.d}
            fill="none"
            strokeLinecap="round"
            stroke="var(--pp-teal)"
            strokeWidth={2.5}
            initial={animate ? { pathLength: 0 } : false}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
          />
        ))}
      </svg>
      {ready && markers.map((marker, index) => {
        const position = positions.get(marker.site.id);
        if (!position) return null;
        return (
          <AtlasMarker
            key={marker.site.id}
            marker={marker}
            point={project(position)}
            labelAbove={position.y <= hubY + 1e-6}
            selected={marker.site.id === selectedId}
            index={index}
            animate={animate}
            onSelect={onSelect}
          />
        );
      })}
      {ready && selectedPosition && renderSelection?.(
        compact
          ? project(selectedPosition).top > size.height / 2
            ? { left: DOCK_INSET, top: 40, width: size.width - DOCK_INSET * 2, side: "bottom" }
            : { left: DOCK_INSET, top: size.height - 64, width: size.width - DOCK_INSET * 2, side: "top" }
          : { left: PAD_X, top: size.height - DOCK_INSET, width: clamp(size.width - reserveRight - PAD_X - 12 - CAPTION_WIDTH, 280, 420), side: "top" },
      )}
      <div className={cn("absolute bottom-3 left-3 z-10 flex overflow-hidden rounded-lg border border-border bg-card shadow-sm", compact ? "flex-row" : "flex-col")} role="group" aria-label="Map controls">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="size-9 rounded-none max-md:size-11" aria-label="Zoom in" onClick={() => setZoom((value) => clamp(value + 0.15, ZOOM_MIN, ZOOM_MAX))}><Plus /></Button>
          </TooltipTrigger>
          <TooltipContent side="right">Zoom in</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="size-9 rounded-none border-border max-md:size-11 data-[compact=true]:border-l data-[compact=false]:border-t" data-compact={compact} aria-label="Zoom out" onClick={() => setZoom((value) => clamp(value - 0.15, ZOOM_MIN, ZOOM_MAX))}><Minus /></Button>
          </TooltipTrigger>
          <TooltipContent side="right">Zoom out</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="size-9 rounded-none border-border max-md:size-11 data-[compact=true]:border-l data-[compact=false]:border-t" data-compact={compact} aria-label="Fit network" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}><Focus /></Button>
          </TooltipTrigger>
          <TooltipContent side="right">Fit network</TooltipContent>
        </Tooltip>
      </div>
      <p className={cn("absolute z-10 rounded-md bg-card/95 px-2 py-1 text-xs text-muted-foreground shadow-xs", compact ? "top-3 left-3" : "bottom-3")} style={compact ? undefined : { right: 12 + reserveRight }}>
        Illustrative layout — not geography
      </p>
    </div>
  );
}
