import { useEffect, useEffectEvent, useRef, useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { vocabularyFor } from "@/lib/mode-vocabulary";
import { SALES_LABEL } from "@/components/data-explorer/trust-panel";
import { networkApi, type Network } from "@/lib/network-api";
import { ApiError, type Schema } from "@/lib/planning-api";
import { formatUnits, pluralize } from "./live-source";
import type { Location } from "./location-map";

type Product = Schema["LocationProjection"]["products"][number];
type Load = { status: "loading" } | { status: "error"; code: string } | { status: "ready"; projection: Schema["LocationProjection"] };
type Props = { network: Network; forecastRunId: string; location: Location; onClose: () => void; /** The ranking row's driving product, listed first. */ drivingProductId?: string };

const DONATIONS = "Donations (forecast, not confirmed)";
const shortDate = (iso: string) => new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
const cell = (value: number | null) => (value === null ? "unknown" : value.toLocaleString("en-US"));

function placeLine(mode: Network["mode"], location: Location) {
  const coordinates = location.latitude !== null && location.longitude !== null
    ? `${location.latitude}, ${location.longitude}` : "no coordinates, so not on the map";
  const role = vocabularyFor(mode).types[location.role] ?? location.role;
  return [role, location.location_id, [location.city, location.state].filter(Boolean).join(", "), coordinates].filter(Boolean).join(" · ");
}

/** One product's days in its own unit. `null` is unknown, never zero; nothing is added across products. */
function ProductProjection({ product, mode, driving }: { product: Product; mode: Network["mode"]; driving: boolean }) {
  const pantry = mode === "PANTRY";
  const columns: [string, (number | null)[] | null][] = [
    ["Target", product.target], [pantry ? "Served" : "Sold", product.served], [pantry ? "Unmet need" : "Lost sales", product.unmet],
    ["Expiring unsold", product.expiring_unsold], ...(pantry ? [[DONATIONS, product.donation_forecast] as [string, (number | null)[] | null]] : []),
  ];
  const shown = columns.filter((c): c is [string, (number | null)[]] => c[1] !== null);
  const missing = columns.filter(([, values]) => values === null).map(([name]) => name);
  return (
    <div className="grid gap-1.5" data-driving={driving || undefined}>
      {driving && <p className="w-fit rounded-md border border-pp-danger/50 px-1.5 py-0.5 text-xs font-medium">Drives this location&apos;s danger rank</p>}
      <div role="region" tabIndex={0} aria-label={`${product.product_id} days, scrolls horizontally`} className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-xs tabular-nums">
          <caption className="pb-1 text-left text-sm font-medium">{product.product_id} in {pluralize(product.unit)}</caption>
          <thead className="text-muted-foreground">
            <tr>{["Day", ...shown.map(([name]) => name)].map((h) => <th key={h} scope="col" className="py-1 pr-3 font-medium">{h}</th>)}</tr>
          </thead>
          <tbody>
            {product.dates.map((date, i) => (
              <tr key={date} className="border-t border-border">
                <th scope="row" className="py-1 pr-3 font-medium">{shortDate(date)}</th>
                {shown.map(([name, values]) => <td key={name} className="py-1 pr-3">{cell(values[i])}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs">Eligible stock now: {formatUnits(product.eligible_stock_now, product.unit)}</p>
      {product.basis === "sales" && <p className="text-xs">Basis: {SALES_LABEL}</p>}
      {missing.map((name) => <p key={name} className="text-xs text-muted-foreground">{name}: not available for {product.product_id}.</p>)}
    </div>
  );
}

/** v1 site inspector (V1-SPEC §6.6) on LocationProjection: per product, in each product's own unit. */
export function LocationInspector({ network, forecastRunId, location, onClose, drivingProductId }: Props) {
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, []);
  // W4-03 ux-critic #5: Escape anywhere closes it, as the demo atlas's inspector does (network-atlas.tsx), unless an
  // open listbox, menu or popover takes the key first.
  const onEscape = useEffectEvent((event: KeyboardEvent) => {
    if (event.key !== "Escape" || event.defaultPrevented) return;
    const target = event.target instanceof Element ? event.target : null;
    if (target?.closest('[role="listbox"], [role="menu"], [data-radix-popper-content-wrapper]')) return;
    event.preventDefault();
    onClose();
  });
  useEffect(() => {
    document.addEventListener("keydown", onEscape);
    return () => document.removeEventListener("keydown", onEscape);
  }, []);
  useEffect(() => {
    let active = true;
    networkApi.projection(network.id, forecastRunId, location.location_id).then(
      (projection) => { if (active) setLoad({ status: "ready", projection }); },
      (error: unknown) => { if (active) setLoad({ status: "error", code: error instanceof ApiError ? error.code : "REQUEST_FAILED" }); },
    );
    return () => { active = false; };
  }, [network.id, forecastRunId, location.location_id, attempt]);

  return (
    <section aria-label={`Site inspector · ${location.name}`} className="pp-inspector-in grid content-start gap-3 rounded-lg border border-border bg-background p-3 lg:sticky lg:top-4">
      <div className="flex items-start justify-between gap-2">
        <div className="grid gap-0.5">
          <h3 ref={heading} tabIndex={-1} className="text-base font-semibold outline-none">{location.name}</h3>
          <p className="text-xs text-muted-foreground">{placeLine(network.mode, location)}</p>
        </div>
        <Button type="button" variant="ghost" size="icon" aria-label="Close inspector" onClick={onClose}><X aria-hidden="true" /></Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Forecast run {forecastRunId.slice(0, 8)}. Forecasts are projections. Each product stays in its own unit and is never added to another.
      </p>
      {load.status === "loading" && <p role="status" className="text-sm text-muted-foreground">Loading the projection…</p>}
      {load.status === "error" && (
        <div role="alert" className="flex flex-wrap items-center gap-3 text-sm">
          Projection unavailable ({load.code.replaceAll("_", " ").toLowerCase()}).
          <Button variant="outline" size="sm" onClick={() => { setLoad({ status: "loading" }); setAttempt((n) => n + 1); }}>Retry</Button>
        </div>
      )}
      {load.status === "ready" && (load.projection.products.length === 0
        ? <p className="text-sm">No product is projected at this location.</p>
        // The driving product first (W4-03 ux-critic #5); the rest keep the API's order.
        : [...load.projection.products].sort((a, b) => Number(b.product_id === drivingProductId) - Number(a.product_id === drivingProductId))
          .map((p) => <ProductProjection key={p.product_id} product={p} mode={load.projection.mode} driving={p.product_id === drivingProductId} />))}
    </section>
  );
}
