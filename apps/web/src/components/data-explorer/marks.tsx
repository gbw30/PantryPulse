import { cn } from "@/lib/utils";
import { STATUS_LABEL } from "./format";
import type { MarkStatus } from "./types";

// Shape carries status alongside colour, matching the Overview legend: Shortfall ◆, Watch ▲,
// Covered ●, Not evaluated ◌ (dashed ring), Hub ■.
export function StatusGlyph({ status, size = 14, className }: { status: MarkStatus; size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" className={cn("shrink-0", className)}>
      {status === "shortfall" && <path d="M8 1 L15 8 L8 15 L1 8 Z" fill="var(--pp-danger)" stroke="var(--pp-surface)" strokeWidth="1" />}
      {status === "watch" && <path d="M8 1.5 L15 14.5 H1 Z" fill="var(--pp-warning)" stroke="var(--pp-surface)" strokeWidth="1" strokeLinejoin="round" />}
      {status === "covered" && <circle cx="8" cy="8" r="6.5" fill="var(--pp-teal)" stroke="var(--pp-surface)" strokeWidth="1" />}
      {status === "not_evaluated" && <circle cx="8" cy="8" r="6" fill="var(--pp-surface)" stroke="var(--pp-neutral)" strokeWidth="2" strokeDasharray="2.6 2" />}
      {status === "hub" && <rect x="2" y="2" width="12" height="12" rx="1.5" fill="var(--pp-ink)" stroke="var(--pp-surface)" strokeWidth="1" />}
    </svg>
  );
}

/** ConstraintBadge-style status chip: glyph + text in ink; colour is only on the shape and border. */
export function StatusChip({ status, children, className }: { status: MarkStatus; children?: React.ReactNode; className?: string }) {
  const border = status === "shortfall" ? "border-pp-danger/60" : status === "watch" ? "border-pp-warning/70" : status === "covered" ? "border-pp-teal/50" : "border-border";
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-md border bg-card px-2 py-0.5 text-xs font-medium whitespace-nowrap text-foreground", border, className)}>
      <StatusGlyph status={status} size={12} />
      {children ?? STATUS_LABEL[status]}
    </span>
  );
}

type Tone = "live" | "fixture" | "degraded";
const TONE: Record<Tone, { pill: string; dot: string }> = {
  live: { pill: "border-pp-teal/30 bg-pp-teal-soft", dot: "bg-pp-teal" },
  fixture: { pill: "border-border bg-muted", dot: "bg-pp-neutral" },
  degraded: { pill: "border-pp-warning bg-card", dot: "bg-pp-warning" },
};

/** ProvenancePill: where the numbers on screen come from. Text in ink; dot and tone are supplementary. */
export function ProvenancePill({ children, className, tone = "live", wrap = false }: { children: React.ReactNode; className?: string; tone?: Tone; wrap?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium text-foreground", wrap ? "rounded-lg" : "whitespace-nowrap", TONE[tone].pill, className)}>
      <span aria-hidden="true" className={cn("size-1.5 shrink-0 rounded-full", TONE[tone].dot)} />
      <span className="min-w-0">{children}</span>
    </span>
  );
}
