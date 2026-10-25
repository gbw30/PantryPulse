import { cn } from "@/lib/utils";

type Tone = "live" | "fixture" | "degraded";

const TONE: Record<Tone, { pill: string; dot: string }> = {
  live: { pill: "border-pp-teal/30 bg-pp-teal-soft", dot: "bg-pp-teal" },
  fixture: { pill: "border-border bg-muted", dot: "bg-pp-neutral" },
  degraded: { pill: "border-pp-danger/50 bg-card", dot: "bg-pp-danger" },
};

/** ProvenancePill: names where displayed numbers come from. Text in ink; the dot and tone are supplementary. */
export function ProvenancePill({ children, className, tone = "live" }: { children: React.ReactNode; className?: string; tone?: Tone }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap text-foreground", TONE[tone].pill, className)}>
      <span aria-hidden="true" className={cn("size-1.5 rounded-full", TONE[tone].dot)} />
      {children}
    </span>
  );
}
