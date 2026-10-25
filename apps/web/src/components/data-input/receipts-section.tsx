"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { isUuid, type Schema } from "@/lib/planning-api";
import { dataInputApi, describeError, isStale, POSITIVE, useIntentKey, type OperationalCatalog, type ReceiptRead } from "./api";
import { describedBy, ErrorAlert, Field, nativeSelect, SavedAlert } from "./shared";

// Receipts: create a revision (no stock effect), then post it once (stock effect), reconcile later.
// There is no list endpoint (backend follow-up), so the panel tracks receipts opened this session
// plus "Open receipt by id".

type LineDraft = { line_key: string; product_id: string; quantity: string };
type Declaration = { eligibility: "ELIGIBLE" | "HELD" | "INELIGIBLE" | "UNKNOWN"; kind: "DATED" | "NON_EXPIRING" | "UNKNOWN"; expires_on: string };

function linesProblem(lines: LineDraft[]): string {
  if (!lines.length) return "Add at least one line.";
  if (lines.some((l) => !l.line_key.trim() || !l.product_id)) return "Every line needs a key and a product.";
  if (lines.some((l) => !POSITIVE.test(l.quantity.trim()))) return "Quantities must be positive whole numbers.";
  if (new Set(lines.map((l) => l.line_key.trim())).size !== lines.length) return "Line keys must be unique.";
  return "";
}

function ReceiptForm({ catalog, receipt, onSaved }: { catalog: OperationalCatalog; receipt: ReceiptRead | null; onSaved: (id: string) => void }) {
  const latest = receipt?.revisions.at(-1) ?? null;
  const [donorId, setDonorId] = useState(latest?.donor_id ?? "");
  const [siteId, setSiteId] = useState(latest?.receiving_site_id ?? latest?.site_id ?? "");
  const [sourceId, setSourceId] = useState(receipt?.receipt.source_id ?? "");
  const [recordKey, setRecordKey] = useState(receipt?.receipt.source_record_key ?? "");
  const [receivedAt, setReceivedAt] = useState(latest ? latest.received_at.slice(0, 16) : "");
  const [isVoid, setIsVoid] = useState(latest?.is_void ?? false);
  const [lines, setLines] = useState<LineDraft[]>(latest
    ? latest.lines.map((l) => ({ line_key: l.line_key, product_id: l.product_id, quantity: l.received_quantity }))
    : [{ line_key: "L1", product_id: "", quantity: "" }]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const key = useIntentKey();
  const revising = receipt !== null;
  const prefix = revising ? "revise" : "create";
  const edit = <T,>(set: (v: T) => void) => (v: T) => { key.reset(); setError(null); set(v); };
  const invalid = !donorId || !siteId || !sourceId || !recordKey.trim() || !receivedAt ? "Fill donor, site, source, record key and received time." : linesProblem(lines);

  async function submit() {
    if (busy || invalid) return;
    setBusy(true); setError(null);
    try {
      const body: Schema["ReceiptWrite"] = {
        donor_id: donorId, site_id: siteId, source_id: sourceId, source_record_key: recordKey.trim(),
        received_at: new Date(receivedAt).toISOString(), is_void: isVoid,
        expected_revision: revising ? latest!.revision : null,
        lines: lines.map((l) => ({ line_key: l.line_key.trim(), product_id: l.product_id, quantity: l.quantity.trim() })),
      };
      const result = revising
        ? await dataInputApi.reviseReceipt(receipt!.receipt.id, body, key.current())
        : await dataInputApi.createReceipt(body, key.current());
      key.reset();
      onSaved(String((result.result as { receipt_id?: string }).receipt_id ?? receipt?.receipt.id ?? ""));
    } catch (e) { setError(e); } finally { setBusy(false); }
  }

  return (
    <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Field id={`${prefix}-donor`} label="Donor">
          <select id={`${prefix}-donor`} className={nativeSelect} value={donorId} onChange={(e) => edit(setDonorId)(e.target.value)}><option value="">Choose a donor</option>{catalog.donors.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select>
        </Field>
        <Field id={`${prefix}-site`} label="Receiving site">
          <select id={`${prefix}-site`} className={nativeSelect} value={siteId} onChange={(e) => edit(setSiteId)(e.target.value)}><option value="">Choose a site</option>{catalog.sites.map((s) => <option key={s.id} value={s.id}>{s.name}{s.role === "HUB" ? " (hub)" : ""}</option>)}</select>
        </Field>
        <Field id={`${prefix}-source`} label="Data source" hint={revising ? "A revision keeps the receipt's source." : undefined}>
          <select id={`${prefix}-source`} className={nativeSelect} value={sourceId} disabled={revising} onChange={(e) => edit(setSourceId)(e.target.value)} aria-describedby={describedBy(`${prefix}-source`, revising ? "hint" : undefined)}><option value="">Choose a source</option>{catalog.data_sources.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.classification.toLowerCase()})</option>)}</select>
        </Field>
        <Field id={`${prefix}-record-key`} label="Source record key" hint={revising ? "Kept from the original receipt." : "The source system's id for this receipt."}>
          <Input id={`${prefix}-record-key`} maxLength={256} value={recordKey} disabled={revising} onChange={(e) => edit(setRecordKey)(e.target.value)} aria-describedby={describedBy(`${prefix}-record-key`, "hint")} />
        </Field>
        <Field id={`${prefix}-received-at`} label="Received at" hint="Local time; cannot be in the future.">
          <Input id={`${prefix}-received-at`} type="datetime-local" value={receivedAt} onChange={(e) => edit(setReceivedAt)(e.target.value)} aria-describedby={describedBy(`${prefix}-received-at`, "hint")} />
        </Field>
        <div className="flex items-end pb-1">
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={isVoid} onChange={(e) => edit(setIsVoid)(e.target.checked)} />Void (cancels the receipt&apos;s content)</label>
        </div>
      </div>
      <Table>
        <TableCaption>Received quantities in each product&apos;s own unit</TableCaption>
        <TableHeader><TableRow><TableHead>Line key</TableHead><TableHead>Product</TableHead><TableHead>Quantity</TableHead><TableHead><span className="sr-only">Remove</span></TableHead></TableRow></TableHeader>
        <TableBody>
          {lines.map((line, index) => (
            <TableRow key={index}>
              <TableCell><Input aria-label={`Line ${index + 1} key`} className="w-28" maxLength={256} value={line.line_key} onChange={(e) => edit(setLines)(lines.map((l, i) => i === index ? { ...l, line_key: e.target.value } : l))} /></TableCell>
              <TableCell><select aria-label={`Line ${index + 1} product`} className={nativeSelect + " w-48"} value={line.product_id} onChange={(e) => edit(setLines)(lines.map((l, i) => i === index ? { ...l, product_id: e.target.value } : l))}><option value="">Product…</option>{catalog.products.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.base_unit})</option>)}</select></TableCell>
              <TableCell><Input aria-label={`Line ${index + 1} quantity`} inputMode="numeric" className="w-28" value={line.quantity} onChange={(e) => edit(setLines)(lines.map((l, i) => i === index ? { ...l, quantity: e.target.value } : l))} /></TableCell>
              <TableCell><Button type="button" variant="outline" size="sm" disabled={lines.length === 1} onClick={() => edit(setLines)(lines.filter((_, i) => i !== index))}>Remove<span className="sr-only"> line {index + 1}</span></Button></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <div>
        <Button type="button" variant="outline" size="sm" onClick={() => edit(setLines)([...lines, { line_key: `L${lines.length + 1}`, product_id: "", quantity: "" }])}>Add line</Button>
      </div>
      {!!error && <ErrorAlert message={describeError(error)} onRetry={isStale(error) ? undefined : () => void submit()} />}
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={busy || !!invalid}>{busy ? "Saving…" : revising ? `Save revision ${Number(latest!.revision) + 1} (no stock effect)` : "Create receipt (no stock effect)"}</Button>
        {invalid && <span className="text-xs text-muted-foreground">{invalid}</span>}
      </div>
    </form>
  );
}

function StockDialog({ receipt, action, catalog, onClose, onSaved }: { receipt: ReceiptRead; action: "post" | "reconcile"; catalog: OperationalCatalog; onClose: () => void; onSaved: (text: string) => void }) {
  const latest = receipt.revisions.at(-1)!;
  const siteId = latest.receiving_site_id ?? latest.site_id ?? "";
  const products = [...new Set(latest.lines.map((l) => l.product_id))];
  const [declarations, setDeclarations] = useState<Record<string, Declaration>>(Object.fromEntries(latest.lines.map((l) => [l.line_key, { eligibility: "ELIGIBLE", kind: "DATED", expires_on: "" } as Declaration])));
  const [versions, setVersions] = useState<Record<string, string>>(Object.fromEntries(products.map((p) => [p, ""])));
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadingVersions, setLoadingVersions] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const key = useIntentKey();
  const productName = (id: string) => { const p = catalog.products.find((x) => x.id === id); return p ? `${p.name} (${p.base_unit})` : id; };
  const invalid = latest.lines.some((l) => { const d = declarations[l.line_key]; return d.kind === "DATED" && !d.expires_on; })
    ? "Dated lines need an expiry date."
    : products.some((p) => versions[p].trim() !== "" && !POSITIVE.test(versions[p].trim())) ? "Versions must be positive whole numbers."
    : !reason.trim() ? "Enter a reason." : "";

  async function loadVersions() {
    setLoadingVersions(true); setError(null);
    try {
      const snapshots = await Promise.all(products.map((p) => dataInputApi.inventory(siteId, p)));
      key.reset();
      setVersions(Object.fromEntries(snapshots.map((s) => [s.product_id, s.inventory_version ?? ""])));
    } catch (e) { setError(e); } finally { setLoadingVersions(false); }
  }

  async function submit() {
    if (busy || invalid) return;
    setBusy(true); setError(null);
    try {
      const body: Schema["ReceiptStockWrite"] = {
        revision_id: latest.id, reason: reason.trim(),
        declarations: latest.lines.map((l) => { const d = declarations[l.line_key]; return { line_key: l.line_key, eligibility: d.eligibility, expiry: { kind: d.kind, expires_on: d.kind === "DATED" ? d.expires_on : null } }; }),
        expected_versions: products.filter((p) => versions[p].trim() !== "").map((p) => ({ site_id: siteId, product_id: p, version: versions[p].trim() })),
        supply_matches: [], supply_versions: [],
      };
      await dataInputApi.postReceipt(receipt.receipt.id, action, body, key.current());
      key.reset();
      onSaved(action === "post" ? `Receipt posted — stock changed at ${catalog.sites.find((s) => s.id === siteId)?.name ?? siteId}.` : "Receipt reconciled against posted stock.");
    } catch (e) { setError(e); } finally { setBusy(false); }
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{action === "post" ? "Post receipt to stock" : "Reconcile receipt"}</DialogTitle>
          <DialogDescription>Revision {latest.revision} at {catalog.sites.find((s) => s.id === siteId)?.name ?? siteId}. Each line needs an eligibility and expiry declaration; expected versions guard against concurrent stock changes (409 when stale).</DialogDescription>
        </DialogHeader>
        <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
          {latest.lines.map((line) => {
            const d = declarations[line.line_key];
            const set = (next: Partial<Declaration>) => { key.reset(); setDeclarations((all) => ({ ...all, [line.line_key]: { ...all[line.line_key], ...next } })); };
            return (
              <fieldset key={line.line_key} className="grid gap-2 rounded-md border border-border p-3">
                <legend className="px-1 text-sm font-medium">Line {line.line_key} · {productName(line.product_id)} · {line.received_quantity}</legend>
                <div className="flex flex-wrap gap-3">
                  {(["ELIGIBLE", "HELD", "INELIGIBLE", "UNKNOWN"] as const).map((v) => (
                    <label key={v} className="flex items-center gap-1.5 text-sm"><input type="radio" name={`elig-${line.line_key}`} checked={d.eligibility === v} onChange={() => set({ eligibility: v })} />{v.toLowerCase()}</label>
                  ))}
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  {(["DATED", "NON_EXPIRING", "UNKNOWN"] as const).map((v) => (
                    <label key={v} className="flex items-center gap-1.5 text-sm"><input type="radio" name={`exp-${line.line_key}`} checked={d.kind === v} onChange={() => set({ kind: v })} />{v.toLowerCase().replace("_", "-")}</label>
                  ))}
                  {d.kind === "DATED" && <Input aria-label={`Line ${line.line_key} expires on`} type="date" className="w-40" value={d.expires_on} onChange={(e) => set({ expires_on: e.target.value })} />}
                </div>
              </fieldset>
            );
          })}
          <fieldset className="grid gap-2 rounded-md border border-border p-3">
            <legend className="px-1 text-sm font-medium">Expected inventory versions</legend>
            <div className="flex items-center gap-2">
              <Button type="button" variant="outline" size="sm" disabled={loadingVersions} onClick={() => void loadVersions()}>{loadingVersions ? "Loading…" : "Load current versions"}</Button>
              <span className="text-xs text-muted-foreground">Leave blank for a product with no stock yet.</span>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {products.map((p) => (
                <Field key={p} id={`version-${p}`} label={productName(p)}>
                  <Input id={`version-${p}`} inputMode="numeric" value={versions[p]} onChange={(e) => { key.reset(); setVersions((v) => ({ ...v, [p]: e.target.value })); }} placeholder="no stock yet" />
                </Field>
              ))}
            </div>
          </fieldset>
          <Field id={`${action}-reason`} label="Reason"><Textarea id={`${action}-reason`} maxLength={1000} value={reason} onChange={(e) => { key.reset(); setReason(e.target.value); }} required /></Field>
          {!!error && <ErrorAlert message={describeError(error)} onRetry={isStale(error) ? () => void loadVersions() : () => void submit()} retryLabel={isStale(error) ? "Reload versions" : "Retry"} />}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={busy || !!invalid}>{busy ? "Saving…" : action === "post" ? "Post to stock" : "Reconcile"}</Button>
          </DialogFooter>
          {invalid && <p className="text-xs text-muted-foreground">{invalid}</p>}
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ReceiptsSection({ catalog }: { catalog: OperationalCatalog }) {
  const [openId, setOpenId] = useState("");
  const [receipt, setReceipt] = useState<ReceiptRead | null>(null);
  const [known, setKnown] = useState<string[]>([]);
  const [mode, setMode] = useState<"view" | "create" | "revise">("create");
  const [stockAction, setStockAction] = useState<"post" | "reconcile" | null>(null);
  const [saved, setSaved] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function open(id: string) {
    if (!isUuid(id)) { setError(new Error("Enter a receipt id (UUID).")); return; }
    // Keeps `saved` so a save-then-reload flow still shows its confirmation.
    setBusy(true); setError(null);
    try {
      const value = await dataInputApi.receipt(id);
      setReceipt(value); setMode("view");
      setKnown((k) => (k.includes(id) ? k : [...k, id]));
    } catch (e) { setError(e); } finally { setBusy(false); }
  }

  const latest = receipt?.revisions.at(-1) ?? null;
  const siteName = (id?: string) => catalog.sites.find((s) => s.id === id)?.name ?? id ?? "?";
  const productName = (id: string) => { const p = catalog.products.find((x) => x.id === id); return p ? `${p.name} (${p.base_unit})` : id; };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Receipts</CardTitle>
        <CardDescription>A receipt revision records what arrived (no stock effect). Posting it once applies stock with per-line eligibility and expiry; reconciling checks it later. There is no list API yet — receipts opened this session are tracked here.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <div className="flex flex-wrap items-end gap-2">
          <Field id="receipt-open" label="Open receipt by id">
            <Input id="receipt-open" className="w-80" value={openId} onChange={(e) => setOpenId(e.target.value)} placeholder="receipt UUID" />
          </Field>
          <Button variant="outline" disabled={busy} onClick={() => void open(openId.trim())}>Open</Button>
          <Button variant={mode === "create" ? "default" : "outline"} onClick={() => { setMode("create"); setReceipt(null); setSaved(""); setError(null); }}>New receipt</Button>
        </div>
        {known.length > 0 && (
          <p className="text-xs text-muted-foreground">This session: {known.map((id) => (
            <Button key={id} variant="link" size="sm" className="h-auto px-1 font-mono text-xs" onClick={() => void open(id)}>{id.slice(0, 8)}</Button>
          ))}</p>
        )}
        {!!error && <ErrorAlert message={error instanceof Error && !("code" in error) ? error.message : describeError(error)} />}
        {saved && <SavedAlert title="Saved">{saved}</SavedAlert>}

        {mode === "create" && <ReceiptForm key="create" catalog={catalog} receipt={null} onSaved={(id) => { setSaved(`Receipt created (no stock effect). Id ${id}.`); void open(id); }} />}
        {mode === "revise" && receipt && <ReceiptForm key={`revise-${receipt.receipt.id}-${latest?.revision}`} catalog={catalog} receipt={receipt} onSaved={(id) => { setSaved("Revision saved (no stock effect)."); void open(id); }} />}

        {mode === "view" && receipt && latest && (
          <div className="grid gap-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <Badge variant="outline">Revision {latest.revision}</Badge>
              {latest.is_void && <Badge variant="outline">VOID</Badge>}
              <Badge variant="outline">{receipt.reconciliation ? (receipt.reconciliation.needs_reconciliation ? "Posted · needs reconciliation" : "Posted · reconciled") : "Not posted"}</Badge>
              <span>{siteName(latest.receiving_site_id ?? latest.site_id)} · received {new Date(latest.received_at).toLocaleString()} · local day {latest.local_day}</span>
            </div>
            <Table>
              <TableCaption>Latest revision&apos;s lines</TableCaption>
              <TableHeader><TableRow><TableHead>Line</TableHead><TableHead>Product</TableHead><TableHead>Quantity</TableHead></TableRow></TableHeader>
              <TableBody>{latest.lines.map((l) => <TableRow key={l.id}><TableCell>{l.line_key}</TableCell><TableCell>{productName(l.product_id)}</TableCell><TableCell className="tabular-nums">{l.received_quantity}</TableCell></TableRow>)}</TableBody>
            </Table>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => { setMode("revise"); setSaved(""); setError(null); }}>Revise (expects revision {latest.revision})</Button>
              <Button onClick={() => { setSaved(""); setError(null); setStockAction("post"); }}>Post to stock…</Button>
              <Button variant="outline" onClick={() => { setSaved(""); setError(null); setStockAction("reconcile"); }}>Reconcile…</Button>
            </div>
            <p className="text-xs text-muted-foreground">{receipt.revisions.length} revision(s). Posting applies the latest revision; it is rejected if already posted or void.</p>
          </div>
        )}
        {stockAction && receipt && (
          <StockDialog receipt={receipt} action={stockAction} catalog={catalog} onClose={() => setStockAction(null)}
            onSaved={(text) => { setStockAction(null); setSaved(text); void open(receipt.receipt.id); }} />
        )}
      </CardContent>
    </Card>
  );
}
