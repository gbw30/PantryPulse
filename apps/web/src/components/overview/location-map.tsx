import type { Schema } from "@/lib/planning-api";
import { cn } from "@/lib/utils";
import { DANGER_BANDS, DangerBandGlyph, type DangerBand } from "./risk-legend";

export type Location = Schema["LocationSummary"];
export type Placed = { location: Location; x: number; y: number };

const PAD = 0.08;
const ASPECT = 16 / 9;
const BAND_LABEL = Object.fromEntries(DANGER_BANDS.map((b) => [b.band, b.label])) as Record<DangerBand, string>;
const span = (values: number[]) => [Math.min(...values), Math.max(...values)] as const;

/**
 * Schematic placement from real coordinates (V1-SPEC §6.6): an equirectangular projection with one scale on both
 * axes, so direction and relative distance hold. x/y are percent of a 16:9 frame. No coordinates: listed, never guessed.
 */
export function placeLocations(locations: Location[], aspect = ASPECT) {
  const located = locations.filter((l) => l.latitude !== null && l.longitude !== null);
  const unplaced = locations.filter((l) => l.latitude === null || l.longitude === null);
  const [latMin, latMax] = span(located.map((l) => Number(l.latitude)));
  const k = Math.cos(((latMin + latMax) / 2) * (Math.PI / 180));
  const points = located.map((l) => ({ location: l, px: Number(l.longitude) * k, py: Number(l.latitude) }));
  const [xMin, xMax] = span(points.map((p) => p.px));
  const [yMin, yMax] = span(points.map((p) => p.py));
  const scale = Math.min(xMax > xMin ? (aspect * (1 - 2 * PAD)) / (xMax - xMin) : Infinity, yMax > yMin ? (1 - 2 * PAD) / (yMax - yMin) : Infinity);
  const s = Number.isFinite(scale) ? scale : 0;
  const placed: Placed[] = points.map(({ location, px, py }) => ({
    location,
    x: 50 + (((px - (xMin + xMax) / 2) * s) / aspect) * 100,
    y: 50 - (py - (yMin + yMax) / 2) * s * 100,
  }));
  return { placed, unplaced };
}

type MapProps = {
  name: string;
  placed: Placed[];
  label: (locationId: string) => string;
  bandOf: (locationId: string) => DangerBand | null;
  onSelect: (locationId: string, opener: HTMLElement) => void;
  /** Shown with the caption (beside the map on desktop): the locations it can't place. */
  children?: React.ReactNode;
};

/** Each placed location is a button with its band shape; colour only reinforces the shape and text. */
export function LocationMap({ name, placed, label, bandOf, onSelect, children }: MapProps) {
  if (placed.length === 0) return children; // nothing to place: no empty frame, only the unplaced list
  return (
    // Desktop: the capped map leaves room beside it for its caption, so the ranking starts higher (W4-03 #5).
    <div className="grid gap-1 lg:grid-cols-[auto_minmax(0,1fr)] lg:items-end lg:gap-x-4">
      {/* Desktop caps the height (keeping 16:9) so ranks #1–#3 sit in the first view (W4-03 ux-critic #5). */}
      <div role="group" aria-label={`Map of ${name}`} className="relative aspect-video w-full overflow-hidden rounded-lg border border-border bg-muted/30 lg:h-[clamp(8rem,calc(100svh-36rem),22rem)] lg:w-auto lg:max-w-full">
        {placed.map(({ location, x, y }) => {
          const band = bandOf(location.location_id);
          const text = `${label(location.location_id)}, ${band ? BAND_LABEL[band] : "not ranked"}`;
          return (
            <button key={location.location_id} type="button" aria-label={text} title={text} style={{ left: `${x}%`, top: `${y}%` }}
              className="group absolute grid size-6 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring"
              onClick={(event) => onSelect(location.location_id, event.currentTarget)}>
              {band ? <DangerBandGlyph band={band} size={16} /> : (
                <svg width={12} height={12} viewBox="0 0 12 12" aria-hidden="true"><rect x="1.5" y="1.5" width="9" height="9" fill="var(--pp-surface)" stroke="var(--pp-ink-muted)" strokeWidth="1.5" /></svg>
              )}
              {/* W4-03 ux-critic #5: a keyboard-focused marker names its site; it opens toward the map's centre so the frame never clips it. */}
              <span aria-hidden="true" className={cn("pointer-events-none absolute hidden whitespace-nowrap rounded-md border border-border bg-popover px-1.5 py-0.5 text-xs text-popover-foreground shadow-sm group-focus-visible:block",
                x < 50 ? "left-0" : "right-0", y > 70 ? "bottom-full mb-1" : "top-full mt-1")}>{label(location.location_id)}</span>
            </button>
          );
        })}
      </div>
      <div className="grid content-end gap-2">
        <p className="text-xs text-muted-foreground">Placed from each location&apos;s coordinates on a schematic projection, with no basemap. A square marks a location that is not ranked.</p>
        {children}
      </div>
    </div>
  );
}
