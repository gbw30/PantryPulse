import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { animate as animateValue, AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Focus, Minus, Plus, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { clampInside, DROP_GAP, GLYPH_FROM_TOP_LABEL_ABOVE, GLYPH_FROM_TOP_LABEL_BELOW, glyphPoint, markerBox, relativeBox, settleBox, type Box, type Point } from "./atlas-geometry";
import type { ResolvedPosition } from "./atlas-layout";
import { PRESS, SPRING } from "./atlas-motion";
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
  /** Saves a dragged or keyboard-moved node, normalised on the placement area like atlas-layout.ts. */
  onMoveNode?: (siteId: string, position: { x: number; y: number }) => void;
  /** Restores atlas-layout.ts defaults for nodes and panels. */
  onResetLayout?: () => void;
  layoutCustomized?: boolean;
  className?: string;
};

const ZOOM_MIN = 0.7;
const ZOOM_MAX = 1.8;
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
// Desktop drops stay above the docked-card band: the tallest card (live, with a fallback note) plus its inset.
const CARD_BAND = 150;
// A press that moves less than this is a click (select), not a drag.
const DRAG_THRESHOLD = 4;
const KEY_STEP = 8;
const MOVE_HINT_ID = "atlas-move-hint";

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

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

type NodeHandlers = {
  start: (siteId: string, event: PointerEvent<HTMLButtonElement>) => void;
  move: (event: PointerEvent<HTMLButtonElement>) => void;
  end: (event: PointerEvent<HTMLButtonElement>, cancelled: boolean) => void;
  /** True when the click that follows a drag must not select. */
  consumeClick: (siteId: string) => boolean;
  key: (site: Site, event: KeyboardEvent<HTMLButtonElement>) => void;
  blur: (site: Site) => void;
};

type MarkerProps = {
  marker: MapMarker;
  point: Point;
  labelAbove: boolean;
  selected: boolean;
  lifted: boolean;
  moving: boolean;
  index: number;
  animate: boolean;
  onSelect: NetworkMapProps["onSelect"];
  handlers: NodeHandlers | null;
};

/** AtlasMarker: one site as a keyboard-operable, draggable button. Status is shape + text, not colour alone. */
function AtlasMarker({ marker, point, labelAbove, selected, lifted, moving, index, animate, onSelect, handlers }: MarkerProps) {
  const { site, status } = marker;
  const isHub = site.role === "HUB";
  const [hovered, setHovered] = useState(false);
  // Spring scale: picked up > selected > hovered (transforms, so reduced motion makes them instant).
  const scale = lifted ? 1.16 : selected ? 1.1 : hovered ? 1.06 : 1;
  const glyph = (
    <motion.span
      data-glyph
      className={cn(
        "relative grid size-10 place-items-center rounded-full border bg-card transition-[border-color,box-shadow] duration-200",
        lifted ? "border-primary shadow-lg" : selected || moving ? "border-primary shadow-sm" : "border-border shadow-sm group-hover:border-foreground/40",
      )}
      animate={{ scale }}
      transition={SPRING}
    >
      {selected && (
        <motion.span
          aria-hidden="true"
          className="absolute -inset-1.5 rounded-full border-2 border-primary"
          initial={animate ? { opacity: 0, scale: 0.7 } : false}
          animate={{ opacity: 1, scale: 1 }}
          transition={SPRING}
        />
      )}
      {moving && <span aria-hidden="true" className="absolute -inset-2.5 rounded-full border-2 border-dashed border-primary" />}
      {animate ? (
        <AnimatePresence initial={false} mode="wait">
          <motion.span key={status} className="grid place-items-center" initial={{ opacity: 0, scale: 0.5 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.5, transition: { duration: 0.12 } }} transition={SPRING}>
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
          <motion.span key={marker.statusLine} className="block text-[11px] whitespace-nowrap text-foreground" initial={{ opacity: 0, y: 3 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, transition: { duration: 0.1 } }} transition={SPRING}>
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
      data-moving={moving ? "true" : undefined}
      aria-label={marker.accessibleName}
      aria-pressed={selected}
      aria-describedby={handlers ? MOVE_HINT_ID : undefined}
      onClick={(event) => {
        if (handlers?.consumeClick(site.id)) return;
        onSelect(site.id, event.currentTarget);
      }}
      onPointerDown={handlers ? (event) => handlers.start(site.id, event) : undefined}
      onPointerMove={handlers?.move}
      onPointerUp={handlers ? (event) => handlers.end(event, false) : undefined}
      onPointerCancel={handlers ? (event) => handlers.end(event, true) : undefined}
      onPointerEnter={(event) => { if (event.pointerType === "mouse") setHovered(true); }}
      onPointerLeave={() => setHovered(false)}
      onKeyDown={handlers ? (event) => handlers.key(site, event) : undefined}
      onBlur={handlers ? () => handlers.blur(site) : undefined}
      className={cn(
        "group absolute flex w-26 -translate-x-1/2 touch-none flex-col items-center gap-1 rounded-lg p-0.5 outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        handlers && "cursor-grab",
        lifted && "z-30 cursor-grabbing",
      )}
      style={{ left: point.left, top: point.top - (labelAbove ? GLYPH_FROM_TOP_LABEL_ABOVE : GLYPH_FROM_TOP_LABEL_BELOW) }}
      initial={animate ? { opacity: 0, scale: 0.85 } : false}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ ...SPRING, delay: 0.1 + index * 0.06 }}
    >
      {labelAbove ? <>{label}{glyph}</> : <>{glyph}{label}</>}
    </motion.button>
  );
}

export function SchematicMapRenderer({ markers, positions, selectedId, onSelect, reserveRight, reserveTop = 0, compact = false, renderSelection, onMoveNode, onResetLayout, layoutCustomized = false, className }: NetworkMapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);
  // Node drag: the pointer's live point overrides the saved position until the drop settles.
  const [live, setLive] = useState<{ siteId: string; point: Point } | null>(null);
  const liveRef = useRef<{ siteId: string; point: Point } | null>(null);
  const [lifted, setLifted] = useState<string | null>(null);
  const [moving, setMoving] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const nodeDrag = useRef<{ siteId: string; pointerId: number; x: number; y: number; origin: Point; moved: boolean } | null>(null);
  const settling = useRef<ReturnType<typeof animateValue> | null>(null);
  const suppressClick = useRef<string | null>(null);
  // First-load reveals, status transitions and the drop settle explain change; reduced motion skips them.
  const animate = !useReducedMotion();

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const observer = new ResizeObserver(([entry]) => setSize({ width: entry.contentRect.width, height: entry.contentRect.height }));
    observer.observe(map);
    return () => observer.disconnect();
  }, []);

  useEffect(() => () => settling.current?.stop(), []);

  const top = reserveTop > 0 ? reserveTop + LABEL_ABOVE_CLEARANCE : PAD_TOP;
  const bottom = compact ? PAD_BOTTOM_COMPACT : PAD_BOTTOM;
  const area = {
    left: PAD_X,
    top,
    width: Math.max(1, size.width - reserveRight - PAD_X * 2),
    height: Math.max(1, size.height - top - bottom),
  };
  const center = { x: area.left + area.width / 2, y: area.top + area.height / 2 };

  function project(position: ResolvedPosition): Point {
    const baseX = area.left + position.x * area.width;
    const baseY = area.top + position.y * area.height;
    return { left: center.x + (baseX - center.x) * zoom + pan.x, top: center.y + (baseY - center.y) * zoom + pan.y };
  }

  // Inverse of project(): a map point back to the normalised placement area at the current zoom and pan.
  function unproject(point: Point) {
    const baseX = center.x + (point.left - pan.x - center.x) / zoom;
    const baseY = center.y + (point.top - pan.y - center.y) / zoom;
    return { x: (baseX - area.left) / area.width, y: (baseY - area.top) / area.height };
  }

  function updateLive(next: { siteId: string; point: Point } | null) {
    liveRef.current = next;
    setLive(next);
  }

  function announce(text: string) {
    setAnnouncement(text);
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
  const hubIds = new Set(hubs.map((hub) => hub.site.id));
  const projected = new Map<string, Point>();
  if (ready) {
    for (const marker of markers) {
      const position = positions.get(marker.site.id);
      if (position) projected.set(marker.site.id, project(position));
    }
  }
  const pointFor = (siteId: string) => (live?.siteId === siteId ? live.point : projected.get(siteId));
  const hubPoint = hubs[0] ? pointFor(hubs[0].site.id) : undefined;
  // Labels sit above the glyph for sites level with or above the hub, below it otherwise (links never cross them).
  const labelAboveAt = (siteId: string, point: Point) => hubIds.has(siteId) || !hubPoint || point.top <= hubPoint.top + 1e-6;

  // Drops stay on the map and clear of the legend, inspector, zoom controls, caption and (desktop) the
  // docked-card band. Obstacles are measured when the drop happens, so moved panels count where they are.
  const bounds: Box = { left: DROP_GAP, top: DROP_GAP, width: Math.max(0, size.width - DROP_GAP * 2), height: Math.max(0, size.height - DROP_GAP * 2) };
  function obstacles(): Box[] {
    const map = mapRef.current;
    if (!map) return [];
    const scope = map.parentElement ?? map;
    const boxes = [...scope.querySelectorAll("[data-atlas-obstacle]")].filter((element) => element.getClientRects().length > 0).map((element) => relativeBox(element, map));
    if (!compact) boxes.push({ left: 0, top: size.height - DOCK_INSET - CARD_BAND, width: size.width, height: CARD_BAND + DOCK_INSET });
    return boxes;
  }

  function resolveDrop(siteId: string, point: Point): Point | null {
    const labelAbove = labelAboveAt(siteId, point);
    const settled = settleBox(markerBox(point, labelAbove), bounds, obstacles());
    return settled ? glyphPoint(settled, labelAbove) : null;
  }

  function placeNode(siteId: string, point: Point) {
    onMoveNode?.(siteId, unproject(point));
  }

  const handlers: NodeHandlers | null = onMoveNode
    ? {
        start(siteId, event) {
          if (event.button !== 0) return;
          const origin = pointFor(siteId);
          if (!origin) return;
          settling.current?.stop();
          settling.current = null;
          if (liveRef.current && liveRef.current.siteId !== siteId) updateLive(null);
          suppressClick.current = null;
          try {
            event.currentTarget.setPointerCapture(event.pointerId);
          } catch {
            // The drag still follows this element's own move events.
          }
          nodeDrag.current = { siteId, pointerId: event.pointerId, x: event.clientX, y: event.clientY, origin, moved: false };
        },
        move(event) {
          const state = nodeDrag.current;
          if (!state || state.pointerId !== event.pointerId) return;
          const dx = event.clientX - state.x;
          const dy = event.clientY - state.y;
          if (!state.moved && Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
          if (!state.moved) {
            state.moved = true;
            setLifted(state.siteId);
            setMoving(null);
          }
          // While dragging the node follows the pointer, kept on the map; obstacles resolve on drop.
          const raw = { left: state.origin.left + dx, top: state.origin.top + dy };
          const labelAbove = labelAboveAt(state.siteId, raw);
          updateLive({ siteId: state.siteId, point: glyphPoint(clampInside(markerBox(raw, labelAbove), bounds), labelAbove) });
        },
        end(event, cancelled) {
          const state = nodeDrag.current;
          if (!state || state.pointerId !== event.pointerId) return;
          nodeDrag.current = null;
          if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
          if (!state.moved) return; // A click follows and selects.
          // The click that follows this pointerup (same task) is not a selection.
          suppressClick.current = state.siteId;
          window.setTimeout(() => {
            if (suppressClick.current === state.siteId) suppressClick.current = null;
          }, 0);
          setLifted(null);
          const from = liveRef.current?.siteId === state.siteId ? liveRef.current.point : state.origin;
          if (cancelled) {
            updateLive(null);
            return;
          }
          const target = resolveDrop(state.siteId, from) ?? state.origin;
          placeNode(state.siteId, target);
          if (!animate || (Math.abs(from.left - target.left) < 0.5 && Math.abs(from.top - target.top) < 0.5)) {
            updateLive(null);
            return;
          }
          // Spring settle from the drop point to the clamped point; marker and link move together.
          settling.current = animateValue(0, 1, {
            ...SPRING,
            onUpdate: (t) => updateLive({ siteId: state.siteId, point: { left: from.left + (target.left - from.left) * t, top: from.top + (target.top - from.top) * t } }),
            onComplete: () => {
              settling.current = null;
              updateLive(null);
            },
          });
        },
        consumeClick(siteId) {
          if (suppressClick.current !== siteId) return false;
          suppressClick.current = null;
          return true;
        },
        key(site, event) {
          if (moving !== site.id) {
            if ((event.key === "m" || event.key === "M") && !event.ctrlKey && !event.metaKey && !event.altKey) {
              event.preventDefault();
              setMoving(site.id);
              announce(`Moving ${site.name}. Arrow keys move it ${KEY_STEP} pixels at a time; Enter or Escape places it.`);
            }
            return;
          }
          const step = ({ ArrowLeft: [-KEY_STEP, 0], ArrowRight: [KEY_STEP, 0], ArrowUp: [0, -KEY_STEP], ArrowDown: [0, KEY_STEP] } as Record<string, [number, number]>)[event.key];
          if (step) {
            event.preventDefault();
            const from = pointFor(site.id);
            if (!from) return;
            const target = resolveDrop(site.id, { left: from.left + step[0], top: from.top + step[1] });
            if (target) placeNode(site.id, target);
            return;
          }
          if (event.key === "Enter" || event.key === "Escape") {
            // Placing never selects the site or clears the current selection.
            event.preventDefault();
            event.stopPropagation();
            setMoving(null);
            announce(`${site.name} placed. Reset layout restores the default layout.`);
          }
        },
        blur(site) {
          if (moving !== site.id) return;
          setMoving(null);
          announce(`${site.name} placed.`);
        },
      }
    : null;

  // One link per hub -> beneficiary pair; never pantry <-> pantry (that topology needs a transfer mode).
  const links = ready
    ? hubs.flatMap((hub) => {
        const hubAt = pointFor(hub.site.id);
        if (!hubAt) return [];
        return markers
          .filter((marker) => marker.site.role !== "HUB")
          .flatMap((marker) => {
            const at = pointFor(marker.site.id);
            return at ? [{ hubId: hub.site.id, siteId: marker.site.id, d: supplyLinkPath(hubAt, at) }] : [];
          });
      })
    : [];
  const selectedIsHub = hubIds.has(selectedId ?? "");
  const emphasized = (link: { hubId: string; siteId: string }) => selectedIsHub ? link.hubId === selectedId : link.siteId === selectedId;

  function resetLayout() {
    if (!layoutCustomized) {
      announce("The layout is already the default.");
      return;
    }
    settling.current?.stop();
    settling.current = null;
    updateLive(null);
    setMoving(null);
    onResetLayout?.();
    announce("Layout reset: sites and panels are back in their default places.");
  }

  const resetButton = onResetLayout && (
    <Button asChild variant="outline" size="sm" className="h-8 bg-card text-foreground shadow-sm aria-disabled:text-muted-foreground max-md:h-11">
      <motion.button type="button" aria-disabled={!layoutCustomized} onClick={resetLayout} {...PRESS}>
        <RotateCcw aria-hidden="true" />
        Reset layout
      </motion.button>
    </Button>
  );

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
            className="pp-supply-emphasis"
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
        {/* Flow (decision 4): dashes travel hub -> pantry on every link; same pattern everywhere, so no quantity. */}
        {links.map((link) => {
          const isEmphasized = emphasized(link);
          return (
            <path
              key={`flow-${link.hubId}-${link.siteId}`}
              data-supply-flow={link.siteId}
              data-emphasis={String(isEmphasized)}
              data-dimmed={String(Boolean(selectedId) && !isEmphasized)}
              className="pp-supply-flow"
              d={link.d}
            />
          );
        })}
      </svg>
      {ready && markers.map((marker, index) => {
        const point = pointFor(marker.site.id);
        if (!point) return null;
        return (
          <AtlasMarker
            key={marker.site.id}
            marker={marker}
            point={point}
            labelAbove={labelAboveAt(marker.site.id, point)}
            selected={marker.site.id === selectedId}
            lifted={marker.site.id === lifted}
            moving={marker.site.id === moving}
            index={index}
            animate={animate}
            onSelect={onSelect}
            handlers={handlers}
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
      <div data-atlas-obstacle className="absolute bottom-3 left-3 z-20 flex items-end gap-2">
        <div className={cn("flex overflow-hidden rounded-lg border border-border bg-card shadow-sm", compact ? "flex-row" : "flex-col")} role="group" aria-label="Map controls">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button asChild variant="ghost" size="icon" className="size-9 rounded-none max-md:size-11">
                <motion.button type="button" aria-label="Zoom in" onClick={() => setZoom((value) => clamp(value + 0.15, ZOOM_MIN, ZOOM_MAX))} {...PRESS}><Plus /></motion.button>
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">Zoom in</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button asChild variant="ghost" size="icon" className="size-9 rounded-none border-border max-md:size-11 data-[compact=true]:border-l data-[compact=false]:border-t" data-compact={compact}>
                <motion.button type="button" aria-label="Zoom out" onClick={() => setZoom((value) => clamp(value - 0.15, ZOOM_MIN, ZOOM_MAX))} {...PRESS}><Minus /></motion.button>
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">Zoom out</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button asChild variant="ghost" size="icon" className="size-9 rounded-none border-border max-md:size-11 data-[compact=true]:border-l data-[compact=false]:border-t" data-compact={compact}>
                <motion.button type="button" aria-label="Fit network" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }} {...PRESS}><Focus /></motion.button>
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">Fit network</TooltipContent>
          </Tooltip>
        </div>
        {compact && resetButton}
      </div>
      {compact ? (
        <p data-atlas-obstacle className="absolute top-3 left-3 z-10 rounded-md bg-card/95 px-2 py-1 text-xs text-muted-foreground shadow-xs">
          Illustrative layout — not geography
        </p>
      ) : (
        <div data-atlas-obstacle className="absolute bottom-3 z-20 flex flex-col items-end gap-1.5" style={{ right: 12 + reserveRight }}>
          {resetButton}
          <p className="rounded-md bg-card/95 px-2 py-1 text-xs text-muted-foreground shadow-xs">Illustrative layout — not geography</p>
        </div>
      )}
      {onMoveNode && (
        <span id={MOVE_HINT_ID} hidden>
          Press M to move this site on the map, then use the arrow keys; Enter or Escape places it. Dragging also moves it.
        </span>
      )}
      <p data-atlas-announcer role="status" aria-live="polite" className="sr-only">{announcement}</p>
    </div>
  );
}
