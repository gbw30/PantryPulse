"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import type { Schema } from "@/lib/planning-api";
import { dataInputApi, describeError, isStale, NONNEGATIVE, POSITIVE, useIntentKey, type OperationalCatalog, type SupplyRow } from "./api";
import { describedBy, ErrorAlert, Field, nativeSelect, SavedAlert } from "./shared";

// Expected supplies: future arrivals. Confirming sets the outstanding quantity and optional ETA;
// a confirmed supply is still NOT on-hand stock — only a posted receipt is.

function ConfirmDialog({ supply, inventoryVersionHint, catalog, onClose, onSaved, onReload }: {
  supply: SupplyRow; inventoryVersionHint: string | null; catalog: OperationalCatalog; onClose: () => void; onSaved: (text: string) => void; onReload: () => Promise<void>;
}) {
  const [outstanding, setOutstanding] = useState(supply.outstanding_confirmed_quantity !== "0" ? supply.outstanding_confirmed_quantity : supply.quantity);
  const [arrival, setArrival] = useState(supply.expected_arrival_at ? supply.expected_arrival_at.slice(0, 16) : "");
  const [inventoryVersion, setInventoryVersion] = useState(inventoryVersionHint ?? "");
  const [cancel, setCancel] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const key = useIntentKey();
  const product = catalog.products.find((p) => p.id === supply.product_id);
  const invalid = !NONNEGATIVE.test(outstanding.trim()) ? "Outstanding must be a whole number (0 with Cancel)." :
    !POSITIVE.test(inventoryVersion.trim()) ? "Enter the current inventory version (load it in Inventory & Lots; post a receipt first if none exists)." :
    !reason.trim() ? "Enter a reason." : "";

  async function submit() {
    if (busy || invalid) return;
    setBusy(true); setError(null);
    try {
      const body: Schema["SupplyConfirmation"] = {
        cancel, reason: reason.trim(),
        outstanding_quantity: cancel ? "0" : outstanding.trim(),
        expected_arrival_at: arrival ? new Date(arrival).toISOString() : null,
        expected_inventory_version: inventoryVersion.trim(),
        expected_supply_version: supply.version,
      };
      await dataInputApi.confirmSupply(supply.id, body, key.current());
      key.reset();
      onSaved(cancel ? `Supply ${supply.source_record_key} cancelled.` : `Supply ${supply.source_record_key} confirmed — ${outstanding.trim()} ${product?.base_unit ?? "units"} outstanding. Confirmed supply is an expected arrival, not on-hand stock.`);
    } catch (e) { setError(e); } finally { setBusy(false); }
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{cancel ? "Cancel expected supply" : "Confirm expected supply"}</DialogTitle>
          <DialogDescription>{supply.source_record_key} · {product ? `${product.name} (${product.base_unit})` : supply.product_id} · announced {supply.quantity}. Sends supply version {supply.version}; a newer version is rejected (409).</DialogDescription>
        </DialogHeader>
        <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={cancel} onChange={(e) => { key.reset(); setCancel(e.target.checked); }} />Cancel this supply instead of confirming</label>
          {!cancel && (
            <>
              <Field id="confirm-outstanding" label={`Outstanding quantity (${product?.base_unit ?? "units"})`} hint="What is still expected to arrive.">
                <Input id="confirm-outstanding" inputMode="numeric" value={outstanding} onChange={(e) => { key.reset(); setOutstanding(e.target.value); }} aria-describedby={describedBy("confirm-outstanding", "hint")} />
              </Field>
              <Field id="confirm-arrival" label="Expected arrival (optional)">
                <Input id="confirm-arrival" type="datetime-local" value={arrival} onChange={(e) => { key.reset(); setArrival(e.target.value); }} />
              </Field>
            </>
          )}
          <Field id="confirm-inventory-version" label="Current inventory version" hint="For this site and product; shown in Inventory & Lots.">
            <Input id="confirm-inventory-version" inputMode="numeric" value={inventoryVersion} onChange={(e) => { key.reset(); setInventoryVersion(e.target.value); }} aria-describedby={describedBy("confirm-inventory-version", "hint")} />
          </Field>
          <Field id="confirm-reason" label="Reason"><Textarea id="confirm-reason" maxLength={1000} value={reason} onChange={(e) => { key.reset(); setReason(e.target.value); }} required /></Field>
          {!!error && <ErrorAlert message={describeError(error)} onRetry={isStale(error) ? () => void onReload() : () => void submit()} retryLabel={isStale(error) ? "Reload supplies" : "Retry"} />}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Close</Button>
            <Button type="submit" variant={cancel ? "destructive" : "default"} disabled={busy || !!invalid}>{busy ? "Saving…" : cancel ? "Cancel supply" : "Confirm supply"}</Button>
          </DialogFooter>
          {invalid && <p className="text-xs text-muted-foreground">{invalid}</p>}
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function SuppliesSection({ catalog }: { catalog: OperationalCatalog }) {
  const [rows, setRows] = useState<SupplyRow[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState<SupplyRow | null>(null);
  const [draft, setDraft] = useState({ site_id: "", product_id: "", source_id: "", source_record_key: "", quantity: "" });
  const key = useIntentKey();

  const load = useCallback(() =>
    dataInputApi.supplies().then((value) => setRows(value.supplies)).catch(setError), []);
  useEffect(() => { void load(); }, [load]);

  const edit = (patch: Partial<typeof draft>) => { key.reset(); setSaved(""); setDraft((d) => ({ ...d, ...patch })); };
  const invalid = !draft.site_id || !draft.product_id || !draft.source_id || !draft.source_record_key.trim() ? "Fill site, product, source and record key."
    : !POSITIVE.test(draft.quantity.trim()) ? "Quantity must be a positive whole number." : "";

  async function create() {
    if (busy || invalid) return;
    setBusy(true); setError(null); setSaved("");
    try {
      await dataInputApi.createSupply({ ...draft, source_record_key: draft.source_record_key.trim(), quantity: draft.quantity.trim() }, key.current());
      key.reset();
      setSaved("Expected supply created (unconfirmed). It is not stock until a receipt is posted.");
      setDraft({ site_id: "", product_id: "", source_id: "", source_record_key: "", quantity: "" });
      await load();
    } catch (e) { setError(e); } finally { setBusy(false); }
  }

  const name = (list: { id: string; name: string }[], id: string) => list.find((x) => x.id === id)?.name ?? id;
  const unit = (id: string) => catalog.products.find((p) => p.id === id)?.base_unit ?? "units";

  return (
    <Card>
      <CardHeader>
        <CardTitle>Expected supplies</CardTitle>
        <CardDescription>Announced future arrivals. Confirming records the outstanding quantity and optional ETA; stock only changes when a receipt is posted and matched.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); void create(); }}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Field id="supply-site" label="Site"><select id="supply-site" className={nativeSelect} value={draft.site_id} onChange={(e) => edit({ site_id: e.target.value })}><option value="">Site…</option>{catalog.sites.map((s) => <option key={s.id} value={s.id}>{s.name}{s.role === "HUB" ? " (hub)" : ""}</option>)}</select></Field>
            <Field id="supply-product" label="Product"><select id="supply-product" className={nativeSelect} value={draft.product_id} onChange={(e) => edit({ product_id: e.target.value })}><option value="">Product…</option>{catalog.products.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.base_unit})</option>)}</select></Field>
            <Field id="supply-source" label="Data source"><select id="supply-source" className={nativeSelect} value={draft.source_id} onChange={(e) => edit({ source_id: e.target.value })}><option value="">Source…</option>{catalog.data_sources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>
            <Field id="supply-record-key" label="Source record key"><Input id="supply-record-key" maxLength={256} value={draft.source_record_key} onChange={(e) => edit({ source_record_key: e.target.value })} /></Field>
            <Field id="supply-quantity" label={`Quantity${draft.product_id ? ` (${unit(draft.product_id)})` : ""}`}><Input id="supply-quantity" inputMode="numeric" value={draft.quantity} onChange={(e) => edit({ quantity: e.target.value })} /></Field>
          </div>
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={busy || !!invalid}>{busy ? "Saving…" : "Create expected supply"}</Button>
            {invalid && <span className="text-xs text-muted-foreground">{invalid}</span>}
          </div>
        </form>
        {!!error && !confirming && <ErrorAlert message={describeError(error)} onRetry={() => { setError(null); void load(); }} />}
        {saved && <SavedAlert title="Saved">{saved}</SavedAlert>}
        {rows === null ? <Skeleton className="h-32 w-full" /> : (
          <div className="overflow-x-auto">
            <Table>
              <TableCaption>Quantities in each product&apos;s own unit; at most 100 supplies are listed.</TableCaption>
              <TableHeader><TableRow><TableHead>Record key</TableHead><TableHead>Site</TableHead><TableHead>Product</TableHead><TableHead>Announced</TableHead><TableHead>Outstanding</TableHead><TableHead>Received</TableHead><TableHead>ETA</TableHead><TableHead>State</TableHead><TableHead><span className="sr-only">Actions</span></TableHead></TableRow></TableHeader>
              <TableBody>
                {rows.length === 0 && <TableRow><TableCell colSpan={9} className="text-muted-foreground">No expected supplies recorded.</TableCell></TableRow>}
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>{row.source_record_key}</TableCell>
                    <TableCell>{name(catalog.sites, row.site_id)}</TableCell>
                    <TableCell>{name(catalog.products, row.product_id)}</TableCell>
                    <TableCell className="tabular-nums">{row.quantity} {unit(row.product_id)}</TableCell>
                    <TableCell className="tabular-nums">{row.outstanding_confirmed_quantity} {unit(row.product_id)}</TableCell>
                    <TableCell className="tabular-nums">{row.received_quantity} {unit(row.product_id)}</TableCell>
                    <TableCell>{row.expected_arrival_at ? new Date(row.expected_arrival_at).toLocaleString() : "—"}</TableCell>
                    <TableCell><Badge variant="outline">{row.state.toLowerCase()}</Badge></TableCell>
                    <TableCell><Button variant="outline" size="sm" onClick={() => { setSaved(""); setError(null); setConfirming(row); }}>Confirm / cancel<span className="sr-only"> supply {row.source_record_key}</span></Button></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
        {confirming && (
          <ConfirmDialog supply={confirming} inventoryVersionHint={null} catalog={catalog}
            onClose={() => setConfirming(null)}
            onSaved={(text) => { setConfirming(null); setSaved(text); void load(); }}
            onReload={async () => { await load(); setConfirming(null); }} />
        )}
      </CardContent>
    </Card>
  );
}
