import type { Site } from "./types";

/**
 * Marker positions for the schematic Network Atlas — configuration, not geography.
 *
 * Each entry places one site on the schematic canvas with normalised coordinates:
 * x runs 0 (left) to 1 (right), y runs 0 (top) to 1 (bottom). Edit this list to move markers.
 * Entries with an unknown site, a duplicate site, or a coordinate outside 0–1 are ignored and that
 * site falls back to its default position: hubs at the centre, beneficiaries evenly on a ring in
 * fixture order (starting top-left, clockwise). Sites are never dropped and no geography is inferred.
 *
 * Entries match a site by id first, then by exact site name.
 * Example: { siteId: "riverbend", x: 0.5, y: 0.12 } or { siteName: "Riverbend Pantry", x: 0.5, y: 0.12 }
 */
export type AtlasLayoutEntry = { siteId?: string; siteName?: string; x: number; y: number };

export const ATLAS_LAYOUT: readonly AtlasLayoutEntry[] = [];

export type ResolvedPosition = { x: number; y: number; source: "configured" | "default" };

const RING_RADIUS_X = 0.5;
const RING_RADIUS_Y = 0.5;
// First beneficiary at the top-left; the rest follow clockwise in fixture order.
const RING_START = (-2 * Math.PI) / 3;

function isUnit(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
}

export function defaultPositions(sites: readonly Site[]): Map<string, ResolvedPosition> {
  const positions = new Map<string, ResolvedPosition>();
  const hubs = sites.filter((site) => site.role === "HUB");
  const beneficiaries = sites.filter((site) => site.role !== "HUB");
  hubs.forEach((site, index) => {
    const offset = hubs.length === 1 ? 0 : (index / (hubs.length - 1) - 0.5) * 0.24;
    positions.set(site.id, { x: 0.5 + offset, y: 0.5, source: "default" });
  });
  beneficiaries.forEach((site, index) => {
    const angle = RING_START + (index * 2 * Math.PI) / Math.max(1, beneficiaries.length);
    positions.set(site.id, {
      x: 0.5 + RING_RADIUS_X * Math.cos(angle),
      y: 0.5 + RING_RADIUS_Y * Math.sin(angle),
      source: "default",
    });
  });
  return positions;
}

export function resolveAtlasLayout(sites: readonly Site[], entries: readonly AtlasLayoutEntry[] = ATLAS_LAYOUT): Map<string, ResolvedPosition> {
  const positions = defaultPositions(sites);
  const byId = new Map(sites.map((site) => [site.id, site]));
  const byName = new Map(sites.map((site) => [site.name, site]));
  const seen = new Set<string>();
  for (const entry of entries) {
    if (!entry) continue;
    const site = (entry.siteId !== undefined ? byId.get(entry.siteId) : undefined) ?? (entry.siteName !== undefined ? byName.get(entry.siteName) : undefined);
    if (!site || seen.has(site.id)) continue;
    seen.add(site.id);
    if (isUnit(entry.x) && isUnit(entry.y)) positions.set(site.id, { x: entry.x, y: entry.y, source: "configured" });
  }
  return positions;
}
