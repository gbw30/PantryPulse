import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { dataInputApi, describeError, MAX_ACTIVE_PRODUCTS, useIntentKey, type OperationalCatalog } from "./api";
import { describedBy, ErrorAlert, Field, SavedAlert } from "./shared";

// Products (resource categories): each keeps its own base unit, and quantities are never added
// across products. A new product has no history, so forecasts stay unplanned until its demand and
// donation coverage are imported for every site.

const EMPTY = { name: "", base_unit: "", category_name: "" };

export function ProductsSection({ catalog, onChanged }: { catalog: OperationalCatalog; onChanged: () => Promise<void> }) {
  const [draft, setDraft] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState("");
  const key = useIntentKey();
  const full = catalog.products.length >= MAX_ACTIVE_PRODUCTS;

  const edit = (patch: Partial<typeof draft>) => { key.reset(); setSaved(""); setError(null); setDraft((d) => ({ ...d, ...patch })); };
  const invalid = full ? `The demo network holds at most ${MAX_ACTIVE_PRODUCTS} active products.`
    : !draft.name.trim() || !draft.base_unit.trim() ? "Enter a product name and its base unit." : "";

  async function create() {
    if (busy || invalid) return;
    setBusy(true); setError(null); setSaved("");
    const name = draft.name.trim();
    try {
      await dataInputApi.createProduct({ name, base_unit: draft.base_unit.trim(), category_name: draft.category_name.trim() || null }, key.current());
      key.reset();
      setDraft(EMPTY);
      setSaved(`${name} added. Import its demand history and donation coverage for every site before generating a forecast.`);
      await onChanged();
    } catch (e) { setError(e); } finally { setBusy(false); }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Products</CardTitle>
        <CardDescription>Resource categories in the simulated network, {catalog.products.length} of {MAX_ACTIVE_PRODUCTS} products. Each keeps its own base unit; quantities are never added across products.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); void create(); }}>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field id="product-name" label="Product name"><Input id="product-name" maxLength={200} value={draft.name} disabled={full} onChange={(e) => edit({ name: e.target.value })} /></Field>
            <Field id="product-unit" label="Base unit" hint="Singular, for example can or kit.">
              <Input id="product-unit" maxLength={32} value={draft.base_unit} disabled={full} onChange={(e) => edit({ base_unit: e.target.value })} aria-describedby={describedBy("product-unit", "hint")} />
            </Field>
            <Field id="product-category" label="Category (optional)" hint="Defaults to the product name.">
              <Input id="product-category" maxLength={200} value={draft.category_name} disabled={full} onChange={(e) => edit({ category_name: e.target.value })} aria-describedby={describedBy("product-category", "hint")} />
            </Field>
          </div>
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={busy || !!invalid}>{busy ? "Saving…" : "Add product"}</Button>
            {invalid && <span className="text-xs text-muted-foreground">{invalid}</span>}
          </div>
        </form>
        {!!error && <ErrorAlert message={describeError(error)} />}
        {saved && <SavedAlert title="Saved">{saved}</SavedAlert>}
        <div className="overflow-x-auto">
          <Table>
            <TableCaption>Active products and their base units</TableCaption>
            <TableHeader><TableRow><TableHead>Product</TableHead><TableHead>Base unit</TableHead></TableRow></TableHeader>
            <TableBody>
              {catalog.products.length === 0 && <TableRow><TableCell colSpan={2} className="text-muted-foreground">No active products.</TableCell></TableRow>}
              {catalog.products.map((product) => (
                <TableRow key={product.id}><TableCell>{product.name}</TableCell><TableCell>{product.base_unit}</TableCell></TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
