"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AppShell } from "@/components/shell/app-shell";
import { usePresenter } from "@/components/shell/presenter-session";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, isUuid, type Schema } from "@/lib/planning-api";
import { dataInputApi, describeError, isStale, SIGNED_NONZERO, useIntentKey, type OperationalCatalog } from "./api";
import { DataInputHeader, describedBy, ErrorAlert, Field, nativeSelect, PresenterRequired, SavedAlert } from "./shared";

type Snapshot = Schema["InventorySnapshot"];
type Lot = Schema["InventoryLotView"];
type Eligibility = Lot["eligibility"];
type ExpiryKind = Lot["expiry_kind"];

const ELIGIBILITY: Eligibility[] = ["ELIGIBLE", "HELD", "INELIGIBLE", "UNKNOWN"];
const EXPIRY: ExpiryKind[] = ["DATED", "NON_EXPIRING", "UNKNOWN"];
const EXCLUSION: Record<string, string> = { HELD: "Held", INELIGIBLE: "Ineligible", UNKNOWN_ELIGIBILITY: "Eligibility unknown", UNKNOWN_EXPIRY: "Expiry unknown", EXPIRED: "Expired" };

function DeclareDialog({ lot, snapshot, onClose, onSaved, onReload }: { lot: Lot; snapshot: Snapshot; onClose: () => void; onSaved: (text: string) => void; onReload: () => Promise<void> }) {
  const [eligibility, setEligibility] = useState<Eligibility>(lot.eligibility);
  const [kind, setKind] = useState<ExpiryKind>(lot.expiry_kind);
  const [expiresOn, setExpiresOn] = useState(lot.expires_on ?? "");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const key = useIntentKey();
  // A reload after a 409 changes the version sent, so it is a new intent with a new key.
  useEffect(() => key.reset(), [snapshot.inventory_version, key]);
  const edit = <T,>(set: (v: T) => void) => (v: T) => { key.reset(); set(v); };
  const invalid = !reason.trim() ? "Enter a reason." : kind === "DATED" && !expiresOn ? "Enter the expiry date." : "";

  async function submit() {
    if (busy || invalid || !snapshot.inventory_version) return;
    setBusy(true); setError(null);
    try {
      await dataInputApi.declareLot(lot.lot_id, { eligibility, expiry: { kind, expires_on: kind === "DATED" ? expiresOn : null },
        reason: reason.trim(), expected_inventory_version: snapshot.inventory_version }, key.current());
      key.reset();
      onSaved(`Lot ${lot.batch_key} declared ${eligibility.toLowerCase()} · expiry ${kind === "DATED" ? expiresOn : kind.toLowerCase().replace("_", "-")}.`);
    } catch (e) { setError(e); } finally { setBusy(false); }
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Declare lot {lot.batch_key}</DialogTitle>
          <DialogDescription>Changes eligibility or expiry metadata. Sends inventory version {snapshot.inventory_version}; a newer version is rejected.</DialogDescription>
        </DialogHeader>
        <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
          <fieldset className="grid gap-1.5"><legend className="text-sm font-medium">Eligibility</legend>
            <div className="flex flex-wrap gap-3">{ELIGIBILITY.map((value) => (
              <label key={value} className="flex items-center gap-1.5 text-sm"><input type="radio" name="eligibility" value={value} checked={eligibility === value} onChange={() => edit(setEligibility)(value)} />{value.toLowerCase()}</label>
            ))}</div>
          </fieldset>
          <fieldset className="grid gap-1.5"><legend className="text-sm font-medium">Expiry</legend>
            <div className="flex flex-wrap gap-3">{EXPIRY.map((value) => (
              <label key={value} className="flex items-center gap-1.5 text-sm"><input type="radio" name="expiry-kind" value={value} checked={kind === value} onChange={() => edit(setKind)(value)} />{value.toLowerCase().replace("_", "-")}</label>
            ))}</div>
          </fieldset>
          {kind === "DATED" && <Field id="declare-expires" label="Expires on (local date)"><Input id="declare-expires" type="date" value={expiresOn} onChange={(e) => edit(setExpiresOn)(e.target.value)} required /></Field>}
          <Field id="declare-reason" label="Reason" hint="Recorded with the command; up to 1000 characters.">
            <Textarea id="declare-reason" maxLength={1000} value={reason} onChange={(e) => edit(setReason)(e.target.value)} aria-describedby={describedBy("declare-reason", "hint")} required />
          </Field>
          {!!error && <ErrorAlert message={describeError(error)} onRetry={isStale(error) ? () => void onReload() : undefined} retryLabel="Reload inventory" />}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={busy || !!invalid}>{busy ? "Saving…" : "Save declaration"}</Button>
          </DialogFooter>
          {invalid && <p className="text-xs text-muted-foreground">{invalid}</p>}
        </form>
      </DialogContent>
    </Dialog>
  );
}

function AdjustDialog({ snapshot, onClose, onSaved, onReload }: { snapshot: Snapshot; onClose: () => void; onSaved: (text: string) => void; onReload: () => Promise<void> }) {
  const [deltas, setDeltas] = useState<Record<string, string>>({});
  const [reason, setReason] = useState("");
  const [reference, setReference] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const key = useIntentKey();
  useEffect(() => key.reset(), [snapshot.inventory_version, key]);
  const changes = Object.entries(deltas).filter(([, v]) => v.trim() !== "").map(([lot_id, delta]) => ({ lot_id, delta: delta.trim() }));
  const bad = changes.filter((c) => !SIGNED_NONZERO.test(c.delta)).map((c) => c.lot_id);
  const invalid = !changes.length ? "Enter a change for at least one lot." : bad.length ? "Changes must be whole, non-zero numbers (use − for removals)." : !reason.trim() ? "Enter a reason." : !reference.trim() ? "Enter a source reference." : "";

  async function submit() {
    if (busy || invalid || !snapshot.inventory_version) return;
    setBusy(true); setError(null);
    try {
      const result = await dataInputApi.adjust(snapshot.site_id, snapshot.product_id, { changes, reason: reason.trim(),
        source_reference: reference.trim(), expected_inventory_version: snapshot.inventory_version }, key.current());
      key.reset();
      onSaved(`Adjustment applied to ${result.lots.length} lot(s). Inventory version ${result.before_version} → ${result.after_version}.`);
    } catch (e) { setError(e); } finally { setBusy(false); }
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Record stock adjustment</DialogTitle>
          <DialogDescription>{snapshot.site_name} · {snapshot.product_name} ({snapshot.base_unit}). A count is not a correction: this records a separate, audited change. Sends inventory version {snapshot.inventory_version}.</DialogDescription>
        </DialogHeader>
        <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
          <Table>
            <TableCaption>Leave a lot blank for no change</TableCaption>
            <TableHeader><TableRow><TableHead>Lot</TableHead><TableHead>On hand ({snapshot.base_unit})</TableHead><TableHead>Change</TableHead></TableRow></TableHeader>
            <TableBody>{snapshot.lots.map((lot) => (
              <TableRow key={lot.lot_id}>
                <TableCell>{lot.batch_key}</TableCell>
                <TableCell className="tabular-nums">{lot.on_hand_quantity}</TableCell>
                <TableCell>
                  <Input aria-label={`Change for lot ${lot.batch_key} (${snapshot.base_unit})`} inputMode="numeric" className="w-28" value={deltas[lot.lot_id] ?? ""}
                    aria-invalid={bad.includes(lot.lot_id) || undefined}
                    onChange={(e) => { key.reset(); setDeltas((d) => ({ ...d, [lot.lot_id]: e.target.value })); }} placeholder="e.g. -3" />
                </TableCell>
              </TableRow>
            ))}</TableBody>
          </Table>
          <Field id="adjust-reason" label="Reason"><Textarea id="adjust-reason" maxLength={1000} value={reason} onChange={(e) => { key.reset(); setReason(e.target.value); }} required /></Field>
          <Field id="adjust-reference" label="Source reference" hint="Count sheet, incident or document id."><Input id="adjust-reference" maxLength={256} value={reference} onChange={(e) => { key.reset(); setReference(e.target.value); }} aria-describedby="adjust-reference-hint" required /></Field>
          {!!error && <ErrorAlert message={describeError(error)} onRetry={isStale(error) ? () => void onReload() : undefined} retryLabel="Reload inventory" />}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" variant={changes.some((c) => c.delta.startsWith("-")) ? "destructive" : "default"} disabled={busy || !!invalid}>{busy ? "Saving…" : "Apply adjustment"}</Button>
          </DialogFooter>
          {invalid && <p className="text-xs text-muted-foreground">{invalid}</p>}
        </form>
      </DialogContent>
    </Dialog>
  );
}

function InventoryContent() {
  const { state, expired } = usePresenter();
  const router = useRouter();
  const params = useSearchParams();
  const [catalog, setCatalog] = useState<OperationalCatalog | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState("");
  const [declaring, setDeclaring] = useState<Lot | null>(null);
  const [adjusting, setAdjusting] = useState(false);
  const request = useRef(0);
  const site = params.get("site") ?? "";
  const product = params.get("product") ?? "";

  const fail = useCallback((e: unknown) => { if (e instanceof ApiError && e.status === 401) expired(); setError(e); }, [expired]);

  useEffect(() => {
    if (state !== "presenter") return;
    dataInputApi.catalog().then(setCatalog).catch(fail);
  }, [state, fail]);

  const load = useCallback(() => {
    const id = ++request.current;
    // State flips happen in microtask/promise callbacks so an effect can call load() directly.
    if (!isUuid(site) || !isUuid(product)) {
      queueMicrotask(() => { if (id === request.current) setSnapshot(null); });
      return Promise.resolve();
    }
    queueMicrotask(() => { if (id === request.current) { setLoading(true); setError(null); } });
    return dataInputApi.inventory(site, product)
      .then((value) => { if (id === request.current) setSnapshot(value); })
      .catch((e) => { if (id === request.current) fail(e); })
      .finally(() => { if (id === request.current) setLoading(false); });
  }, [site, product, fail]);

  useEffect(() => { if (state === "presenter") void load(); }, [state, load]);

  const choose = (name: "site" | "product", value: string) => {
    const next = new URLSearchParams(params.toString());
    if (value) next.set(name, value); else next.delete(name);
    setSaved("");
    router.replace(`/data/inventory?${next.toString()}`, { scroll: false });
  };
  const onSaved = (text: string) => { setDeclaring(null); setAdjusting(false); setSaved(text); void load(); };
  const reload = async () => { await load(); };

  if (state === "checking") return <p role="status" className="text-sm text-muted-foreground">Checking presenter session…</p>;
  if (state === "visitor") return <PresenterRequired what="Lot-level inventory is read through presenter-only APIs." />;

  const beneficiaries = catalog?.sites ?? [];
  return (
    <div className="grid gap-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:max-w-2xl">
        <Field id="inventory-site" label="Site">
          <select id="inventory-site" className={nativeSelect} value={site} onChange={(e) => choose("site", e.target.value)} disabled={!catalog}>
            <option value="">Choose a site</option>
            {beneficiaries.map((s) => <option key={s.id} value={s.id}>{s.name}{s.role === "HUB" ? " (hub)" : ""}</option>)}
          </select>
        </Field>
        <Field id="inventory-product" label="Product">
          <select id="inventory-product" className={nativeSelect} value={product} onChange={(e) => choose("product", e.target.value)} disabled={!catalog}>
            <option value="">Choose a product</option>
            {catalog?.products.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.base_unit})</option>)}
          </select>
        </Field>
      </div>
      {!!error && !declaring && !adjusting && <ErrorAlert message={describeError(error)} onRetry={() => void load()} />}
      {saved && <SavedAlert title="Saved">{saved}</SavedAlert>}
      {!snapshot && !loading && !error && <p className="text-sm text-muted-foreground">Choose a site and a product to see its lots.</p>}
      {loading && !snapshot && <Skeleton className="h-48 w-full" />}
      {snapshot && (
        <Card>
          <CardHeader>
            <CardTitle>{snapshot.site_name} · {snapshot.product_name}</CardTitle>
            <CardDescription>
              Observed {new Date(snapshot.observed_at).toLocaleString()} · local date {snapshot.local_date} ({snapshot.timezone}) · inventory version {snapshot.inventory_version ?? "none yet"}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <div><dt className="text-muted-foreground">On hand</dt><dd className="font-semibold tabular-nums">{snapshot.on_hand_quantity} {snapshot.base_unit}</dd></div>
              <div><dt className="text-muted-foreground">Usable</dt><dd className="font-semibold tabular-nums">{snapshot.usable_quantity} {snapshot.base_unit}</dd></div>
              <div><dt className="text-muted-foreground">Excluded</dt><dd className="font-semibold tabular-nums">{snapshot.excluded_quantity} {snapshot.base_unit}</dd></div>
              <div><dt className="text-muted-foreground">Excluded by reason</dt><dd className="tabular-nums">{Object.entries(snapshot.excluded_quantities).map(([k, v]) => `${EXCLUSION[k] ?? k}: ${String(v)}`).join(" · ") || "None"}</dd></div>
            </dl>
            <div className="flex flex-wrap items-center gap-2">
              <Button onClick={() => { setSaved(""); setError(null); setAdjusting(true); }} disabled={!snapshot.inventory_version || !snapshot.lots.length}>Record stock adjustment</Button>
              {!snapshot.inventory_version && <span className="text-xs text-muted-foreground">No inventory version yet; post a receipt first.</span>}
            </div>
            <div className="overflow-x-auto">
              <Table>
                <TableCaption>Lots in {snapshot.base_unit}; expiry is a local date. Usable means eligible, known expiry and not expired.</TableCaption>
                <TableHeader><TableRow>
                  <TableHead>Batch</TableHead><TableHead>Eligibility</TableHead><TableHead>Expiry</TableHead><TableHead>On hand</TableHead><TableHead>Usable</TableHead><TableHead>Exclusion</TableHead><TableHead><span className="sr-only">Actions</span></TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {snapshot.lots.length === 0 && <TableRow><TableCell colSpan={7} className="text-muted-foreground">No lots recorded.</TableCell></TableRow>}
                  {snapshot.lots.map((lot) => (
                    <TableRow key={lot.lot_id}>
                      <TableCell>{lot.batch_key}</TableCell>
                      <TableCell><Badge variant="outline">{lot.eligibility.toLowerCase()}</Badge></TableCell>
                      <TableCell>{lot.expiry_kind === "DATED" ? lot.expires_on : lot.expiry_kind === "NON_EXPIRING" ? "Non-expiring" : "Unknown"}</TableCell>
                      <TableCell className="tabular-nums">{lot.on_hand_quantity}</TableCell>
                      <TableCell>{lot.usable ? "Yes" : "No"}</TableCell>
                      <TableCell>{lot.exclusion_reason ? EXCLUSION[lot.exclusion_reason] ?? lot.exclusion_reason : "—"}</TableCell>
                      <TableCell><Button variant="outline" size="sm" disabled={!snapshot.inventory_version} onClick={() => { setSaved(""); setError(null); setDeclaring(lot); }}>Declare<span className="sr-only"> lot {lot.batch_key}</span></Button></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}
      {declaring && snapshot && <DeclareDialog lot={declaring} snapshot={snapshot} onClose={() => setDeclaring(null)} onSaved={onSaved} onReload={reload} />}
      {adjusting && snapshot && <AdjustDialog snapshot={snapshot} onClose={() => setAdjusting(false)} onSaved={onSaved} onReload={reload} />}
    </div>
  );
}

export function InventoryView() {
  return (
    <AppShell active="data">
      <div className="flex flex-1 flex-col gap-4 px-4 pt-3 pb-6 md:gap-6 md:px-6 md:py-5">
        <DataInputHeader active="inventory" title="Inventory & Lots" description="Lot-level eligibility, expiry and stock for one site and product. Presenter corrections are versioned commands." />
        <Suspense fallback={<Skeleton className="h-48 w-full" />}><InventoryContent /></Suspense>
      </div>
    </AppShell>
  );
}
