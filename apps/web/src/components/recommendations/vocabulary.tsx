import { CalendarClock, CheckCircle2, CircleDashed, CircleSlash, ShieldCheck, TriangleAlert } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDay, METHOD_LABEL, nativeStatusLabel, outcomeLabel, replayLabel, type MethodOutcome } from "./model";

// Semantic vocabulary for this screen (ART-DIRECTION.md), built on tokens only. Status always reads as
// text plus a shape; colour is supplementary. Local copies: components/overview is being edited (PP-52).

type Tone = "simulated" | "live" | "degraded";
const PILL: Record<Tone, { pill: string; dot: string }> = {
  simulated: { pill: "border-pp-teal/30 bg-pp-teal-soft", dot: "bg-pp-teal" },
  live: { pill: "border-border bg-card", dot: "bg-pp-forecast" },
  degraded: { pill: "border-pp-danger/50 bg-card", dot: "bg-pp-danger" },
};

/** ProvenancePill: where the displayed numbers come from. */
export function ProvenancePill({ children, tone = "simulated", className }: { children: React.ReactNode; tone?: Tone; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap text-foreground", PILL[tone].pill, className)}>
      <span aria-hidden="true" className={cn("size-1.5 rounded-full", PILL[tone].dot)} />
      {children}
    </span>
  );
}

/** SolverStatus: outcome, native status and independent replay for one method, in words. */
export function SolverStatus({ method, showMethod = false, className }: { method: MethodOutcome; showMethod?: boolean; className?: string }) {
  const verified = method.outcome === "VERIFIED" && method.verification?.passed === true;
  const Icon = verified ? ShieldCheck : method.outcome === "VERIFIED" ? TriangleAlert : CircleSlash;
  return (
    <span data-solver-status={method.outcome} className={cn("inline-flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-foreground", className)}>
      <Icon aria-hidden="true" className={cn("size-3.5 shrink-0", verified ? "text-pp-teal" : "text-pp-danger")} />
      {showMethod && <span className="font-semibold">{METHOD_LABEL[method.method]}</span>}
      <span>{outcomeLabel(method.outcome)}</span>
      <span aria-hidden="true" className="text-muted-foreground">·</span>
      <span>Solver: {nativeStatusLabel(method.native_status)}</span>
      <span aria-hidden="true" className="text-muted-foreground">·</span>
      <span>Independent replay: {replayLabel(method)}</span>
    </span>
  );
}

/** ConstraintBadge: a hard constraint, claimed only as far as independent replay passed. */
export function ConstraintBadge({ label, passed }: { label: string; passed: boolean }) {
  return (
    <li className={cn("flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-sm text-foreground", passed ? "border-pp-teal/40 bg-pp-teal-soft/50" : "border-dashed border-border")}>
      {passed ? <CheckCircle2 aria-hidden="true" className="size-4 shrink-0 text-pp-teal" /> : <CircleDashed aria-hidden="true" className="size-4 shrink-0 text-pp-neutral" />}
      <span className="font-medium">{label}</span>
      <span className="text-xs text-muted-foreground">{passed ? "passed independent replay" : "not verified"}</span>
    </li>
  );
}

/** Q-54-1: display-only dated tag; no priority score. */
export function DeficitTag({ day }: { day: string | null }) {
  return day ? (
    <span className="inline-flex items-center gap-1 rounded-full border border-pp-danger/50 bg-card px-2 py-0.5 text-xs font-medium whitespace-nowrap text-foreground">
      <CalendarClock aria-hidden="true" className="size-3 text-pp-danger" />Deficit {formatDay(day)}
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-2 py-0.5 text-xs whitespace-nowrap text-muted-foreground">
      <CheckCircle2 aria-hidden="true" className="size-3 text-pp-teal" />No deficit in window
    </span>
  );
}

/** BeforeAfterMetric: baseline → plan for one product; "Unavailable" when the baseline was not saved. */
export function BeforeAfterMetric({ metric, product, label, before, after }: { metric: string; product: string; label: string; before: string | null; after: string | null }) {
  return (
    <div data-metric={metric} data-product={product} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 border-b border-border py-1.5 last:border-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-right text-sm font-medium text-foreground tabular-nums">
        {`${before ?? "Unavailable"} → ${after ?? "Unavailable"}`}
      </dd>
    </div>
  );
}

type NoticeTone = "info" | "warning" | "danger";
/** State notice row: a status region unless it is an error. */
export function Notice({ kind, tone = "info", title, children, role }: { kind: string; tone?: NoticeTone; title: string; children?: React.ReactNode; role?: "status" | "alert" }) {
  const Icon = tone === "info" ? CircleDashed : TriangleAlert;
  return (
    <div data-rec-notice={kind} role={role ?? (tone === "danger" ? "alert" : "status")}
      className={cn("flex items-start gap-2.5 rounded-lg border bg-card px-3 py-2.5 text-sm text-foreground",
        tone === "danger" ? "border-pp-danger" : tone === "warning" ? "border-pp-warning" : "border-border")}>
      <Icon aria-hidden="true" className={cn("mt-0.5 size-4 shrink-0", tone === "danger" ? "text-pp-danger" : tone === "warning" ? "text-pp-warning" : "text-pp-neutral")} />
      <div className="grid min-w-0 gap-1">
        <p className="font-semibold">{title}</p>
        {children && <div className="grid gap-1 text-sm text-foreground">{children}</div>}
      </div>
    </div>
  );
}

export const LINK = "font-medium text-foreground underline underline-offset-2 outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm";
