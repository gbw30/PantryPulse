import { cn } from "@/lib/utils";
import { StatusGlyph } from "./status-glyph";
import { STATUS_LABEL } from "./status";
import type { MarkerStatus } from "./types";

// Display-only deficit-date definitions for the selected product and day (not solver policy).
const ROWS: { status: MarkerStatus; meaning: string }[] = [
  { status: "shortfall", meaning: "Projected unmet units on the selected day" },
  { status: "watch", meaning: "No unmet on the selected day; a projected deficit later in the horizon" },
  { status: "covered", meaning: "No projected unmet from the selected day through the horizon" },
  { status: "not_evaluated", meaning: "No projection or insufficient data; never shown as covered" },
  { status: "hub", meaning: "Distribution hub; no beneficiary status" },
];

/** RiskLegend: shape + label for each status, with the product/day it applies to. */
export function RiskLegend({ context, className, style }: { context: string; className?: string; style?: React.CSSProperties }) {
  return (
    <div className={cn("flex flex-wrap items-center gap-x-4 gap-y-1.5 rounded-xl border border-border bg-card/95 px-3.5 py-2 text-foreground shadow-sm", className)} style={style}>
      <p className="text-xs">
        <span className="font-semibold">Site status</span>
        <span className="text-muted-foreground"> · {context}</span>
      </p>
      <ul aria-label="Site status legend" className="flex flex-wrap gap-x-4 gap-y-1.5 text-[13px]">
        {ROWS.map((row) => (
          <li key={row.status} className="flex items-center gap-1.5" title={row.meaning}>
            <StatusGlyph status={row.status} />
            <span>{STATUS_LABEL[row.status]}</span>
            <span className="sr-only">: {row.meaning}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
