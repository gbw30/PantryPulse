"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { Schema } from "@/lib/planning-api";
import { pluralize } from "@/components/data-explorer/format";
import { cn } from "@/lib/utils";
import { transferModeLabel, type NetworkMode, type TransferMode } from "@/lib/mode-vocabulary";
import {
  DEFAULT_PANTRY_POLICY, MODE_LABEL, V1_METHOD_LABEL, V1_METHODS, checkMultiplier, policySummary, shortId, usdUnavailableReason, when,
  type ProductInfo, type SiteInfo, type V1Measure,
} from "./model";

// R3 GuidedScenarioStepper: four numbered steps. Desktop shows all; below md one step at a time.

export type StepStatus = "Incomplete" | "Valid draft" | "Ready" | "Saved";
export type Draft = { forecastId: string; assumptionsId: string; mode: "" | Schema["TransferMode"]; days: number; multipliers: Record<string, string>; search: string };
export const modifierKey = (siteId: string, productId: string) => `${siteId}|${productId}`;

type Props = {
  readOnly: boolean;
  busy: boolean;
  jobRunning: boolean;
  forecastRunning: boolean;
  forecastStrategy: Schema["ForecastSubmissionPolicy"]["strategy"];
  onForecastStrategyChange: (strategy: Schema["ForecastSubmissionPolicy"]["strategy"]) => void;
  forecastResult: Schema["ForecastResult"] | null;
  onSelectForecast: (id: string) => void;
  draft: Draft;
  setDraft: (update: (draft: Draft) => Draft) => void;
  catalog: Schema["PlanningCatalog"] | null;
  beneficiaries: SiteInfo[];
  products: ProductInfo[];
  assumptions: Schema["AssumptionsResult"] | null;
  scenario: Schema["ScenarioResult"] | null;
  dirty: boolean;
  diff: string[];
  windows: number[];
  maxSearch: number;
  canGenerate: boolean;
  onSelectAssumptions: (id: string) => void;
  onGenerateForecast: () => void;
  onSaveAssumptions: (text: string) => Promise<string | null>;
  onFreeze: () => void;
  onCompare: () => void;
  constraints: React.ReactNode;
};

const STEP_TITLES = ["Context", "Transfer mode", "Disruptions", "Freeze and compare"];

function StatusBadge({ status }: { status: StepStatus }) {
  return (
    <Badge variant="outline" data-step-status={status} className={cn("text-[11px]", status === "Incomplete" ? "border-dashed text-muted-foreground" : status === "Saved" ? "border-pp-teal text-foreground" : "text-foreground")}>
      {status}
    </Badge>
  );
}

function Step({ n, current, status, children }: { n: number; current: number; status: StepStatus; children: React.ReactNode }) {
  return (
    <motion.fieldset
      key={n}
      initial={false}
      animate={{ opacity: 1 }}
      className={cn("relative min-w-0 border-0 p-0 pl-10", n !== current && "max-md:hidden")}
      aria-describedby={`step-${n}-status`}
    >
      <span aria-hidden="true" className="absolute top-0 left-0 grid size-7 place-items-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">{n}</span>
      <legend className="flex w-full flex-wrap items-center justify-between gap-2 pb-2 text-sm font-semibold">
        <span>Step {n} of 4 · {STEP_TITLES[n - 1]}</span>
        <span id={`step-${n}-status`}><StatusBadge status={status} /></span>
      </legend>
      <div className="grid min-w-0 gap-3 [&>*]:min-w-0 [&_[data-slot=select-trigger]]:max-w-full [&_[data-slot=select-value]]:truncate">{children}</div>
    </motion.fieldset>
  );
}

export function GuidedScenarioStepper(props: Props) {
  const { readOnly, busy, draft, setDraft, catalog, beneficiaries, products, assumptions, scenario, dirty } = props;
  const [current, setCurrent] = useState(1);
  const [jsonOpen, setJsonOpen] = useState(false);
  const [jsonText, setJsonText] = useState("");
  const [jsonError, setJsonError] = useState("");
  const lock = readOnly || busy;
  // One multiplier column per product (up to 8), so a row never wraps onto a second line.
  const columns = { gridTemplateColumns: `minmax(6rem,1fr) repeat(${Math.max(products.length, 1)}, minmax(3.75rem,4.75rem))` };

  const errors = Object.fromEntries(Object.entries(draft.multipliers).map(([k, v]) => [k, checkMultiplier(v)]));
  const invalid = Object.values(errors).some(Boolean);
  const searchValue = Number(draft.search);
  const searchError = !/^\d+$/.test(draft.search.trim()) || searchValue < 1 || searchValue > props.maxSearch ? `Use whole seconds from 1 to ${props.maxSearch}.` : null;
  const saved = !!scenario && !dirty;
  const contextOk = !!draft.forecastId && !!assumptions;
  const s1: StepStatus = !contextOk ? "Incomplete" : saved ? "Saved" : "Valid draft";
  const s2: StepStatus = !draft.mode ? "Incomplete" : saved ? "Saved" : "Valid draft";
  const s3: StepStatus = invalid || !beneficiaries.length ? "Incomplete" : saved ? "Saved" : "Valid draft";
  const ready = contextOk && !!draft.mode && !invalid && beneficiaries.length > 0;
  const s4: StepStatus = saved ? "Saved" : ready ? "Ready" : "Incomplete";
  const canFreeze = !lock && !props.forecastRunning && ready && dirty;
  const canCompare = !lock && !!scenario && !props.jobRunning && !searchError;

  const setMultiplier = (key: string, value: string) => setDraft((d) => ({ ...d, multipliers: { ...d.multipliers, [key]: value } }));

  return (
    <form aria-label="Scenario builder" className="grid min-w-0 gap-5 rounded-lg border border-border bg-card p-4 md:sticky md:top-4 md:max-h-[calc(100svh-2rem)] md:overflow-y-auto md:overscroll-contain focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" tabIndex={0} onSubmit={(e) => e.preventDefault()} data-current-step={current}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold">Scenario builder</h2>
        {dirty && !readOnly && <Badge variant="outline" className="border-pp-warning text-foreground">Draft changes — not computed</Badge>}
      </div>
      <p className="text-xs text-muted-foreground md:hidden" aria-live="polite">Step {current} of 4</p>

      <Step n={1} current={current} status={s1}>
        <div className="grid gap-1.5">
          <Label htmlFor="sl-forecast">Planning-ready forecast</Label>
          <Select value={draft.forecastId} onValueChange={props.onSelectForecast} disabled={lock || !catalog?.forecasts.length}>
            <SelectTrigger id="sl-forecast" className="w-full"><SelectValue placeholder={readOnly ? "Presenter only" : "No planning-ready forecast"} /></SelectTrigger>
            <SelectContent>{catalog?.forecasts.map((f) => <SelectItem key={f.id} value={f.id}>{when(f.recorded_at)} · {shortId(f.id)}</SelectItem>)}</SelectContent>
          </Select>
          {catalog && !catalog.forecasts.length && <p className="text-xs text-muted-foreground">No planning-ready forecast yet. Generate a seven-day forecast from the simulated history first.</p>}
          <Label htmlFor="sl-forecast-method">Forecast method</Label>
          <Select value={props.forecastStrategy} onValueChange={(value) => props.onForecastStrategyChange(value as Props["forecastStrategy"])} disabled={lock || props.jobRunning}>
            <SelectTrigger id="sl-forecast-method" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="SEASONAL_NAIVE">Seasonal naive</SelectItem>
              <SelectItem value="MOVING_AVERAGE">Moving average</SelectItem>
              <SelectItem value="CHRONOS2">Chronos-2 · experimental</SelectItem>
            </SelectContent>
          </Select>
          {props.canGenerate && !readOnly && (
            <Button type="button" variant="outline" size="sm" className="justify-self-start" disabled={lock || props.jobRunning} onClick={props.onGenerateForecast}>Generate forecast</Button>
          )}
          <p className="text-xs text-muted-foreground">Seven-day demand forecast with explicitly enabled moving-average fallback. Chronos requires available model compute; its raw intervals are uncalibrated. Donation predictions never become stock.</p>
          {props.forecastResult && <p role="status" aria-label="Last generated forecast" className="text-xs text-muted-foreground">
            Last generated forecast ({shortId(props.forecastResult.job_id)}): {props.forecastResult.planning_ready ? "planning ready" : "incomplete; unavailable for planning"}. Actual providers: {props.forecastResult.forecast.actual_providers.join(", ") || "none"}.
            {props.forecastResult.forecast.series.some((row) => row.fallback_used) && " Baseline fallback was used."}
          </p>}
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="sl-assumptions">Simulated assumptions version</Label>
          <Select value={draft.assumptionsId} onValueChange={props.onSelectAssumptions} disabled={lock || !catalog?.assumptions.length}>
            <SelectTrigger id="sl-assumptions" className="w-full"><SelectValue placeholder={readOnly ? "Presenter only" : "No assumptions"} /></SelectTrigger>
            <SelectContent>{catalog?.assumptions.map((a) => <SelectItem key={a.id} value={a.id}>{a.label} · {shortId(a.id)}</SelectItem>)}</SelectContent>
          </Select>
          {assumptions && <p className="text-xs text-muted-foreground">Policy {assumptions.payload.policy.version} (read only) · {assumptions.payload.classification}</p>}
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="sl-days">Allocation window</Label>
          <Select value={String(draft.days)} onValueChange={(v) => setDraft((d) => ({ ...d, days: Number(v) }))} disabled={lock}>
            <SelectTrigger id="sl-days" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>{props.windows.map((d) => <SelectItem key={d} value={String(d)}>{d} day{d > 1 ? "s" : ""} (of the 7-day projection)</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <p className="text-xs text-muted-foreground">
          Scope (fixed): {beneficiaries.length || 6} beneficiaries × {products.length || 2} products{products.length ? `: ${products.map((p) => `${p.name} (${p.unit})`).join(", ")}` : ""}.
        </p>
        {!readOnly && assumptions && (
          <details className="text-xs" open={jsonOpen} onToggle={(e) => { const open = (e.currentTarget as HTMLDetailsElement).open; setJsonOpen(open); if (open) { setJsonText(JSON.stringify(assumptions.payload, null, 2)); setJsonError(""); } }}>
            <summary className="cursor-pointer font-medium">Advanced: edit simulated assumptions (JSON)</summary>
            <p className="my-1 text-muted-foreground">Saving creates a new simulated assumptions version; the current one never changes. Routes, capacities, reserves and vulnerability scores are explicit assumptions, not a validated real-world policy.</p>
            <Label htmlFor="sl-json" className="sr-only">Assumptions JSON</Label>
            <Textarea id="sl-json" rows={10} spellCheck={false} className="font-mono text-[11px]" value={jsonText} aria-invalid={!!jsonError || undefined}
              aria-describedby={jsonError ? "sl-json-error" : undefined} onChange={(e) => setJsonText(e.target.value)} disabled={lock} />
            {jsonError && <p id="sl-json-error" className="mt-1 text-pp-danger">{jsonError}</p>}
            <Button type="button" size="sm" variant="outline" className="mt-2" disabled={lock || jsonText === JSON.stringify(assumptions.payload, null, 2)}
              onClick={() => void props.onSaveAssumptions(jsonText).then((error) => setJsonError(error ?? ""))}>Save new assumptions version</Button>
          </details>
        )}
      </Step>

      <Step n={2} current={current} status={s2}>
        <RadioGroup aria-label="Transfer mode (required)" value={draft.mode} disabled={lock} onValueChange={(v) => setDraft((d) => ({ ...d, mode: v as Schema["TransferMode"] }))}>
          {(["HUB_ONLY", "HUB_AND_PANTRY"] as const).map((mode) => (
            <div key={mode} className="flex items-start gap-2">
              <RadioGroupItem id={`sl-mode-${mode}`} value={mode} className="mt-0.5" aria-describedby={`sl-mode-${mode}-hint`} />
              <div className="grid gap-0.5">
                <Label htmlFor={`sl-mode-${mode}`}>{MODE_LABEL[mode]}</Label>
                <span id={`sl-mode-${mode}-hint`} className="text-xs text-muted-foreground">{mode === "HUB_ONLY" ? "Hub → beneficiary transfers only" : "Also eligible beneficiary → beneficiary transfers, protecting the origin’s reserve"}</span>
              </div>
            </div>
          ))}
        </RadioGroup>
        <p className="text-xs text-muted-foreground">Required, no default. Changing it after freezing creates a new scenario.</p>
      </Step>

      <Step n={3} current={current} status={s3}>
        <p className="text-xs text-muted-foreground">Demand multiplier per site and product, 0–3 (1 = baseline forecast). Central forecast estimate.</p>
        <div className="overflow-x-auto">
        <div className="grid gap-1.5" style={{ minWidth: products.length > 2 ? `${7 + products.length * 5.25}rem` : undefined }}>
          <div className="grid gap-x-2 text-[11px] font-medium text-muted-foreground" style={columns} aria-hidden="true">
            <span>Site</span>{products.map((p) => <span key={p.id} className="truncate">{pluralize(p.unit)} ×</span>)}
          </div>
          {beneficiaries.map((site) => (
            <div key={site.id} className="grid items-start gap-x-2" style={columns}>
              <span className="truncate pt-1.5 text-xs">{site.name}</span>
              {products.map((p) => {
                const key = modifierKey(site.id, p.id);
                const value = draft.multipliers[key] ?? "1";
                const error = errors[key];
                return (
                  <div key={p.id} className="grid gap-0.5">
                    <Input type="text" inputMode="decimal" value={value} disabled={lock} aria-label={`${site.name} · ${p.name} demand multiplier`}
                      aria-invalid={error ? true : undefined} aria-describedby={error ? `sl-err-${site.id}-${p.id}` : undefined}
                      className="h-8 px-2 text-xs tabular-nums" onChange={(e) => setMultiplier(key, e.target.value)} />
                    {value.trim() === "1" && !error && <span className="text-[10px] text-muted-foreground">baseline</span>}
                  </div>
                );
              })}
            </div>
          ))}
          {beneficiaries.flatMap((site) => products.map((p) => {
            const error = errors[modifierKey(site.id, p.id)];
            return error ? <p key={`${site.id}-${p.id}`} id={`sl-err-${site.id}-${p.id}`} className="text-xs text-pp-danger">{site.name} · {p.name}: {error}</p> : null;
          }))}
          {!beneficiaries.length && <p className="text-xs text-muted-foreground">{readOnly ? "Sites load for a signed-in presenter." : "No beneficiary sites loaded."}</p>}
        </div>
        </div>
        <p className="text-xs text-muted-foreground">Only the central estimate is offered for planning. Raw model intervals are uncalibrated.</p>
      </Step>

      <Step n={4} current={current} status={s4}>
        <div className="text-xs">
          <p className="font-medium">{scenario ? `Changes vs frozen scenario ${shortId(scenario.id)}` : "New scenario"}</p>
          {scenario && dirty && <ul className="mt-1 list-disc pl-4 text-muted-foreground">{props.diff.map((d) => <li key={d}>{d}</li>)}</ul>}
          {scenario && !dirty && <p className="text-muted-foreground">The draft matches the frozen scenario.</p>}
          <p className="mt-1 text-muted-foreground">Freezing saves an immutable copy of these inputs; no result is computed yet.</p>
        </div>
        <Button type="button" disabled={!canFreeze} onClick={props.onFreeze}>Create frozen scenario</Button>
        <div className="grid gap-1.5">
          <Label htmlFor="sl-search">Search seconds per method</Label>
          <Input id="sl-search" type="number" min={1} max={props.maxSearch} step={1} value={draft.search} disabled={lock} className="h-9 w-28"
            aria-invalid={searchError ? true : undefined} aria-describedby={searchError ? "sl-search-error" : "sl-search-hint"}
            onChange={(e) => setDraft((d) => ({ ...d, search: e.target.value }))} />
          {searchError ? <p id="sl-search-error" className="text-xs text-pp-danger">{searchError}</p>
            : <p id="sl-search-hint" className="text-xs text-muted-foreground">Both methods get identical settings on the same frozen scenario.</p>}
        </div>
        <Button type="button" variant={scenario ? "default" : "outline"} disabled={!canCompare} onClick={props.onCompare}>Compare methods</Button>
        {scenario && dirty && <p className="text-xs text-muted-foreground">Compare runs frozen scenario {shortId(scenario.id)}, not the unsaved draft.</p>}
        <p className="text-xs text-muted-foreground">Simulation only: nothing is reserved, purchased or dispatched.</p>
        {props.constraints}
      </Step>

      <div className="flex justify-between gap-2 md:hidden">
        <Button type="button" variant="outline" disabled={current === 1} onClick={() => setCurrent((c) => Math.max(1, c - 1))}>Previous step</Button>
        <Button type="button" variant="outline" disabled={current === 4} onClick={() => setCurrent((c) => Math.min(4, c + 1))}>Next step</Button>
      </div>
    </form>
  );
}

// v1 comparison setup (V1-SPEC §6.2): an explicit transfer mode with no default, Retail weights, then
// the measure. Freezing saves the inputs; comparing runs every method of the mode on that frozen copy.

type SetupProps = {
  mode: NetworkMode;
  busy: boolean;
  /** The last frozen scenario; comparing always runs this, never the unsaved choices. */
  scenario: Schema["ScenarioV3"] | null;
  /** Why freezing is not possible yet (no dataset or forecast run); null when it is. */
  blocked?: string | null;
  onFreeze: (options: FreezeOptions) => void;
  onCompare: (measure: V1Measure) => void;
};
/** Retail sends weights; Pantry sends its window and policy. Each mode's other fields are null. */
export type FreezeOptions = { transferMode: TransferMode; retailWeights: Schema["RetailWeights"] | null;
  planningDays: number | null; policy: Schema["ORPolicy"] | null };

const TRANSFERS: TransferMode[] = ["HUB_ONLY", "HUB_AND_PANTRY"];
// The server's RetailWeights are strict integers 0–1000.
const weightError = (text: string) => (/^\d{1,4}$/.test(text.trim()) && Number(text) <= 1000 ? null : "Enter a whole number from 0 to 1000.");
// ORPolicy percents are strict integers 0–100; the two attribute shares must add up to 100.
const percentError = (text: string) => (/^\d{1,3}$/.test(text.trim()) && Number(text) <= 100 ? null : "Enter a whole number from 0 to 100.");
const DAYS = ["1", "2", "3"];
type PolicyKey = "lambda" | "beta" | "poverty" | "snap";
const POLICY_FIELDS: [PolicyKey, string, string | null][] = [
  ["lambda", "Vulnerability weight λ (%)", "How much the poverty and SNAP rates raise a pantry's shortfall weight in EGP-PI-inspired and in the poverty-weighted shortfall. 0 turns this off."],
  ["beta", "Weight on total shortfall β (%)", "Classical GP and EGP-PI-inspired: the rest weights the worst single shortfall."],
  ["poverty", "Poverty rate share (%)", null],
  ["snap", "SNAP rate share (%)", null],
];
const share = (id: string) => String(DEFAULT_PANTRY_POLICY.coefficients.find((c) => c.attribute_id === id)?.percent ?? 0);
const POLICY_START: Record<PolicyKey, string> = { lambda: String(DEFAULT_PANTRY_POLICY.lambda_percent),
  beta: String(DEFAULT_PANTRY_POLICY.beta_percent), poverty: share("poverty_rate"), snap: share("snap_rate") };

export function ComparisonSetup({ mode, busy, scenario, blocked = null, onFreeze, onCompare }: SetupProps) {
  const retail = mode === "RETAIL";
  const [transfer, setTransfer] = useState<TransferMode | "">("");
  const [weights, setWeights] = useState({ w_exp: "1", w_lost: "1" });
  const [days, setDays] = useState("");
  const [policy, setPolicy] = useState(POLICY_START);
  // Pantry measures unmet need in units only; Retail picks units or USD per scenario.
  const [measure, setMeasure] = useState<V1Measure | "">(retail ? "" : "UNITS");
  const usdReason = scenario ? usdUnavailableReason(scenario.payload.products) : null;
  const weightErrors = { w_exp: weightError(weights.w_exp), w_lost: weightError(weights.w_lost) };
  // E-1 (lead, 2026-11-07): with both weights 0 the Optimized objective is constant; the server rejects it too.
  const bothZero = !weightErrors.w_exp && !weightErrors.w_lost && Number(weights.w_exp) === 0 && Number(weights.w_lost) === 0
    ? "At least one weight must be above 0." : null;
  const policyErrors = Object.fromEntries(POLICY_FIELDS.map(([key]) => [key, percentError(policy[key])])) as Record<PolicyKey, string | null>;
  const shareError = !policyErrors.poverty && !policyErrors.snap && Number(policy.poverty) + Number(policy.snap) !== 100
    ? "The poverty and SNAP rate shares must add up to 100." : null;
  const pantryReady = !!days && !shareError && !Object.values(policyErrors).some(Boolean);
  const canFreeze = !busy && !blocked && !!transfer && (retail ? !(weightErrors.w_exp || weightErrors.w_lost || bothZero) : pantryReady);
  const canCompare = !busy && !!scenario && (measure === "UNITS" || (measure === "USD" && !usdReason));

  const freeze = () => transfer && onFreeze({ transferMode: transfer,
    retailWeights: retail ? { w_exp: Number(weights.w_exp), w_lost: Number(weights.w_lost) } : null,
    planningDays: retail ? null : Number(days),
    policy: retail ? null : { ...DEFAULT_PANTRY_POLICY, lambda_percent: Number(policy.lambda), beta_percent: Number(policy.beta),
      coefficients: [{ attribute_id: "poverty_rate", percent: Number(policy.poverty) }, { attribute_id: "snap_rate", percent: Number(policy.snap) }] } });

  return (
    <form aria-label="Comparison setup" className="grid min-w-0 gap-5" onSubmit={(e) => e.preventDefault()}>
      <fieldset className="grid min-w-0 gap-3 border-0 p-0">
        <legend className="pb-2 text-sm font-semibold">1 · Freeze a scenario</legend>
        <RadioGroup aria-label="Transfer mode (required)" value={transfer} disabled={busy} onValueChange={(v) => setTransfer(v as TransferMode)}>
          {TRANSFERS.map((t) => (
            <div key={t} className="flex items-center gap-2">
              <RadioGroupItem id={`v1-transfer-${t}`} value={t} />
              <Label htmlFor={`v1-transfer-${t}`}>{transferModeLabel(mode, t)}</Label>
            </div>
          ))}
        </RadioGroup>
        {!transfer && <p className="text-xs text-muted-foreground">Choose a transfer mode first. There is no default.</p>}
        {!retail && (
          <>
            <RadioGroup aria-label="Planning window (required)" value={days} disabled={busy} onValueChange={setDays} className="flex flex-wrap gap-4">
              {DAYS.map((d) => (
                <div key={d} className="flex items-center gap-2">
                  <RadioGroupItem id={`v1-days-${d}`} value={d} />
                  <Label htmlFor={`v1-days-${d}`}>{d === "1" ? "1 day" : `${d} days`}</Label>
                </div>
              ))}
            </RadioGroup>
            {!days && <p className="text-xs text-muted-foreground">Choose a planning window of 1 to 3 days. There is no default.</p>}
            <div role="group" aria-labelledby="v1-policy-heading" className="grid gap-2">
              <p id="v1-policy-heading" className="text-xs font-medium">Goal-programming policy</p>
              <p className="text-xs text-muted-foreground">v1 defaults are the connected flow&apos;s values; change them here. The two shares must add up to 100.</p>
              {POLICY_FIELDS.map(([key, label, hint]) => {
                const own = policyErrors[key];
                const shared = !own && (key === "poverty" || key === "snap") ? shareError : null;
                return (
                  <div key={key} className="grid gap-1">
                    <Label htmlFor={`v1-policy-${key}`}>{label}</Label>
                    <Input id={`v1-policy-${key}`} type="number" min={0} max={100} step={1} className="h-9 w-28" value={policy[key]} disabled={busy}
                      aria-invalid={own || shared ? true : undefined}
                      aria-describedby={own ? `v1-policy-${key}-error` : shared ? "v1-policy-share-error" : undefined}
                      onChange={(e) => setPolicy((p) => ({ ...p, [key]: e.target.value }))} />
                    {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
                    {own && <p id={`v1-policy-${key}-error`} className="text-xs text-pp-danger">{own}</p>}
                  </div>
                );
              })}
              {shareError && <p id="v1-policy-share-error" className="text-xs text-pp-danger">{shareError}</p>}
            </div>
          </>
        )}
        {retail && (
          <div className="grid gap-2">
            <p className="text-xs text-muted-foreground">Optimized minimizes weight × expired units + weight × lost sales. v1 defaults are 1 and 1; change them here.</p>
            {(["w_exp", "w_lost"] as const).map((key) => (
              <div key={key} className="grid gap-1">
                <Label htmlFor={`v1-${key}`}>{key === "w_exp" ? "Weight on expired units" : "Weight on lost sales"}</Label>
                <Input id={`v1-${key}`} type="number" min={0} max={1000} step={1} className="h-9 w-28" value={weights[key]} disabled={busy}
                  aria-invalid={weightErrors[key] || bothZero ? true : undefined}
                  aria-describedby={weightErrors[key] ? `v1-${key}-error` : bothZero ? "v1-weights-error" : undefined}
                  onChange={(e) => setWeights((w) => ({ ...w, [key]: e.target.value }))} />
                {weightErrors[key] && <p id={`v1-${key}-error`} className="text-xs text-pp-danger">{weightErrors[key]}</p>}
              </div>
            ))}
            {bothZero && <p id="v1-weights-error" className="text-xs text-pp-danger">{bothZero}</p>}
          </div>
        )}
        <Button type="button" className="justify-self-start" disabled={!canFreeze} onClick={freeze}>Freeze scenario</Button>
        {blocked && <p className="text-xs text-muted-foreground">{blocked}</p>}
        {scenario && (
          <div className="grid gap-1 text-xs">
            <p className="font-medium">Frozen scenario {shortId(scenario.id)} · {transferModeLabel(mode, scenario.payload.transfer_mode)}</p>
            {scenario.payload.planning_days != null && scenario.payload.policy && <p>{policySummary(scenario.payload.planning_days, scenario.payload.policy)}</p>}
            {scenario.payload.assumptions.length > 0 && (
              <ul aria-label="Assumptions" className="ml-4 list-disc text-muted-foreground">{scenario.payload.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
            )}
          </div>
        )}
      </fieldset>

      <fieldset className="grid min-w-0 gap-3 border-0 p-0">
        <legend className="pb-2 text-sm font-semibold">2 · Compare methods</legend>
        <ol aria-label="Methods compared" className="ml-5 list-decimal text-sm">
          {V1_METHODS[mode].map((m) => <li key={m}>{V1_METHOD_LABEL[m]}</li>)}
        </ol>
        {retail ? (
          <div className="grid gap-1.5">
            <RadioGroup aria-label="Measure" value={measure} disabled={busy || !scenario} onValueChange={(v) => setMeasure(v as V1Measure)} className="flex gap-4">
              <div className="flex items-center gap-2"><RadioGroupItem id="v1-measure-units" value="UNITS" /><Label htmlFor="v1-measure-units">Units</Label></div>
              <div className="flex items-center gap-2"><RadioGroupItem id="v1-measure-usd" value="USD" disabled={!!usdReason} /><Label htmlFor="v1-measure-usd">USD</Label></div>
            </RadioGroup>
            {usdReason && <p className="text-xs text-muted-foreground">USD unavailable: {usdReason}.</p>}
          </div>
        ) : <p className="text-xs text-muted-foreground">Measure: unmet need in units, per product.</p>}
        <Button type="button" className="justify-self-start" variant={scenario ? "default" : "outline"} disabled={!canCompare} onClick={() => measure && onCompare(measure)}>Compare methods</Button>
        <p className="text-xs text-muted-foreground">Every method runs on the same frozen scenario. Simulation only: nothing is reserved or moved.</p>
      </fieldset>
    </form>
  );
}
