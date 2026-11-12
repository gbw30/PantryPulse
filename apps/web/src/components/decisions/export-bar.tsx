import { useId } from "react";
import Link from "next/link";
import { NO_INBOUND } from "@/components/shell/network-switcher";
import { Button } from "@/components/ui/button";
import type { Schema } from "@/lib/planning-api";

export const SIMULATED_NOTE = "simulated plan; no stock was reserved or moved";

/** The frozen scenario's notes (V1-SPEC §6.1), plus "no scheduled deliveries provided" when it had no inbound.csv. */
export function PlanNotes({ saved }: { saved: Schema["SavedComparisonV3"] }) {
  const id = useId();
  const notes = [...saved.assumptions, ...(saved.inbound_file_provided ? [] : [NO_INBOUND])];
  if (notes.length === 0) return null;
  return (
    <div className="grid gap-0.5 text-xs">
      <p id={id} className="font-medium">Plan notes</p>
      <ul aria-labelledby={id} className="ml-4 list-disc text-muted-foreground">{notes.map((note) => <li key={note}>{note}</li>)}</ul>
    </div>
  );
}

const actions = (n: number) => `${n} action${n === 1 ? "" : "s"}`;

type Props = {
  total: number;
  count: number;
  busy: boolean;
  printHref: string;
  /** Saves the selection for the print page; runs before the link navigates. */
  onPrint: () => void;
  onExport: () => void;
  onSelectAll: () => void;
  onClear: () => void;
};

/** Choose actions, then export the server's CSV or open the print page for the same rows. */
export function ExportBar({ total, count, busy, printHref, onPrint, onExport, onSelectAll, onClear }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-card px-3 py-2">
      <Button type="button" variant="outline" size="sm" disabled={count === total} onClick={onSelectAll}>Select all</Button>
      <Button type="button" variant="outline" size="sm" disabled={count === 0} onClick={onClear}>Clear</Button>
      {/* Busy stays focusable (aria-disabled): disabling the focused button would drop keyboard focus to the page. */}
      <Button type="button" size="sm" disabled={count === 0} aria-disabled={busy || undefined} className="aria-disabled:opacity-50"
        onClick={busy ? undefined : onExport}>Export CSV ({actions(count)})</Button>
      {count > 0
        ? <Link href={printHref} onClick={onPrint} className="text-sm font-medium underline underline-offset-2 outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm">Print page ({actions(count)})</Link>
        : <span className="text-xs text-muted-foreground">Select actions to export or print.</span>}
      <span className="text-xs text-muted-foreground sm:ml-auto">{SIMULATED_NOTE}</span>
    </div>
  );
}
