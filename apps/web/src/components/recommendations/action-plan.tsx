"use client";

import { forwardRef } from "react";
import { motion } from "motion/react";
import Link from "next/link";
import { CheckCircle2, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { Schema } from "@/lib/planning-api";
import {
  formatDay, METHOD_LABEL, planImpact, remainingNeed, shortId, SORT_LABEL, transferLabel, units,
  type ActionRow, type Loaded, type MethodOutcome, type SortKey,
} from "./model";
import { ReviewDialog, type ReviewOutcome } from "./review-dialog";
import { BeforeAfterMetric, DeficitTag, LINK, Notice } from "./vocabulary";

const actionKind = (row: ActionRow) => (row.sourceIsHub ? "Transfer from hub" : "Pantry-to-pantry transfer");
const lotLine = (row: ActionRow) => (row.assignment.expires_on ? `Lot expires ${formatDay(row.assignment.expires_on)}` : "Non-expiring lot");

function InspectButton({ row, selected, onSelect }: { row: ActionRow; selected: boolean; onSelect: (row: ActionRow) => void }) {
  return (
    <Button variant={selected ? "secondary" : "outline"} size="sm" className="h-9 min-w-[4.5rem]" aria-pressed={selected}
      aria-label={`Inspect ${transferLabel(row)}`} onClick={(event) => { event.stopPropagation(); onSelect(row); }}>
      Inspect
    </Button>
  );
}

/** TransferRecommendation: one saved assignment, read as "Source → Destination · N units · arrives date". */
export function TransferRecommendation({ row, selected, onSelect, compact = false }: { row: ActionRow; selected: boolean; onSelect: (row: ActionRow) => void; compact?: boolean }) {
  return (
    <li data-action-row={row.key} className={cn("grid gap-2 rounded-lg border bg-card p-3", selected ? "border-pp-teal ring-1 ring-pp-teal" : "border-border")}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <DeficitTag day={row.firstDeficit} />
        <InspectButton row={row} selected={selected} onSelect={onSelect} />
      </div>
      <p className="text-sm font-semibold text-foreground">{row.sourceName} → {row.destinationName}</p>
      <p className="text-sm text-foreground">
        <span className="font-medium">{units(row.assignment.units, row.assignment.unit)}</span>
        <span className="text-muted-foreground"> · {row.product.name} · </span>
        <span>Arrives {formatDay(row.assignment.arrival)}</span>
      </p>
      {!compact && <p className="text-xs text-muted-foreground">{actionKind(row)} · {lotLine(row)}</p>}
    </li>
  );
}

function Queue({ rows, method, selectedKey, onSelect, sort, onSort, isDesktop }: {
  rows: ActionRow[]; method: MethodOutcome; selectedKey: string | null; onSelect: (row: ActionRow) => void;
  sort: SortKey; onSort: (sort: SortKey) => void; isDesktop: boolean;
}) {
  return (
    <Card className="min-w-0 gap-3 py-4">
      <div className="flex flex-wrap items-end justify-between gap-3 px-4">
        <div>
          <h2 className="text-base font-semibold text-foreground">Recommended actions <span className="font-normal text-muted-foreground">({rows.length})</span></h2>
          <p className="text-xs text-muted-foreground">Transfers in the saved {METHOD_LABEL[method.method]} plan. Inspecting changes nothing.</p>
        </div>
        <div className="grid gap-1">
          <span id="rec-sort-label" className="text-xs font-medium text-muted-foreground">Sort</span>
          <Select value={sort} onValueChange={(value) => onSort(value as SortKey)}>
            <SelectTrigger aria-labelledby="rec-sort-label" className="h-9 w-[190px] bg-card"><SelectValue /></SelectTrigger>
            <SelectContent>
              {(Object.keys(SORT_LABEL) as SortKey[]).map((key) => <SelectItem key={key} value={key}>{SORT_LABEL[key]}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>
      {rows.length === 0 ? (
        <div className="px-4">
          <Notice kind="no-transfer" title="No feasible transfer with current resources">
            <p>The verified plan moves no stock. Unmet need stays as listed under Remaining unmet need.</p>
          </Notice>
        </div>
      ) : isDesktop ? (
        <Table className="table-fixed">
          <TableCaption className="mt-2 px-4 text-left text-xs">Each quantity is in its own product unit. Deficit tags are dates from the plan&apos;s projection, not priority scores.</TableCaption>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-[9.5rem] pl-4">First deficit</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Sites</TableHead>
              <TableHead className="w-[6.5rem]">Quantity</TableHead>
              <TableHead className="w-[7.5rem]">Arrival</TableHead>
              <TableHead className="w-[6rem] pr-4"><span className="sr-only">Inspect</span></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => {
              const selected = row.key === selectedKey;
              return (
                <TableRow key={row.key} data-action-row={row.key} data-state={selected ? "selected" : undefined} className="cursor-pointer" onClick={() => onSelect(row)}>
                  <TableCell className="pl-4"><DeficitTag day={row.firstDeficit} /></TableCell>
                  <TableCell className="whitespace-normal">
                    <span className="block font-medium text-foreground">{actionKind(row)}</span>
                    <span className="block text-xs text-muted-foreground">{row.product.name} · {lotLine(row)}</span>
                  </TableCell>
                  <TableCell className="whitespace-normal text-foreground">{row.sourceName} → {row.destinationName}</TableCell>
                  <TableCell className="font-medium text-foreground tabular-nums">{units(row.assignment.units, row.assignment.unit)}</TableCell>
                  <TableCell className="whitespace-normal text-foreground">Arrives {formatDay(row.assignment.arrival)}</TableCell>
                  <TableCell className="pr-4 text-right"><InspectButton row={row} selected={selected} onSelect={onSelect} /></TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      ) : (
        <ul className="grid gap-2 px-4" aria-label="Recommended actions">
          {rows.map((row) => <TransferRecommendation key={row.key} row={row} selected={row.key === selectedKey} onSelect={onSelect} />)}
        </ul>
      )}
    </Card>
  );
}

function Detail({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[8.5rem_minmax(0,1fr)] gap-x-3 py-1 text-sm">
      <dt className="text-muted-foreground">{term}</dt>
      <dd className="text-foreground">{children}</dd>
    </div>
  );
}

function floorsLine(floors: number[] | null, unit: string) {
  if (!floors || floors.length === 0) return "Unavailable";
  return floors.every((floor) => floor === floors[0]) ? `${units(floors[0], unit)} kept each planning day` : floors.map((floor) => units(floor, unit)).join(", ") + " by planning day";
}

function SelectedDetails({ row, reduced }: { row: ActionRow | null; reduced: boolean }) {
  if (!row) return <p className="text-sm text-muted-foreground">No action selected.</p>;
  const a = row.assignment;
  return (
    <motion.dl key={row.key} initial={reduced ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.18 }} className="grid">
      <Detail term="Origin">{row.sourceName}{row.sourceIsHub ? " (hub)" : ""}</Detail>
      <Detail term="Receiving site">{row.destinationName}</Detail>
      <Detail term="Product">{row.product.name} (unit: {a.unit})</Detail>
      <Detail term="Quantity">{units(a.units, a.unit)}</Detail>
      <Detail term="Departs / arrives">{formatDay(a.departure)} → {formatDay(a.arrival)}{row.etaDays !== null ? ` (${row.etaDays}-day route)` : ""}</Detail>
      <Detail term="Lot">{shortId(a.original_lot_id)} · {a.expires_on ? `expires ${formatDay(a.expires_on)}` : "non-expiring"}</Detail>
      <Detail term="First deficit">{row.firstDeficit ? `${formatDay(row.firstDeficit)} at ${row.destinationName}, with this plan` : "None in the planning window, with this plan"}</Detail>
      <Detail term="Sender reserve">{floorsLine(row.reserveFloors, a.unit)}</Detail>
      <Detail term="Cost basis">{units(a.cost_minor, "simulated cost point")}</Detail>
      <Detail term="Stock version">{a.source_revision}</Detail>
    </motion.dl>
  );
}

type PreviewProps = {
  loaded: Loaded; method: MethodOutcome; selected: ActionRow | null; reduced: boolean;
  presenter: boolean; plan: Schema["PlanResult"] | null; reviewed: boolean; reviewStale: boolean;
  onReviewOutcome: (outcome: ReviewOutcome) => void; onReload: () => void;
};

export const ImpactPreview = forwardRef<HTMLElement, PreviewProps>(function ImpactPreview(
  { loaded, method, selected, reduced, presenter, plan, reviewed, reviewStale, onReviewOutcome, onReload }, ref,
) {
  const impact = planImpact(loaded, method);
  const remaining = remainingNeed(loaded, method);
  const baseline = loaded.comparison.result.baseline_metrics ?? null;
  const after = method.verification?.metrics ?? null;
  const scenarioId = loaded.comparison.scenario_id;
  return (
    <Card ref={ref as React.Ref<HTMLDivElement>} data-impact-preview aria-labelledby="impact-preview-title" role="region" className="min-w-0 scroll-mt-20 gap-4 py-4">
      <div className="px-4">
        <h2 id="impact-preview-title" className="text-base font-semibold text-foreground">Impact Preview</h2>
        <p className="text-xs text-muted-foreground">Saved, independently replayed {METHOD_LABEL[method.method]} plan · simulated</p>
      </div>

      <section className="grid gap-1 px-4" aria-labelledby="selected-action-title">
        <h3 id="selected-action-title" className="text-sm font-semibold text-foreground">Selected action details</h3>
        <p aria-live="polite" className="text-sm font-medium text-foreground">{selected ? `Selected action: ${transferLabel(selected)}` : "Selected action: none"}</p>
        <SelectedDetails row={selected} reduced={reduced} />
      </section>

      <section className="grid gap-1 border-t border-border px-4 pt-3" aria-labelledby="plan-impact-title">
        <h3 id="plan-impact-title" className="text-sm font-semibold text-foreground">Plan-level projected impact</h3>
        <p className="text-xs text-muted-foreground">Whole-plan projection on frozen scenario {shortId(scenarioId)}; {"not attributable to one transfer (V5 OPEN-02)"}. Baseline is no transfers on the same scenario.</p>
        {impact.map((item) => (
          <div key={item.product.id} className="mt-1">
            <p className="text-xs font-semibold text-foreground">{item.product.name} ({item.product.unit})</p>
            <dl>
              <BeforeAfterMetric metric="unmet" product={item.product.unit} label="Unmet need, baseline → plan"
                before={item.unmetBefore === null ? null : units(item.unmetBefore, item.product.unit)} after={units(item.unmetAfter, item.product.unit)} />
              <BeforeAfterMetric metric="sites-short" product={item.product.unit} label="Sites with unmet need"
                before={item.sitesShortBefore === null ? null : units(item.sitesShortBefore, "site")} after={units(item.sitesShortAfter, "site")} />
              <BeforeAfterMetric metric="served" product={item.product.unit} label={`Served of ${units(item.target, item.product.unit)} target`}
                before={item.servedBefore === null ? null : units(item.servedBefore, item.product.unit)} after={units(item.servedAfter, item.product.unit)} />
              <BeforeAfterMetric metric="expired" product={item.product.unit} label="Projected expired"
                before={item.expiredBefore === null ? null : units(item.expiredBefore, item.product.unit)} after={item.expiredAfter === null ? null : units(item.expiredAfter, item.product.unit)} />
            </dl>
          </div>
        ))}
        <dl className="mt-1">
          <BeforeAfterMetric metric="cost" product="cost-point" label="Simulated cost points (whole plan)"
            before={baseline ? baseline.cost_minor.toLocaleString("en-US") : null} after={after ? after.cost_minor.toLocaleString("en-US") : null} />
        </dl>
      </section>

      <section className="grid gap-1 border-t border-border px-4 pt-3" aria-labelledby="remaining-title">
        <h3 id="remaining-title" className="text-sm font-semibold text-foreground">Remaining unmet need</h3>
        {remaining.length === 0 ? (
          <p className="text-sm text-foreground">No unmet need remains in the planning window with this plan.</p>
        ) : (
          <ul data-remaining className="grid gap-1">
            {remaining.map((item) => (
              <li key={`${item.siteId}|${item.product.id}`} className="flex justify-between gap-3 text-sm">
                <span className="text-foreground">{item.siteName} · {item.product.name}</span>
                <span className="font-medium text-foreground tabular-nums">{units(item.unmet, item.product.unit)} of {units(item.target, item.product.unit)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="grid gap-2 border-t border-border bg-card px-4 pt-3 max-lg:sticky max-lg:bottom-0 max-lg:pb-3">
        {reviewStale && (
          <Notice kind="review-stale" tone="warning" title="This plan changed since it was loaded; nothing was recorded.">
            <p>Reload the comparison before reviewing (PLAN_REVISION_MISMATCH).</p>
            <Button variant="outline" size="sm" className="w-fit" onClick={onReload}>Reload comparison</Button>
          </Notice>
        )}
        {reviewed && (
          <p role="status" className="flex items-center gap-2 text-sm font-medium text-foreground">
            <CheckCircle2 aria-hidden="true" className="size-4 text-pp-teal" /><span>Reviewed — simulation</span>
          </p>
        )}
        {presenter && plan && !reviewStale && <ReviewDialog plan={plan} scenarioId={scenarioId} onOutcome={onReviewOutcome} />}
        {presenter && !plan && <p className="text-xs text-muted-foreground">Review unavailable: the saved plan record could not be read{loaded.plansError ? ` (${loaded.plansError})` : ""}.</p>}
        <Link className={cn(LINK, "text-sm")} href={`/scenarios?comparison=${loaded.comparison.id}`}>Compare in Scenario Lab</Link>
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground"><ShieldCheck aria-hidden="true" className="size-3.5" />No stock, purchase or dispatch effect</p>
      </div>
    </Card>
  );
});

export function ActionPlan(props: {
  loaded: Loaded; method: MethodOutcome; rows: ActionRow[]; selected: ActionRow | null; onSelect: (row: ActionRow) => void;
  sort: SortKey; onSort: (sort: SortKey) => void; isDesktop: boolean; previewRef: React.Ref<HTMLElement>;
} & Omit<PreviewProps, "loaded" | "method" | "selected">) {
  const { loaded, method, rows, selected, onSelect, sort, onSort, isDesktop, previewRef, ...preview } = props;
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px] lg:items-start">
      <Queue rows={rows} method={method} selectedKey={selected?.key ?? null} onSelect={onSelect} sort={sort} onSort={onSort} isDesktop={isDesktop} />
      <ImpactPreview ref={previewRef} loaded={loaded} method={method} selected={selected} {...preview} />
    </div>
  );
}
