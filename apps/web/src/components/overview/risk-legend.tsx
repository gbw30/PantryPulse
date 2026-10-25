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

/** RiskLegend: shape, label and a one-line meaning for each status, for one product and day. */
export function RiskLegend({ context, className, style, ref }: { context: string; className?: string; style?: React.CSSProperties; ref?: React.Ref<HTMLDivElement> }) {
  return (
    <div ref={ref} className={cn("rounded-xl border border-border bg-card/95 px-3.5 py-2 text-foreground shadow-sm", className)} style={style}>
      <p className="text-xs">
        <span className="font-semibold">Site status</span>
        <span className="text-muted-foreground"> · {context}</span>
      </p>
      <ul aria-label="Site status legend" className="mt-1 flex flex-col gap-0.5 text-[13px] md:flex-row md:flex-wrap md:gap-x-4">
        {ROWS.map((row) => (
          <li key={row.status} className="flex items-center gap-1.5">
            <StatusGlyph status={row.status} />
            <span className="font-medium">{STATUS_LABEL[row.status]}</span>
            <span aria-hidden="true" className="text-xs text-muted-foreground">{row.meaning}</span>
            <span className="sr-only">: {row.full}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
