import { CircleDashed, ShieldCheck } from "lucide-react";
import { formatUnits } from "@/components/overview/danger-ranking";
import type { NetworkMode } from "@/lib/mode-vocabulary";
import type { Schema } from "@/lib/planning-api";

type Action = Schema["DecisionAction"];

/** "40 units lower" / "unchanged". A delta is this plan minus the same plan without this one transfer. */
function change(delta: number) {
  return delta === 0 ? "unchanged" : `${formatUnits(Math.abs(delta), "unit")} ${delta < 0 ? "lower" : "higher"}`;
}

function usdChange(delta: string) {
  const n = Number(delta);
  return n === 0 ? "unchanged" : `$${Math.abs(n).toFixed(2)} ${n < 0 ? "lower" : "higher"}`;
}

/** V1-SPEC §6.5 effect lines; `usd` is null when no USD line applies (Pantry plans are never in USD). */
export function effectLines(action: Action, mode: NetworkMode, usdUnavailableReason: string | null) {
  const { effect } = action;
  const short = mode === "RETAIL" ? "lost sales" : "unmet need";
  const usd = mode !== "RETAIL" ? null : effect.usd_delta !== null
    ? `Value lost (USD): ${usdChange(effect.usd_delta)}`
    : `USD effect unavailable: ${usdUnavailableReason ?? "this plan was compared in units"}`;
  return {
    receiver: `Receiver ${short}: ${change(effect.receiver_unmet_delta)}`,
    sender: `Sender ${short}: ${change(effect.sender_unmet_delta)}`,
    expired: `Expired: ${change(effect.expired_delta)}`,
    usd,
  };
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
  selected: boolean;
  onSelectedChange: (selected: boolean) => void;
};

const PART = "text-xs font-semibold tracking-wide text-muted-foreground uppercase";

/** One suggested transfer as Action, Why and Effect, with its own export checkbox. */
export function ActionCard({ action, mode, usdUnavailableReason, selected, onSelectedChange }: Props) {
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
        <h3 className={PART}>Effect</h3>
        <ul className="grid gap-0.5">
          <li>{lines.receiver}</li>
          <li>{lines.sender}</li>
          <li>{lines.expired}</li>
          {lines.usd && <li>{lines.usd}</li>}
        </ul>
        <p className="text-xs text-muted-foreground">Product {action.effect.product_id}; units as in the plan.</p>
      </section>
    </article>
  );
}
