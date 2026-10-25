import { useSyncExternalStore } from "react";

/**
 * Per-browser Network Atlas layout (PP-52): where this viewer dragged map nodes and floating panels.
 * A viewing convenience only, never shared and never part of the data. Stored in localStorage under a
 * schema version; anything unreadable, from another version, or out of range is ignored, so the
 * layout falls back to atlas-layout.ts defaults. Storage can be blocked (private windows, site-data
 * settings): every access is guarded and moves still work for the current page view.
 *
 * - Nodes: `{ x, y }` per site id, normalised on the same placement area as atlas-layout.ts.
 * - Panels: `{ dx, dy }` pixel offsets of the legend, the desktop inspector and the docked card from
 *   their default spot.
 */

export const LAYOUT_STORAGE_KEY = "pp-atlas-layout";
export const LAYOUT_SCHEMA_VERSION = 1;

export type PanelId = "legend" | "inspector" | "card";
export type NodePosition = { x: number; y: number };
export type PanelOffset = { dx: number; dy: number };
export type SavedLayout = {
  v: typeof LAYOUT_SCHEMA_VERSION;
  nodes: Readonly<Record<string, NodePosition>>;
  panels: Readonly<Partial<Record<PanelId, PanelOffset>>>;
};

const PANELS: readonly PanelId[] = ["legend", "inspector", "card"];
// Dragged positions are clamped to the map, so saved values stay close to 0–1; anything far outside is corrupt.
const NODE_MIN = -1;
const NODE_MAX = 2;
const MAX_OFFSET = 4000;

export const EMPTY_LAYOUT: SavedLayout = Object.freeze({ v: LAYOUT_SCHEMA_VERSION, nodes: Object.freeze({}), panels: Object.freeze({}) });

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function inRange(value: unknown, min: number, max: number): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= min && value <= max;
}

/** Validates a stored layout. Returns the empty layout for anything that is not a valid v1 layout. */
export function parseLayout(raw: string | null): SavedLayout {
  if (!raw) return EMPTY_LAYOUT;
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return EMPTY_LAYOUT;
  }
  if (!isRecord(data) || data.v !== LAYOUT_SCHEMA_VERSION) return EMPTY_LAYOUT;
  // Null-prototype maps: a site id such as "__proto__" stays an ordinary key.
  const nodes: Record<string, NodePosition> = Object.create(null);
  if (isRecord(data.nodes)) {
    for (const [siteId, value] of Object.entries(data.nodes)) {
      if (siteId && isRecord(value) && inRange(value.x, NODE_MIN, NODE_MAX) && inRange(value.y, NODE_MIN, NODE_MAX)) nodes[siteId] = { x: value.x, y: value.y };
    }
  }
  const panels: Partial<Record<PanelId, PanelOffset>> = {};
  if (isRecord(data.panels)) {
    for (const id of PANELS) {
      const value = Object.hasOwn(data.panels, id) ? data.panels[id] : undefined;
      if (isRecord(value) && inRange(value.dx, -MAX_OFFSET, MAX_OFFSET) && inRange(value.dy, -MAX_OFFSET, MAX_OFFSET)) panels[id] = { dx: value.dx, dy: value.dy };
    }
  }
  return { v: LAYOUT_SCHEMA_VERSION, nodes, panels };
}

export function isCustomized(layout: SavedLayout) {
  return Object.keys(layout.nodes).length > 0 || Object.keys(layout.panels).length > 0;
}

// The in-memory layout is the source of truth for this page view; storage only persists it.
let memory: SavedLayout | null = null;
const listeners = new Set<() => void>();

function readStored(): SavedLayout {
  try {
    return parseLayout(window.localStorage.getItem(LAYOUT_STORAGE_KEY));
  } catch {
    return EMPTY_LAYOUT;
  }
}

function current(): SavedLayout {
  if (memory === null) memory = readStored();
  return memory;
}

function commit(next: SavedLayout) {
  memory = next;
  try {
    if (isCustomized(next)) window.localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(next));
    else window.localStorage.removeItem(LAYOUT_STORAGE_KEY);
  } catch {
    // Not persisted; the move still applies to this page view.
  }
  for (const listener of listeners) listener();
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  // Another tab changed or cleared the layout.
  const onStorage = (event: StorageEvent) => {
    if (event.key !== null && event.key !== LAYOUT_STORAGE_KEY) return;
    memory = parseLayout(event.newValue);
    onChange();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onStorage);
  };
}

export function saveNodePosition(siteId: string, position: NodePosition) {
  const layout = current();
  const x = Math.min(NODE_MAX, Math.max(NODE_MIN, position.x));
  const y = Math.min(NODE_MAX, Math.max(NODE_MIN, position.y));
  commit({ ...layout, nodes: { ...layout.nodes, [siteId]: { x, y } } });
}

export function savePanelOffset(id: PanelId, offset: PanelOffset) {
  const layout = current();
  const dx = Math.round(Math.min(MAX_OFFSET, Math.max(-MAX_OFFSET, offset.dx)));
  const dy = Math.round(Math.min(MAX_OFFSET, Math.max(-MAX_OFFSET, offset.dy)));
  const panels = { ...layout.panels };
  if (dx === 0 && dy === 0) delete panels[id];
  else panels[id] = { dx, dy };
  commit({ ...layout, panels });
}

export function resetLayout() {
  commit(EMPTY_LAYOUT);
}

/** The saved layout; the server render and the first hydration pass use the empty (default) layout. */
export function useSavedLayout(): SavedLayout {
  return useSyncExternalStore(subscribe, current, () => EMPTY_LAYOUT);
}
