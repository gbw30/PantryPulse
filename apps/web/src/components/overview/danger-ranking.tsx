"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { SampleBadge, useNetwork } from "@/components/shell/network-switcher";
import { networkApi, type Network } from "@/lib/network-api";
import { ApiError, type Schema } from "@/lib/planning-api";
import { cn } from "@/lib/utils";
import { formatUnits } from "./live-source";
import { LocationInspector } from "./location-inspector";
import { LocationMap, placeLocations } from "./location-map";
import { DANGER_BANDS, DangerBandGlyph, DangerLegend } from "./risk-legend";

type Ranking = Schema["DangerRanking"];
type Row = Schema["DangerRow"];

const BAND_LABEL = Object.fromEntries(DANGER_BANDS.map((b) => [b.band, b.label])) as Record<Row["band"], string>;
export { formatUnits } from "./live-source";
const percent = (ratio: string) => `${(Number(ratio) * 100).toLocaleString("en-US", { maximumFractionDigits: 1 })}%`;
const shortDate = (iso: string) => new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });

/** The share the score measures, in words (V1-SPEC §6.6). */
function scoreText(row: Row, mode: Ranking["mode"]) {
  if (row.reason === "expiry") return `${percent(row.score_ratio)} of stock projected to expire unsold`;
  return `${percent(row.score_ratio)} of 7-day ${mode === "RETAIL" ? "sales" : "demand"} projected unmet`;
}
const unitsText = (row: Row) => `${formatUnits(row.driving_units, row.unit)} ${row.reason === "expiry" ? "expiring unsold" : "projected unmet"}`;
const retailReason = (row: Row) => row.reason === "expiry"
  ? "Reason: stock expiring unsold (higher than the unmet-sales share)"
  : "Reason: lost sales (higher than the expiring-stock share)";

type View = "list" | "table";

type RankingProps = {
  ranking: Ranking;
  view?: View;
  /** "Archer Road Pantry (P-12)" once the location list has loaded; the bare ID until then. */
  label?: (locationId: string) => string;
  /** Opens the site inspector; absent for a location the list doesn't know. */
  onSelect?: (locationId: string, opener: HTMLElement) => void;
  canSelect?: (locationId: string) => boolean;
};

/** Ranked locations with a band (text + shape), the driving product in its own unit, and a table view. */
export function DangerRanking({ ranking, view: initialView = "list", label = (id) => id, onSelect, canSelect = () => true }: RankingProps) {
  const [view, setView] = useState<View>(initialView);
  const rows = [...ranking.rows].sort((a, b) => a.rank - b.rank);
  const name = (id: string, className: string) => onSelect && canSelect(id)
    ? <button type="button" className={cn(className, "text-left underline underline-offset-2 hover:text-primary")} onClick={(e) => onSelect(id, e.currentTarget)}>{label(id)}</button>
    : <span className={className}>{label(id)}</span>;
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <DangerLegend mode={ranking.mode} />
        <div className="flex gap-1" role="group" aria-label="Ranking view">
          {(["list", "table"] as const).map((v) => (
            <Button key={v} variant={view === v ? "secondary" : "ghost"} size="sm" aria-pressed={view === v} onClick={() => setView(v)} className="max-md:h-11">
              {v === "list" ? "List" : "Table"}
            </Button>
          ))}
        </div>
      </div>
      {view === "list" ? (
        <ol aria-label="Locations by danger" className="grid gap-2">
          {rows.map((row) => (
            <li key={row.location_id} aria-label={`${label(row.location_id)}, rank ${row.rank}, ${BAND_LABEL[row.band]}`}
              className={cn("grid gap-1 rounded-lg border bg-card px-3 py-2 text-sm", row.band === "high" ? "border-pp-danger/50" : "border-border")}>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="tabular-nums text-muted-foreground">#{row.rank}</span>
                {name(row.location_id, "font-semibold")}
                <span className="inline-flex items-center gap-1.5"><DangerBandGlyph band={row.band} /><span>{BAND_LABEL[row.band]}</span></span>
                <span>{scoreText(row, ranking.mode)}</span>
              </div>
              <p className="text-muted-foreground">
                Driving product <span className="font-medium text-foreground">{row.driving_product_id}</span>: {unitsText(row)}
                {row.first_deficit_date && <> · first deficit {shortDate(row.first_deficit_date)}</>}
              </p>
              {ranking.mode === "RETAIL" && <p className="text-xs text-muted-foreground">{retailReason(row)}</p>}
            </li>
          ))}
        </ol>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border" role="group" aria-label="Scrollable danger ranking table" tabIndex={0}>
          <table className="w-full min-w-[40rem] border-collapse text-left text-sm">
            <caption className="px-3 py-2 text-left font-medium">Danger ranking ({rows.length} locations)</caption>
            <thead className="bg-muted/60 text-xs text-muted-foreground">
              <tr>{["Location", "Rank", "Band", "Score", "Driving product", "Units (that product)", "First deficit"].map((h) => <th key={h} scope="col" className="px-3 py-2 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.location_id} className="border-t border-border">
                  <td className="px-3 py-2">{name(row.location_id, "font-medium")}</td>
                  <td className="px-3 py-2 tabular-nums">{row.rank}</td>
                  <td className="px-3 py-2"><span className="inline-flex items-center gap-1.5"><DangerBandGlyph band={row.band} />{BAND_LABEL[row.band]}</span></td>
                  <td className="px-3 py-2">{scoreText(row, ranking.mode)}{ranking.mode === "RETAIL" && <span className="block text-xs text-muted-foreground">{retailReason(row)}</span>}</td>
                  <td className="px-3 py-2">{row.driving_product_id}</td>
                  <td className="px-3 py-2 tabular-nums">{unitsText(row)}</td>
                  <td className="px-3 py-2 tabular-nums">{row.first_deficit_date ? shortDate(row.first_deficit_date) : "None in horizon"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

type Load = { status: "loading" } | { status: "error"; code: string } | { status: "ready"; ranking: Ranking };
type Places = { status: "loading" } | { status: "error"; code: string } | { status: "ready"; list: Schema["LocationList"] };
const codeOf = (error: unknown) => (error instanceof ApiError ? error.code : "REQUEST_FAILED");
const words = (code: string) => code.replaceAll("_", " ").toLowerCase();

/**
 * The chosen v1 network's danger ranking for one forecast run, its locations placed by coordinates, and the site
 * inspector. Kept apart from the demo atlas snapshot so fixture and v1 data never mix.
 */
export function DangerRankingSection({ forecastRunId }: { forecastRunId?: string }) {
  const { network } = useNetwork();
  // A new network or forecast run starts from loading, with nothing selected.
  return network ? <RankingSection key={`${network.id}:${forecastRunId ?? ""}`} network={network} forecastRunId={forecastRunId} /> : null;
}

function RankingSection({ network, forecastRunId }: { network: Network; forecastRunId?: string }) {
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [places, setPlaces] = useState<Places>({ status: "loading" });
  const [attempt, setAttempt] = useState({ ranking: 0, places: 0 });
  const [selected, setSelected] = useState<string | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!forecastRunId) return;
    let active = true;
    networkApi.danger(network.id, forecastRunId).then(
      (ranking) => { if (active) setLoad({ status: "ready", ranking }); },
      (error: unknown) => { if (active) setLoad({ status: "error", code: codeOf(error) }); },
    );
    return () => { active = false; };
  }, [network.id, forecastRunId, attempt.ranking]);
  useEffect(() => {
    if (!forecastRunId) return;
    let active = true;
    networkApi.locations(network.id).then(
      (list) => { if (active) setPlaces({ status: "ready", list }); },
      (error: unknown) => { if (active) setPlaces({ status: "error", code: codeOf(error) }); },
    );
    return () => { active = false; };
  }, [network.id, forecastRunId, attempt.places]);

  const locations = places.status === "ready" ? places.list.locations : [];
  const byId = new Map(locations.map((l) => [l.location_id, l]));
  const label = (id: string) => { const l = byId.get(id); return l ? `${l.name} (${id})` : id; };
  const bands = new Map(load.status === "ready" ? load.ranking.rows.map((r) => [r.location_id, r.band]) : []);
  const { placed, unplaced } = placeLocations(locations);
  const location = selected ? byId.get(selected) : undefined;
  const select = (id: string, element: HTMLElement) => { opener.current = element; setSelected(id); };
  const close = () => { setSelected(null); opener.current?.focus(); };

  return (
    <section aria-labelledby="danger-heading" className="grid gap-3 rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="danger-heading" className="text-lg font-semibold">Danger ranking · {network.name}</h2>
        {network.is_sample && <SampleBadge />}
      </div>
      {!forecastRunId && <p className="text-sm text-muted-foreground">Run a forecast for this network to rank its locations by danger.</p>}
      {forecastRunId && (
        <div className={cn("grid min-w-0 gap-4", location && "lg:grid-cols-[minmax(0,1fr)_24rem]")}>
          <div className="grid min-w-0 content-start gap-3">
            {places.status === "loading" && <p role="status" className="text-sm text-muted-foreground">Loading locations…</p>}
            {places.status === "error" && (
              <div role="alert" className="flex flex-wrap items-center gap-3 text-sm">
                Location names and map unavailable ({words(places.code)}). The ranking below uses location IDs.
                <Button variant="outline" size="sm" onClick={() => { setPlaces({ status: "loading" }); setAttempt((a) => ({ ...a, places: a.places + 1 })); }}>Retry</Button>
              </div>
            )}
            {placed.length > 0 && <LocationMap name={network.name} placed={placed} label={label} bandOf={(id) => bands.get(id) ?? null} onSelect={select} />}
            {unplaced.length > 0 && (
              <div className="grid gap-1 text-xs">
                <p id="unplaced-heading" className="font-medium">Not on the map (no coordinates)</p>
                <ul aria-labelledby="unplaced-heading" className="flex flex-wrap gap-x-3 gap-y-1">{unplaced.map((l) => <li key={l.location_id}>{label(l.location_id)}</li>)}</ul>
              </div>
            )}
            {load.status === "loading" && <p role="status" className="text-sm text-muted-foreground">Loading the danger ranking…</p>}
            {load.status === "error" && (
              <div role="alert" className="flex flex-wrap items-center gap-3 text-sm">
                Danger ranking unavailable ({words(load.code)}).
                <Button variant="outline" size="sm" onClick={() => { setLoad({ status: "loading" }); setAttempt((a) => ({ ...a, ranking: a.ranking + 1 })); }}>Retry</Button>
              </div>
            )}
            {load.status === "ready" && (
              load.ranking.rows.length === 0
                ? <p className="text-sm">No location is projected to run short in this forecast.</p>
                : <DangerRanking ranking={load.ranking} label={label} onSelect={select} canSelect={(id) => byId.has(id)} />
            )}
          </div>
          {location && forecastRunId && <LocationInspector key={location.location_id} network={network} forecastRunId={forecastRunId} location={location} onClose={close} />}
        </div>
      )}
    </section>
  );
}
