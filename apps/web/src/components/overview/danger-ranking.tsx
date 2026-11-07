"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { SampleBadge, useNetwork } from "@/components/shell/network-switcher";
import { networkApi } from "@/lib/network-api";
import { ApiError, type Schema } from "@/lib/planning-api";
import { cn } from "@/lib/utils";
import { pluralize } from "./live-source";
import { DANGER_BANDS, DangerBandGlyph, DangerLegend } from "./risk-legend";

type Ranking = Schema["DangerRanking"];
type Row = Schema["DangerRow"];

const BAND_LABEL = Object.fromEntries(DANGER_BANDS.map((b) => [b.band, b.label])) as Record<Row["band"], string>;
const UNPLURAL = /^(each|lb|lbs|kg|g|oz)$/i;

/** "55 cases": the row's own unit; never combined with another product's. */
export const formatUnits = (n: number, unit: string) => `${n.toLocaleString("en-US")} ${n === 1 || UNPLURAL.test(unit) ? unit : pluralize(unit)}`;
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

/** Ranked locations with a band (text + shape), the driving product in its own unit, and a table view. */
export function DangerRanking({ ranking, view: initialView = "list" }: { ranking: Ranking; view?: View }) {
  const [view, setView] = useState<View>(initialView);
  const rows = [...ranking.rows].sort((a, b) => a.rank - b.rank);
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
            <li key={row.location_id} aria-label={`${row.location_id}, rank ${row.rank}, ${BAND_LABEL[row.band]}`}
              className={cn("grid gap-1 rounded-lg border bg-card px-3 py-2 text-sm", row.band === "high" ? "border-pp-danger/50" : "border-border")}>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="tabular-nums text-muted-foreground">#{row.rank}</span>
                <span className="font-semibold">{row.location_id}</span>
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
                  <td className="px-3 py-2 font-medium">{row.location_id}</td>
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

type Load = { status: "idle" } | { status: "loading" } | { status: "error"; code: string } | { status: "ready"; ranking: Ranking };

/**
 * The chosen v1 network's danger ranking for one forecast run. Kept apart from the demo atlas snapshot
 * so fixture and v1 data never mix. Map placement and the inspector wait on CR-w1-web-1/-3.
 */
export function DangerRankingSection({ forecastRunId }: { forecastRunId?: string }) {
  const { network } = useNetwork();
  const [load, setLoad] = useState<Load>({ status: "idle" });
  const [attempt, setAttempt] = useState(0);
  const networkId = network?.id;
  useEffect(() => {
    if (!networkId || !forecastRunId) return;
    let active = true;
    queueMicrotask(() => { if (active) setLoad({ status: "loading" }); });
    networkApi.danger(networkId, forecastRunId).then(
      (ranking) => { if (active) setLoad({ status: "ready", ranking }); },
      (error: unknown) => { if (active) setLoad({ status: "error", code: error instanceof ApiError ? error.code : "REQUEST_FAILED" }); },
    );
    return () => { active = false; };
  }, [networkId, forecastRunId, attempt]);

  if (!network) return null;
  return (
    <section aria-labelledby="danger-heading" className="grid gap-3 rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="danger-heading" className="text-lg font-semibold">Danger ranking · {network.name}</h2>
        {network.is_sample && <SampleBadge />}
      </div>
      {!forecastRunId && <p className="text-sm text-muted-foreground">Run a forecast for this network to rank its locations by danger.</p>}
      {forecastRunId && load.status === "loading" && <p role="status" className="text-sm text-muted-foreground">Loading the danger ranking…</p>}
      {forecastRunId && load.status === "error" && (
        <div role="alert" className="flex flex-wrap items-center gap-3 text-sm">
          Danger ranking unavailable ({load.code.replaceAll("_", " ").toLowerCase()}).
          <Button variant="outline" size="sm" onClick={() => setAttempt((n) => n + 1)}>Retry</Button>
        </div>
      )}
      {forecastRunId && load.status === "ready" && (
        load.ranking.rows.length === 0
          ? <p className="text-sm">No location is projected to run short in this forecast.</p>
          : <DangerRanking ranking={load.ranking} />
      )}
    </section>
  );
}
