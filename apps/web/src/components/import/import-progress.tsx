import type { ImportStatus } from "@/lib/network-api";

export const NO_INBOUND = "no scheduled deliveries provided";

const PHASE_LABEL: Record<ImportStatus["phase"], string> = {
  uploading: "Uploading files", staging: "Reading files", validating: "Checking every row",
  committing: "Saving the network", done: "Import finished", failed: "Import failed",
};

const n = (value: number) => value.toLocaleString("en-US");

/** In-progress phase and progress, then the finished summary. A failed import is shown by ImportErrors. */
export function ImportProgress({ status }: { status: ImportStatus }) {
  if (status.phase === "failed") return null;
  if (status.phase !== "done") {
    const progress = status.progress;
    return (
      <div role="status" className="grid gap-2 rounded-xl border border-border bg-card p-4 text-sm">
        <p className="font-medium">
          {PHASE_LABEL[status.phase]}
          {progress && `: ${n(progress.done)}${progress.total !== null ? ` of ${n(progress.total)}` : ""} ${progress.unit}`}
        </p>
        {progress?.total ? <progress className="h-2 w-full accent-pp-teal" max={progress.total} value={progress.done} aria-hidden="true" /> : null}
        <p className="text-xs text-muted-foreground">Nothing is saved until every file passes.</p>
      </div>
    );
  }

  const hasInbound = status.files.some((file) => file.name === "inbound");
  return (
    <section aria-labelledby="import-done-heading" className="grid gap-3 rounded-xl border border-border bg-card p-4 text-sm">
      <h3 id="import-done-heading" className="text-base font-semibold">Import finished</h3>
      <p>
        Saved as a new dataset version{status.as_of_date ? `, stock snapshot date ${status.as_of_date}` : ""}.
        Imported files: {status.files.map((file) => `${file.name}.csv`).join(", ")}.
      </p>
      <p>Scheduled deliveries: <span>{hasInbound ? "from inbound.csv" : NO_INBOUND}</span></p>
      {status.outside_horizon_inbound.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border" role="group" aria-label="Scrollable list of deliveries outside the horizon" tabIndex={0}>
          <table className="w-full min-w-[32rem] border-collapse text-left">
            <caption className="px-3 py-2 text-left font-medium">Deliveries outside the 7-day horizon — kept, not planned</caption>
            <thead className="bg-muted/60 text-xs text-muted-foreground">
              <tr>{["Line", "Location", "Product", "Quantity", "Arrival date"].map((h) => <th key={h} scope="col" className="px-3 py-2 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {status.outside_horizon_inbound.map((row) => (
                <tr key={`${row.line}`} className="border-t border-border">
                  <td className="px-3 py-2 tabular-nums">{row.line}</td>
                  <td className="px-3 py-2">{row.location_id}</td>
                  <td className="px-3 py-2">{row.product_id}</td>
                  <td className="px-3 py-2 tabular-nums">{n(row.quantity)}</td>
                  <td className="px-3 py-2 tabular-nums">{row.arrival_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {hasInbound && status.outside_horizon_inbound.length === 0 && <p className="text-muted-foreground">Every scheduled delivery falls inside the 7-day horizon.</p>}
    </section>
  );
}
