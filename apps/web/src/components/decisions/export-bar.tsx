import Link from "next/link";
import { Button } from "@/components/ui/button";

export const SIMULATED_NOTE = "simulated plan; no stock was reserved or moved";

const actions = (n: number) => `${n} action${n === 1 ? "" : "s"}`;

type Props = {
  total: number;
  count: number;
  busy: boolean;
  printHref: string;
  onExport: () => void;
  onSelectAll: () => void;
  onClear: () => void;
};

/** Choose actions, then export the server's CSV or open the print page for the same rows. */
export function ExportBar({ total, count, busy, printHref, onExport, onSelectAll, onClear }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-card px-3 py-2">
      <Button type="button" variant="outline" size="sm" disabled={count === total} onClick={onSelectAll}>Select all</Button>
      <Button type="button" variant="outline" size="sm" disabled={count === 0} onClick={onClear}>Clear</Button>
      <Button type="button" size="sm" disabled={count === 0 || busy} onClick={onExport}>Export CSV ({actions(count)})</Button>
      {count > 0
        ? <Link href={printHref} className="text-sm font-medium underline underline-offset-2 outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm">Print page ({actions(count)})</Link>
        : <span className="text-xs text-muted-foreground">Select actions to export or print.</span>}
      <span className="text-xs text-muted-foreground sm:ml-auto">{SIMULATED_NOTE}</span>
    </div>
  );
}
