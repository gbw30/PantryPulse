import { CircleDashed, ShieldCheck } from "lucide-react";
import { formatUnits } from "@/components/overview/danger-ranking";
import type { NetworkMode } from "@/lib/mode-vocabulary";
import type { Schema } from "@/lib/planning-api";

type Action = Schema["DecisionAction"];
type Decisions = Schema["DecisionActions"];

const day = (iso: string) => new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });

/** "Nov 6–12 (7 days)": inclusive local days of the frozen scenario (W5-L02). */
export function periodText(start: string, end: string) {
  const days = Math.round((Date.parse(end) - Date.parse(start)) / 86_400_000) + 1;
  const [a, b] = [day(start), day(end)];
  const range = start === end ? a : a.split(" ")[0] === b.split(" ")[0] ? `${a}–${b.split(" ")[1]}` : `${a}–${b}`;
  return `${range} (${days} day${days === 1 ? "" : "s"})`;
}

/** W5-UI02.3: the plan is built for its window only; the days after it are not planned. */
export function planCovers(decisions: Decisions, mode: NetworkMode) {
  const after = mode === "RETAIL" ? "lost sales after" : "unmet need after";
  return `Plan covers ${periodText(decisions.plan_window_start, decisions.plan_window_end)} only; ${after} ${day(decisions.plan_window_end)} ${mode === "RETAIL" ? "are" : "is"} not planned.`;
}

/** The period every effect quantity covers: all forecast days, which can be longer than the plan's window. */
export const effectPeriod = (decisions: Decisions) => periodText(decisions.effect_window_start, decisions.effect_window_end);

/** "40 cases lower" / "unchanged", in the product's unit. A delta is this plan minus the same plan without this one transfer. */
function change(delta: number, unit: string) {
  return delta === 0 ? "unchanged" : `${formatUnits(Math.abs(delta), unit)} ${delta < 0 ? "lower" : "higher"}`;
}

function usdChange(delta: string) {
  const n = Number(delta);
  return n === 0 ? "unchanged" : `$${Math.abs(n).toFixed(2)} ${n < 0 ? "lower" : "higher"}`;
}

/**
 * V1-SPEC §6.5 effect lines. A quantity is `dated`: it names the period it covers (W5-UI02.3). There is no USD
 * line in Pantry mode, and "USD effect unavailable" is not a quantity.
 */
export function effectLines(action: Action, mode: NetworkMode, usdUnavailableReason: string | null) {
  const { effect } = action;
  const short = mode === "RETAIL" ? "lost sales" : "unmet need";
  const lines = [
    { text: `Receiver ${short}: ${change(effect.receiver_unmet_delta, effect.unit)}`, dated: true },
    { text: `Sender ${short}: ${change(effect.sender_unmet_delta, effect.unit)}`, dated: true },
    { text: `Expired: ${change(effect.expired_delta, effect.unit)}`, dated: true },
  ];
  if (mode === "RETAIL") {
    lines.push(effect.usd_delta !== null
      // price × (Δunmet + Δexpired), the CSV's wording: neither the objective nor a loss.
      ? { text: `Dollar value of the units changed (USD): ${usdChange(effect.usd_delta)}`, dated: true }
      : { text: `USD effect unavailable: ${usdUnavailableReason ?? "this plan was compared in units"}`, dated: false });
  }
  return lines;
}

/** V5 §14.1: a proven binding constraint vs an inferred reason, as text plus a shape. */
export function ExplanationBadge({ kind }: { kind: Action["explanation_kind"] }) {
  const proven = kind === "proven_binding";
  const Icon = proven ? ShieldCheck : CircleDashed;
  return (
    <span className="inline-flex items-center gap-1.5 justify-self-start rounded-full border border-border bg-card px-2 py-0.5 text-xs font-medium text-foreground">
      <Icon aria-hidden="true" className={proven ? "size-3.5 text-pp-teal" : "size-3.5 text-pp-neutral"} />
      {proven ? "Proven: binding constraint" : "Inferred reason"}
    </span>
  );
}

type Props = {
  action: Action;
  mode: NetworkMode;
  usdUnavailableReason: string | null;
  /** effectPeriod(decisions): "Nov 6–12 (7 days)". */
  period: string;
  selected: boolean;
  onSelectedChange: (selected: boolean) => void;
};

const PART = "text-xs font-semibold tracking-wide text-muted-foreground uppercase";

/** One suggested transfer as Action, Why and Effect, with its own export checkbox. */
export function ActionCard({ action, mode, usdUnavailableReason, period, selected, onSelectedChange }: Props) {
  const lines = effectLines(action, mode, usdUnavailableReason);
  const id = `action-${action.id}`;
  return (
    <article aria-labelledby={`${id}-text`} className="grid gap-3 rounded-lg border border-border bg-card p-3 text-sm">
      <label className="inline-flex items-center gap-2 justify-self-start text-xs font-medium">
        <input type="checkbox" className="size-4 accent-pp-teal" checked={selected} onChange={(e) => onSelectedChange(e.target.checked)} />
        Include in export
      </label>
      <section className="grid gap-1">
        <h3 className={PART}>Action</h3>
        <p id={`${id}-text`} className="font-medium">{action.action_text}</p>
      </section>
      <section className="grid gap-1">
        <h3 className={PART}>Why</h3>
        <p>{action.why_text}</p>
        <ExplanationBadge kind={action.explanation_kind} />
      </section>
      <section className="grid gap-1">
        <h3 id={`${id}-effect`} className={PART}>Effect</h3>
        <ul aria-labelledby={`${id}-effect`} className="grid gap-0.5">
          {lines.map((line) => (
            <li key={line.text}>
              <span>{line.text}</span>
              {line.dated && <span className="text-muted-foreground"> over {period}</span>}
            </li>
          ))}
        </ul>
      </section>
    </article>
  );
}
