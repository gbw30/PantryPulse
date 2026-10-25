/**
 * Map-pixel geometry for dragged nodes and panels (PP-52). Boxes are relative to the map's padding box.
 * Pure functions, so drop clamping is deterministic and does not depend on animation.
 */

export type Box = { left: number; top: number; width: number; height: number };
export type Point = { left: number; top: number };

// Marker button: 104px wide (w-26), about 82px tall. Its glyph centre sits 22px from the box top
// (label below) or 59px from the top (label above).
export const MARKER_WIDTH = 104;
export const MARKER_HEIGHT = 82;
export const GLYPH_FROM_TOP_LABEL_BELOW = 22;
export const GLYPH_FROM_TOP_LABEL_ABOVE = 59;
/** Clearance kept between a dropped node and the map edge or any panel or control. */
export const DROP_GAP = 8;

export function markerBox(point: Point, labelAbove: boolean): Box {
  const fromTop = labelAbove ? GLYPH_FROM_TOP_LABEL_ABOVE : GLYPH_FROM_TOP_LABEL_BELOW;
  return { left: point.left - MARKER_WIDTH / 2, top: point.top - fromTop, width: MARKER_WIDTH, height: MARKER_HEIGHT };
}

export function glyphPoint(box: Box, labelAbove: boolean): Point {
  return { left: box.left + MARKER_WIDTH / 2, top: box.top + (labelAbove ? GLYPH_FROM_TOP_LABEL_ABOVE : GLYPH_FROM_TOP_LABEL_BELOW) };
}

export function overlaps(a: Box, b: Box, gap = 0) {
  return a.left < b.left + b.width + gap && b.left < a.left + a.width + gap && a.top < b.top + b.height + gap && b.top < a.top + a.height + gap;
}

function insideBox(inner: Box, outer: Box) {
  return inner.left >= outer.left - 0.5 && inner.top >= outer.top - 0.5
    && inner.left + inner.width <= outer.left + outer.width + 0.5 && inner.top + inner.height <= outer.top + outer.height + 0.5;
}

/** Moves `box` the least distance that puts it fully inside `bounds` (pinned to the start edge when it cannot fit). */
export function clampInside(box: Box, bounds: Box): Box {
  const left = Math.max(bounds.left, Math.min(box.left, bounds.left + bounds.width - box.width));
  const top = Math.max(bounds.top, Math.min(box.top, bounds.top + bounds.height - box.height));
  return { ...box, left, top };
}

const distance = (a: Box, b: Box) => Math.hypot(a.left - b.left, a.top - b.top);

/**
 * Where a dropped box comes to rest: inside `bounds` and at least `gap` clear of every obstacle (the
 * legend, the inspector, the docked-card band, the zoom controls, the caption). Each step pushes the box
 * out of the first obstacle it hits along the shortest of the four directions that stays in bounds,
 * preferring positions clear of all obstacles. Returns null when no clear position is found nearby, so
 * the caller keeps the node where it started.
 */
export function settleBox(box: Box, bounds: Box, obstacles: readonly Box[], gap = DROP_GAP): Box | null {
  const target = clampInside(box, bounds);
  let current = target;
  for (let attempt = 0; attempt < 6; attempt += 1) {
    const hit = obstacles.find((obstacle) => overlaps(current, obstacle, gap));
    if (!hit) return current;
    const candidates = [
      { ...current, left: hit.left - gap - current.width },
      { ...current, left: hit.left + hit.width + gap },
      { ...current, top: hit.top - gap - current.height },
      { ...current, top: hit.top + hit.height + gap },
    ].filter((candidate) => insideBox(candidate, bounds));
    if (candidates.length === 0) return null;
    const clear = candidates.filter((candidate) => !obstacles.some((obstacle) => overlaps(candidate, obstacle, gap)));
    const pool = clear.length > 0 ? clear : candidates;
    current = pool.reduce((best, candidate) => (distance(candidate, target) < distance(best, target) ? candidate : best));
  }
  return obstacles.some((obstacle) => overlaps(current, obstacle, gap)) ? null : current;
}

/** Clamps a panel offset so the panel (whose box at offset 0 is `base`) stays inside `bounds`. */
export function clampOffset(base: Box, offset: { dx: number; dy: number }, bounds: Box) {
  const moved = clampInside({ ...base, left: base.left + offset.dx, top: base.top + offset.dy }, bounds);
  return { dx: Math.round(moved.left - base.left), dy: Math.round(moved.top - base.top) };
}

/** An element's border box relative to the padding box of `frame` (the map). */
export function relativeBox(element: Element, frame: HTMLElement): Box {
  const rect = element.getBoundingClientRect();
  const origin = frame.getBoundingClientRect();
  return { left: rect.left - origin.left - frame.clientLeft, top: rect.top - origin.top - frame.clientTop, width: rect.width, height: rect.height };
}
