import type { NetworkMode } from "@/lib/mode-vocabulary";
import type { Schema } from "@/lib/planning-api";
import { ActionCard, effectPeriod, planCovers } from "./action-card";

type Props = {
  decisions: Schema["DecisionActions"];
  mode: NetworkMode;
  usdUnavailableReason: string | null;
  selected: ReadonlySet<string>;
  onToggle: (id: string, selected: boolean) => void;
};

/** Every suggested action of one method result. Effects are shown one action at a time and never added up. */
export function ActionList({ decisions, mode, usdUnavailableReason, selected, onToggle }: Props) {
  return (
    <div className="grid gap-3">
      <p className="rounded-md border border-pp-warning bg-card px-3 py-2 text-sm font-medium">{decisions.non_additive_label}</p>
      <p className="text-sm">{planCovers(decisions, mode)}</p>
      {decisions.actions.length === 0 && <p className="text-sm text-muted-foreground">This method suggests no transfers.</p>}
      <div className="grid gap-3 xl:grid-cols-2">
        {decisions.actions.map((action) => (
          <ActionCard key={action.id} action={action} mode={mode} usdUnavailableReason={usdUnavailableReason} period={effectPeriod(decisions)}
            selected={selected.has(action.id)} onSelectedChange={(on) => onToggle(action.id, on)} />
        ))}
      </div>
    </div>
  );
}
