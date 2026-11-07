import { Button } from "@/components/ui/button";
import type { ImportStatus } from "@/lib/network-api";

const n = (value: number) => value.toLocaleString("en-US");

/** A failed import: what failed and that nothing was saved, why, what to do, and every row to fix. */
export function ImportErrors({ status, onStartOver }: { status: ImportStatus; onStartOver: () => void }) {
  const failure = status.failure;
  const truncated = status.errors_truncated || status.error_count > status.errors.length;
  return (
    <div className="grid gap-3">
      <div role="alert" className="grid gap-2 rounded-xl border border-pp-danger/40 bg-card p-4 text-sm">
        <p className="text-base font-semibold">{failure?.message ?? "Import failed: nothing was saved."}</p>
        {failure?.reason && <p>{failure.reason}</p>}
        {failure && failure.next_steps.length > 0 && (
          <>
            <p className="font-medium">What to do</p>
            <ol className="ml-5 list-decimal space-y-1">{failure.next_steps.map((step) => <li key={step}>{step}</li>)}</ol>
          </>
        )}
        <Button variant="outline" className="h-10 justify-self-start" onClick={onStartOver}>Start a new import</Button>
      </div>
      {status.errors.length > 0 && (
        <div className="grid gap-2">
          {truncated && <p className="text-sm">Showing the first {n(status.errors.length)} of {n(status.error_count)} errors.</p>}
          <div className="max-h-[32rem] overflow-auto rounded-lg border border-border" role="group" aria-label="Scrollable list of rows to fix" tabIndex={0}>
            <table className="w-full min-w-[48rem] border-collapse text-left text-sm">
              <caption className="px-3 py-2 text-left font-medium">Rows to fix ({n(status.error_count)})</caption>
              <thead className="sticky top-0 bg-muted text-xs text-muted-foreground">
                <tr>{["File", "Line", "Column", "Value", "Problem", "How to fix"].map((h) => <th key={h} scope="col" className="px-3 py-2 font-medium">{h}</th>)}</tr>
              </thead>
              <tbody>
                {/* Rows hold no state, and file:line:column:code repeats when column is null, so the position is the key. */}
                {status.errors.map((error, index) => (
                  <tr key={index} className="border-t border-border align-top">
                    <td className="px-3 py-2"><code className="font-mono">{error.file}.csv</code></td>
                    <td className="px-3 py-2 tabular-nums">{error.line}</td>
                    <td className="px-3 py-2"><code className="font-mono">{error.column ?? "—"}</code></td>
                    <td className="px-3 py-2"><code className="font-mono">{error.value ?? ""}</code></td>
                    <td className="px-3 py-2">{error.reason}</td>
                    <td className="px-3 py-2">{error.fix}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
