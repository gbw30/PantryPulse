"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Schema } from "@/lib/planning-api";
import { dataInputApi, describeError, feedbackOf, NONNEGATIVE, POSITIVE, useIntentKey, type CommandResult, type OperationalCatalog } from "./api";
import { describedBy, ErrorAlert, Field, ImportFeedbackTable, nativeSelect, SavedAlert } from "./shared";

// Demand-history and donation-coverage imports. Imports are atomic: the API saves all rows or none,
// and a rejection lists every bad row. Empty quantity cells stay null ("not reported"), never 0.

const CSV_HEADERS = "source_record_key,site_id,product_id,day,expected_revision,requested,fulfilled,unmet";

type DemandRowDraft = { source_record_key: string; site_id: string; product_id: string; day: string; expected_revision: string; requested: string; fulfilled: string; unmet: string };
type CoverageRowDraft = { site_id: string; product_id: string; day: string; complete: boolean; expected_revision: string };
const emptyDemandRow = (): DemandRowDraft => ({ source_record_key: "", site_id: "", product_id: "", day: "", expected_revision: "", requested: "", fulfilled: "", unmet: "" });
const emptyCoverageRow = (): CoverageRowDraft => ({ site_id: "", product_id: "", day: "", complete: true, expected_revision: "" });

const orNull = (value: string) => (value.trim() === "" ? null : value.trim());

function demandRowProblem(row: DemandRowDraft): string | null {
  if (!row.source_record_key.trim()) return "record key is required";
  if (!row.site_id || !row.product_id || !row.day) return "site, product and day are required";
  for (const field of ["requested", "fulfilled", "unmet"] as const) {
    const value = row[field].trim();
    if (value !== "" && !NONNEGATIVE.test(value)) return `${field} must be a whole number or empty (empty = not reported)`;
  }
  if (row.expected_revision.trim() !== "" && !POSITIVE.test(row.expected_revision.trim())) return "expected revision must be a positive whole number or empty";
  if (row.requested.trim() === "" && row.fulfilled.trim() === "" && row.unmet.trim() === "") return "at least one of requested, fulfilled, unmet";
  return null;
}

function ResultPanel({ result }: { result: CommandResult }) {
  const data = result.result as { accepted_count?: string; rows?: { site_id: string; product_id: string; day: string; revision: string }[] };
  return (
    <SavedAlert title={`Import saved — ${data.accepted_count ?? "?"} row(s) accepted`}>
      <p className="text-xs text-muted-foreground">Command {result.command_id}</p>
    </SavedAlert>
  );
}

export function ImportsSection({ catalog, coverage }: { catalog: OperationalCatalog; coverage: boolean }) {
  const [sourceId, setSourceId] = useState("");
  const [mode, setMode] = useState<"rows" | "csv" | "json">("rows");
  const [demandRows, setDemandRows] = useState<DemandRowDraft[]>([emptyDemandRow()]);
  const [coverageRows, setCoverageRows] = useState<CoverageRowDraft[]>([emptyCoverageRow()]);
  const [file, setFile] = useState<File | null>(null);
  const [jsonText, setJsonText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<CommandResult | null>(null);
  const key = useIntentKey();
  const title = coverage ? "Donation coverage" : "Demand history";
  const prefix = coverage ? "coverage" : "demand";
  const touched = <T,>(set: (updater: (rows: T[]) => T[]) => void) => (updater: (rows: T[]) => T[]) => { key.reset(); setResult(null); set(updater); };
  const editDemand = touched(setDemandRows);
  const editCoverage = touched(setCoverageRows);

  const rowProblems = coverage
    ? coverageRows.map((row) => (!row.site_id || !row.product_id || !row.day ? "site, product and day are required" : row.expected_revision.trim() !== "" && !POSITIVE.test(row.expected_revision.trim()) ? "expected revision must be a positive whole number or empty" : null))
    : demandRows.map(demandRowProblem);
  const rowsInvalid = !sourceId ? "Choose a data source." : rowProblems.some(Boolean) ? "Fix the marked rows." : "";
  const invalid = mode === "rows" ? rowsInvalid : mode === "csv" ? (!sourceId ? "Choose a data source." : !file ? "Choose a CSV file." : "") : (!sourceId ? "Choose a data source." : !jsonText.trim() ? "Paste the rows JSON." : "");

  async function submit() {
    if (busy || invalid) return;
    setBusy(true); setError(null); setResult(null);
    try {
      let value: CommandResult;
      if (mode === "csv") {
        value = await dataInputApi.importDemandCsv(sourceId, file as File, key.current());
      } else {
        let rows: unknown;
        if (mode === "json") {
          rows = JSON.parse(jsonText);
          if (!Array.isArray(rows)) throw new Error("JSON must be an array of rows");
        } else if (coverage) {
          rows = coverageRows.map((row) => ({ site_id: row.site_id, product_id: row.product_id, day: row.day, complete: row.complete, expected_revision: orNull(row.expected_revision) }));
        } else {
          rows = demandRows.map((row) => ({ source_record_key: row.source_record_key.trim(), site_id: row.site_id, product_id: row.product_id, day: row.day,
            expected_revision: orNull(row.expected_revision), requested: orNull(row.requested), fulfilled: orNull(row.fulfilled), unmet: orNull(row.unmet) }));
        }
        const body = { source_id: sourceId, rows };
        value = coverage ? await dataInputApi.importCoverage(body as Schema["CoverageImport"], key.current()) : await dataInputApi.importDemand(body as Schema["DemandImport"], key.current());
      }
      key.reset();
      setResult(value);
    } catch (e) {
      setError(e instanceof SyntaxError || (e instanceof Error && e.message.startsWith("JSON")) ? new Error("The pasted text is not a JSON array of rows.") : e);
    } finally { setBusy(false); }
  }

  const feedback = feedbackOf(error);
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title} import</CardTitle>
        <CardDescription>
          Up to 100 rows per import, all-or-nothing. {coverage ? "Coverage marks whether a day's donations are completely recorded for a site and product." : "Empty requested/fulfilled/unmet cells mean “not reported” and stay empty; they are never turned into 0."}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field id={`${prefix}-source`} label="Data source">
            <select id={`${prefix}-source`} className={nativeSelect} value={sourceId} onChange={(e) => { key.reset(); setResult(null); setSourceId(e.target.value); }}>
              <option value="">Choose a source</option>
              {catalog.data_sources.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.classification.toLowerCase()})</option>)}
            </select>
          </Field>
          <Field id={`${prefix}-mode`} label="Input method">
            <select id={`${prefix}-mode`} className={nativeSelect} value={mode} onChange={(e) => { key.reset(); setResult(null); setError(null); setMode(e.target.value as typeof mode); }}>
              <option value="rows">Row editor</option>
              {!coverage && <option value="csv">CSV file</option>}
              <option value="json">Paste JSON rows</option>
            </select>
          </Field>
        </div>

        {mode === "rows" && !coverage && (
          <div className="overflow-x-auto">
            <Table>
              <TableCaption>Quantities are whole units of the row&apos;s product; empty means not reported.</TableCaption>
              <TableHeader><TableRow>
                <TableHead>Record key</TableHead><TableHead>Site</TableHead><TableHead>Product</TableHead><TableHead>Day</TableHead><TableHead>Requested</TableHead><TableHead>Fulfilled</TableHead><TableHead>Unmet</TableHead><TableHead>Expected rev.</TableHead><TableHead><span className="sr-only">Remove</span></TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {demandRows.map((row, index) => (
                  <TableRow key={index}>
                    <TableCell><Input aria-label={`Row ${index + 1} record key`} className="w-36" value={row.source_record_key} onChange={(e) => editDemand((rows) => rows.map((r, i) => i === index ? { ...r, source_record_key: e.target.value } : r))} /></TableCell>
                    <TableCell><select aria-label={`Row ${index + 1} site`} className={nativeSelect + " w-40"} value={row.site_id} onChange={(e) => editDemand((rows) => rows.map((r, i) => i === index ? { ...r, site_id: e.target.value } : r))}><option value="">Site…</option>{catalog.sites.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></TableCell>
                    <TableCell><select aria-label={`Row ${index + 1} product`} className={nativeSelect + " w-40"} value={row.product_id} onChange={(e) => editDemand((rows) => rows.map((r, i) => i === index ? { ...r, product_id: e.target.value } : r))}><option value="">Product…</option>{catalog.products.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.base_unit})</option>)}</select></TableCell>
                    <TableCell><Input aria-label={`Row ${index + 1} day`} type="date" className="w-38" value={row.day} onChange={(e) => editDemand((rows) => rows.map((r, i) => i === index ? { ...r, day: e.target.value } : r))} /></TableCell>
                    {(["requested", "fulfilled", "unmet"] as const).map((field) => (
                      <TableCell key={field}><Input aria-label={`Row ${index + 1} ${field}`} inputMode="numeric" className="w-24" placeholder="not reported" value={row[field]} onChange={(e) => editDemand((rows) => rows.map((r, i) => i === index ? { ...r, [field]: e.target.value } : r))} /></TableCell>
                    ))}
                    <TableCell><Input aria-label={`Row ${index + 1} expected revision`} inputMode="numeric" className="w-24" placeholder="new day" value={row.expected_revision} onChange={(e) => editDemand((rows) => rows.map((r, i) => i === index ? { ...r, expected_revision: e.target.value } : r))} /></TableCell>
                    <TableCell><Button variant="outline" size="sm" disabled={demandRows.length === 1} onClick={() => editDemand((rows) => rows.filter((_, i) => i !== index))}>Remove<span className="sr-only"> row {index + 1}</span></Button></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {rowProblems.map((problem, index) => problem && <p key={index} className="text-xs font-medium">⚠ Row {index + 1}: {problem}</p>)}
            <Button variant="outline" size="sm" className="mt-2" disabled={demandRows.length >= 100} onClick={() => editDemand((rows) => [...rows, emptyDemandRow()])}>Add row</Button>
          </div>
        )}

        {mode === "rows" && coverage && (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader><TableRow><TableHead>Site</TableHead><TableHead>Product</TableHead><TableHead>Day</TableHead><TableHead>Completely recorded</TableHead><TableHead>Expected rev.</TableHead><TableHead><span className="sr-only">Remove</span></TableHead></TableRow></TableHeader>
              <TableBody>
                {coverageRows.map((row, index) => (
                  <TableRow key={index}>
                    <TableCell><select aria-label={`Row ${index + 1} site`} className={nativeSelect + " w-40"} value={row.site_id} onChange={(e) => editCoverage((rows) => rows.map((r, i) => i === index ? { ...r, site_id: e.target.value } : r))}><option value="">Site…</option>{catalog.sites.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></TableCell>
                    <TableCell><select aria-label={`Row ${index + 1} product`} className={nativeSelect + " w-40"} value={row.product_id} onChange={(e) => editCoverage((rows) => rows.map((r, i) => i === index ? { ...r, product_id: e.target.value } : r))}><option value="">Product…</option>{catalog.products.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.base_unit})</option>)}</select></TableCell>
                    <TableCell><Input aria-label={`Row ${index + 1} day`} type="date" className="w-38" value={row.day} onChange={(e) => editCoverage((rows) => rows.map((r, i) => i === index ? { ...r, day: e.target.value } : r))} /></TableCell>
                    <TableCell><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={row.complete} onChange={(e) => editCoverage((rows) => rows.map((r, i) => i === index ? { ...r, complete: e.target.checked } : r))} aria-label={`Row ${index + 1} completely recorded`} />{row.complete ? "Complete" : "Incomplete"}</label></TableCell>
                    <TableCell><Input aria-label={`Row ${index + 1} expected revision`} inputMode="numeric" className="w-24" placeholder="new day" value={row.expected_revision} onChange={(e) => editCoverage((rows) => rows.map((r, i) => i === index ? { ...r, expected_revision: e.target.value } : r))} /></TableCell>
                    <TableCell><Button variant="outline" size="sm" disabled={coverageRows.length === 1} onClick={() => editCoverage((rows) => rows.filter((_, i) => i !== index))}>Remove<span className="sr-only"> row {index + 1}</span></Button></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {rowProblems.map((problem, index) => problem && <p key={index} className="text-xs font-medium">⚠ Row {index + 1}: {problem}</p>)}
            <Button variant="outline" size="sm" className="mt-2" disabled={coverageRows.length >= 100} onClick={() => editCoverage((rows) => [...rows, emptyCoverageRow()])}>Add row</Button>
          </div>
        )}

        {mode === "csv" && !coverage && (
          <Field id="demand-csv" label="CSV file" hint={`Exact headers: ${CSV_HEADERS}. At most 100 rows and 60 kB. Empty quantity cells stay "not reported".`}>
            <Input id="demand-csv" type="file" accept=".csv,text/csv" aria-describedby={describedBy("demand-csv", "hint")}
              onChange={(e) => { key.reset(); setResult(null); setFile(e.target.files?.[0] ?? null); }} />
            <Button type="button" variant="outline" size="sm" className="justify-self-start"
              onClick={() => { const a = document.createElement("a"); a.href = `data:text/csv;charset=utf-8,${encodeURIComponent(CSV_HEADERS + "\n")}`; a.download = "demand-history-template.csv"; a.click(); }}>
              Download header template
            </Button>
          </Field>
        )}

        {mode === "json" && (
          <Field id={`${prefix}-json`} label="Rows JSON" hint={coverage ? 'An array of {site_id, product_id, day, complete, expected_revision|null}.' : 'An array of {source_record_key, site_id, product_id, day, expected_revision|null, requested|null, fulfilled|null, unmet|null}; quantities are decimal strings.'}>
            <textarea id={`${prefix}-json`} rows={8} spellCheck={false} value={jsonText} aria-describedby={describedBy(`${prefix}-json`, "hint")}
              className="rounded-md border border-input bg-transparent p-3 font-mono text-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
              onChange={(e) => { key.reset(); setResult(null); setJsonText(e.target.value); }} />
          </Field>
        )}

        {feedback ? <ImportFeedbackTable feedback={feedback} /> : error ? <ErrorAlert message={error instanceof Error && !("code" in error) ? error.message : describeError(error)} onRetry={() => void submit()} /> : null}
        {result && <ResultPanel result={result} />}
        <div className="flex items-center gap-3">
          <Button onClick={() => void submit()} disabled={busy || !!invalid}>{busy ? "Importing…" : `Import ${title.toLowerCase()}`}</Button>
          {invalid && <span className="text-xs text-muted-foreground">{invalid}</span>}
        </div>
      </CardContent>
    </Card>
  );
}
