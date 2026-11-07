import { formatUnits } from "@/components/overview/danger-ranking";
import { fallbackReasonLabel, providerLabel } from "@/components/overview/forecast-method";
import type { Schema } from "@/lib/planning-api";

/** The parts of a forecast series the panel explains (contract `ForecastSeriesResult`). */
export type SeriesMethod = Pick<Schema["ForecastSeriesResult"], "status" | "actual_provider" | "fallback_used" | "fallback_reason" | "diagnostics" | "points">;

export const SALES_LABEL = "sales (undercounts demand when shelves were empty)";
export const NOT_EVALUATED = "accuracy not evaluated: needs 35+ days";

type Props = {
  /** "P-12 · WATER-24" */
  label: string;
  basis: Schema["SeriesBacktest"]["basis"];
  score: Schema["BacktestScore"] | null;
  /** null until the run's series is loaded. */
  method: SeriesMethod | null;
  /** Seven-day donation forecast for this location and product; null when none. */
  donationForecast: { units: number; unit: string } | null;
};

const hasQuantiles = (method: SeriesMethod) =>
  method.points.some((p) => p.interval_method === "MODEL_QUANTILES" && p.p10 !== null && p.p90 !== null);

/** Rounded whole percent from a decimal string ("18.4" → 18). */
const about = (pct: string) => Math.round(Math.abs(Number(pct)));

function biasText(biasPct: string | null) {
  if (biasPct === null) return null;
  const n = Number(biasPct);
  if (about(biasPct) === 0) return "It showed no overall lean too high or too low.";
  // V5 §7: error = prediction − actual, so a positive bias is over-forecasting.
  return `It forecast too ${n > 0 ? "high" : "low"} by about ${about(biasPct)}% on average.`;
}

/** V1-SPEC §6.4: what produced this forecast and how far to trust it, on the user's own history. */
export function TrustPanel({ label, basis, score, method, donationForecast }: Props) {
  return (
    <section aria-label={`Forecast trust: ${label}`} className="grid gap-1.5 rounded-lg border border-border bg-card px-3 py-2.5 text-sm">
      <h3 className="font-semibold">{label}</h3>
      <p>Basis: {basis === "sales" ? <span className="font-medium">{SALES_LABEL}</span> : "demand"}</p>
      {method && (
        <>
          <p>
            Method: {method.actual_provider ? providerLabel(method.actual_provider.name) : "none (no forecast produced)"}
            {method.fallback_used
              ? <span className="block text-muted-foreground">Fallback used: {fallbackReasonLabel(method.fallback_reason ?? null)}</span>
              : <span className="text-muted-foreground"> · no fallback</span>}
          </p>
          <p className="text-muted-foreground">
            {method.diagnostics.missing_count === 0
              ? "No missing days in the history."
              : `${method.diagnostics.missing_count} missing day${method.diagnostics.missing_count === 1 ? "" : "s"} in the history, kept as missing (never zero).`}
          </p>
          <p className="text-muted-foreground">
            {hasQuantiles(method)
              ? "Band: p10–p90 model quantiles, not a calibrated interval or a shortage probability."
              : "No band: this method gives a point forecast only."}
          </p>
        </>
      )}
      {score && (score.status === "evaluated" && score.wape_pct !== null ? (
        <div>
          <p className="font-medium">on your last {score.origins_evaluated === 4 ? "4" : score.origins_evaluated} weeks, this forecast was off by about {about(score.wape_pct)}%</p>
          {biasText(score.bias_pct) && <p>{biasText(score.bias_pct)}</p>}
          <p className="text-xs text-muted-foreground">Measured on {score.scored_points} past days of your own history. No claim is made about future accuracy.</p>
        </div>
      ) : <p className="font-medium">{NOT_EVALUATED}</p>)}
      {donationForecast && (
        <p>
          expected donations (forecast, not confirmed): {formatUnits(donationForecast.units, donationForecast.unit)}
          <span className="block text-xs text-muted-foreground">Not counted as supply in any plan or danger score.</span>
        </p>
      )}
    </section>
  );
}
