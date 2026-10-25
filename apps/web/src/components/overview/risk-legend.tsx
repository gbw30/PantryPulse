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
export function RiskLegend({ context, className, style, ref }: { context: string; className?: string; style?: React.CSSProperties; ref?: React.Ref<HTMLDivElement> }) {
  return (
    <div ref={ref} data-legend-card className={cn("rounded-xl border border-border bg-card/95 px-3.5 py-2.5 text-foreground shadow-sm", className)} style={style}>
      <p className="text-xs">
        <span className="font-semibold">Site status</span>
        <span className="text-muted-foreground"> · {context}</span>
      </p>
      <ul aria-label="Site status legend" className="mt-1.5 grid grid-cols-1 gap-x-4 gap-y-1 text-[13px] sm:grid-cols-2 lg:grid-cols-[repeat(3,auto)]">
        {ROWS.map((row) => (
          <li key={row.status} className="flex items-center gap-1.5 whitespace-nowrap">
            <StatusGlyph status={row.status} />
            <span className="font-medium">{STATUS_LABEL[row.status]}</span>
            <span aria-hidden="true" className="text-xs text-muted-foreground">{row.meaning}</span>
            <span className="sr-only">: {row.full}</span>
          </li>
        ))}
      </ul>
      <p className="mt-1.5 flex items-start gap-1.5 border-t border-border pt-1.5 text-xs text-muted-foreground">
        <svg width="22" height="12" viewBox="0 0 22 12" className="mt-0.5 shrink-0" aria-hidden="true">
          <path d="M1 10 C 9 10, 13 2, 21 2" fill="none" stroke="var(--pp-ink-muted)" strokeOpacity="0.7" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        <span><span className="font-medium text-foreground">Supply link</span>: the hub can send to this pantry; not a planned route or shipment</span>
      </p>
    </div>
  );
}
