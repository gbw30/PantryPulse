import { cn } from "@/lib/utils";
import { StatusGlyph } from "./status-glyph";
import { STATUS_LABEL } from "./status";
import type { MarkerStatus } from "./types";

// Display-only deficit-date definitions for the selected product and day (not solver policy).
// Short meanings stay visible; the screen-reader text spells out the full definition.
const ROWS: { status: MarkerStatus; meaning: string; full: string }[] = [
  { status: "shortfall", meaning: "unmet on this day", full: "projected unmet units on the selected day" },
  { status: "watch", meaning: "deficit later", full: "no unmet on the selected day, a projected deficit later in the horizon" },
  { status: "covered", meaning: "no unmet ahead", full: "no projected unmet from the selected day through the horizon" },
  { status: "not_evaluated", meaning: "no projection", full: "no projection or insufficient data, never shown as covered" },
  { status: "hub", meaning: "source, no status", full: "distribution hub with no beneficiary status" },
];

/**
 * RiskLegend: a compact card with shape, label and a one-line meaning for each status (two rows on
 * desktop), plus the supply-link key. Supply links show where the hub can send, never a planned route.
 */
export function RiskLegend({ context, className, style, ref, grip, lifted = false }: { context: string; className?: string; style?: React.CSSProperties; ref?: React.Ref<HTMLDivElement>; grip?: React.ReactNode; lifted?: boolean }) {
  return (
    // An obstacle for dropped map nodes (PP-52); on narrow layouts it sits above the map and never overlaps.
    <div ref={ref} data-legend-card data-atlas-obstacle className={cn("rounded-xl border border-border bg-card/95 px-3.5 py-2 text-foreground md:py-2.5 transition-shadow duration-150", lifted ? "shadow-xl ring-1 ring-primary/40" : "shadow-sm", className)} style={style}>
      <div className="flex items-center gap-1.5">
        {grip && <span className="-my-1 -ml-1.5 inline-flex">{grip}</span>}
        <p className="text-xs">
          <span className="font-semibold">Site status</span>
          <span className="text-muted-foreground"> · {context}</span>
        </p>
      </div>
      <ul aria-label="Site status legend" className="mt-1 grid grid-cols-1 gap-x-4 gap-y-0.5 text-[13px] md:mt-1.5 md:gap-y-1 sm:grid-cols-2 lg:grid-cols-[repeat(3,auto)]">
        {ROWS.map((row) => (
          <li key={row.status} className="flex items-center gap-1.5 whitespace-nowrap">
            <StatusGlyph status={row.status} />
            <span className="font-medium">{STATUS_LABEL[row.status]}</span>
            <span aria-hidden="true" className="text-xs text-muted-foreground">{row.meaning}</span>
            <span className="sr-only">: {row.full}</span>
          </li>
        ))}
      </ul>
      <p className="mt-1 flex items-start gap-1.5 border-t border-border pt-1 text-xs md:mt-1.5 md:pt-1.5 text-muted-foreground">
        <svg width="22" height="12" viewBox="0 0 22 12" className="mt-0.5 shrink-0" aria-hidden="true">
          <path d="M1 10 C 9 10, 13 2, 21 2" fill="none" stroke="var(--pp-ink-muted)" strokeOpacity="0.7" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        <span><span className="font-medium text-foreground">Supply link</span>: the hub can send to this pantry; not a planned route or shipment</span>
      </p>
    </div>
  );
}

export type DangerBand = "high" | "medium" | "low";

// V1-SPEC §6.6 danger bands: shape and text carry the band; colour only reinforces it.
export const DANGER_BANDS: { band: DangerBand; label: string; meaning: string }[] = [
  { band: "high", label: "High danger", meaning: "a large share projected short" },
  { band: "medium", label: "Medium danger", meaning: "a moderate share projected short" },
  // The API's band() (apps/api/app/services/danger/ranking.py) puts every score under MEDIUM (0.20) in low, 0 included.
  { band: "low", label: "Low danger", meaning: "under 20% projected short (may be none)" },
];

const BAND_SHAPE: Record<DangerBand, "diamond" | "triangle" | "circle"> = { high: "diamond", medium: "triangle", low: "circle" };

export function DangerBandGlyph({ band, size = 14 }: { band: DangerBand; size?: number }) {
  const shape = BAND_SHAPE[band];
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" data-band-shape={shape} className="shrink-0">
      {shape === "diamond" && <path d="M8 1 L15 8 L8 15 L1 8 Z" fill="var(--pp-danger)" stroke="var(--pp-surface)" strokeWidth="1" />}
      {shape === "triangle" && <path d="M8 1.5 L15 14.5 H1 Z" fill="var(--pp-warning)" stroke="var(--pp-surface)" strokeWidth="1" strokeLinejoin="round" />}
      {shape === "circle" && <circle cx="8" cy="8" r="5.5" fill="var(--pp-surface)" stroke="var(--pp-ink-muted)" strokeWidth="2" />}
    </svg>
  );
}

export function DangerLegend({ mode }: { mode: "PANTRY" | "RETAIL" }) {
  return (
    <div className="grid gap-1 text-xs">
      <ul aria-label="Danger bands" className="flex flex-wrap gap-x-4 gap-y-1">
        {DANGER_BANDS.map((b) => (
          <li key={b.band} className="flex items-center gap-1.5">
            <DangerBandGlyph band={b.band} />
            <span className="font-medium">{b.label}</span>
            {/* A Retail score can come from expiry (V1-SPEC §6.6), so its bands never read as shortage alone. */}
            <span className="text-muted-foreground">{mode === "RETAIL" ? b.meaning.replace("projected short", "projected short or expiring unsold") : b.meaning}</span>
          </li>
        ))}
      </ul>
      <p className="text-muted-foreground">
        {mode === "RETAIL"
          ? "Score: the worst product's share of 7-day sales projected unmet, or of its stock projected to expire unsold, whichever is higher; the reason says which."
          : "Score: the worst product's share of 7-day demand projected unmet. Ties go to the earlier first deficit."}
        {" "}Units are never added across products.
      </p>
    </div>
  );
}
