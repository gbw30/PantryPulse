import { useRef, type KeyboardEvent, type PointerEvent } from "react";
import { GripHorizontal, GripVertical } from "lucide-react";
import { cn } from "@/lib/utils";
import { clampOffset, type Box } from "./atlas-geometry";
import type { PanelOffset } from "./layout-store";

/** Panels stay at least this far inside the map. */
const PANEL_INSET = 8;
const KEY_STEP = 8;
export const PANEL_GRIP_HINT_ID = "atlas-panel-grip-hint";

type Props = {
  /** Accessible name, e.g. "Move legend". */
  label: string;
  /** The element that moves (its box includes the current offset). */
  panel: () => HTMLElement | null;
  offset: PanelOffset;
  /** `end` when a drag or key step finishes: the caller persists it. */
  onChange: (offset: PanelOffset, phase: "move" | "end") => void;
  onLift?: (lifted: boolean) => void;
  orientation?: "vertical" | "horizontal";
  className?: string;
};

function mapElement() {
  return document.querySelector<HTMLElement>("[data-atlas-map]");
}

function viewportBox(element: Element): Box {
  const rect = element.getBoundingClientRect();
  return { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
}

/**
 * Drag handle for a floating map panel (legend, inspector, docked card): pointer drag (mouse, pen or
 * touch) or arrow keys in 8px steps, clamped so the panel stays inside the map. Desktop only; the
 * caller does not render it on narrow layouts.
 */
export function PanelGrip({ label, panel, offset, onChange, onLift, orientation = "vertical", className }: Props) {
  const drag = useRef<{ pointerId: number; x: number; y: number; start: PanelOffset; base: Box; bounds: Box; last: PanelOffset } | null>(null);

  function measure(current: PanelOffset) {
    const element = panel();
    const map = mapElement();
    if (!element || !map) return null;
    const rect = viewportBox(element);
    const mapBox = viewportBox(map);
    return {
      base: { ...rect, left: rect.left - current.dx, top: rect.top - current.dy },
      bounds: { left: mapBox.left + PANEL_INSET, top: mapBox.top + PANEL_INSET, width: mapBox.width - PANEL_INSET * 2, height: mapBox.height - PANEL_INSET * 2 },
    };
  }

  function onPointerDown(event: PointerEvent<HTMLButtonElement>) {
    if (event.button !== 0) return;
    const measured = measure(offset);
    if (!measured) return;
    event.preventDefault();
    event.stopPropagation();
    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      // Synthetic or already-released pointer: the drag still follows move events.
    }
    event.currentTarget.focus();
    drag.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, start: offset, last: offset, ...measured };
    onLift?.(true);
  }

  function onPointerMove(event: PointerEvent<HTMLButtonElement>) {
    const state = drag.current;
    if (!state || state.pointerId !== event.pointerId) return;
    const next = clampOffset(state.base, { dx: state.start.dx + event.clientX - state.x, dy: state.start.dy + event.clientY - state.y }, state.bounds);
    state.last = next;
    onChange(next, "move");
  }

  function finish(event: PointerEvent<HTMLButtonElement>) {
    const state = drag.current;
    if (!state || state.pointerId !== event.pointerId) return;
    drag.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    onLift?.(false);
    onChange(state.last, "end");
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    const step = { ArrowLeft: [-KEY_STEP, 0], ArrowRight: [KEY_STEP, 0], ArrowUp: [0, -KEY_STEP], ArrowDown: [0, KEY_STEP] }[event.key];
    if (!step) return;
    event.preventDefault();
    const measured = measure(offset);
    if (!measured) return;
    onChange(clampOffset(measured.base, { dx: offset.dx + step[0], dy: offset.dy + step[1] }, measured.bounds), "end");
  }

  const Icon = orientation === "horizontal" ? GripHorizontal : GripVertical;
  return (
    <button
      type="button"
      aria-label={label}
      aria-describedby={PANEL_GRIP_HINT_ID}
      data-panel-grip
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={finish}
      onPointerCancel={finish}
      onKeyDown={onKeyDown}
      className={cn(
        "inline-grid shrink-0 cursor-grab touch-none place-items-center rounded-md text-muted-foreground outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring active:cursor-grabbing",
        orientation === "horizontal" ? "h-6 w-10" : "size-6",
        className,
      )}
    >
      <Icon className="size-4" aria-hidden="true" />
    </button>
  );
}

/** One shared description for every grip (rendered once by the atlas). */
export function PanelGripHint() {
  return (
    <span id={PANEL_GRIP_HINT_ID} hidden>
      Drag, or use the arrow keys, to move this panel inside the map. Reset layout puts it back.
    </span>
  );
}
