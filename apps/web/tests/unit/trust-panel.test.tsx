// covers: V1-A12, V1-A08, V1-A23
import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { TrustPanel, type SeriesMethod } from "@/components/data-explorer/trust-panel";
import { example } from "./contract-examples";

const backtest = example("BacktestResult");
const evaluated = backtest.series.find((s) => s.score.status === "evaluated")!;
const short = backtest.series.find((s) => s.score.status === "not_evaluated_insufficient_history")!;

// No v1 forecast-result example exists yet (CR-w1-web-4); this is the subset of the contract's
// ForecastSeriesResult the panel reads, typed against the generated schema.
const fallback: SeriesMethod = {
  status: "AVAILABLE", fallback_used: true, fallback_reason: "INSUFFICIENT_REFERENCE_WEEKDAYS",
  actual_provider: { name: "MOVING_AVERAGE", adapter_version: "core-v1", package_version: null, checkpoint: null, checkpoint_revision: null },
  diagnostics: { observed_count: 60, missing_count: 3, proxy_fraction: 0, reference_weekday_count: 1, trailing_sample_count: 14 },
  points: Array.from({ length: 7 }, (_, day) => ({ day: `2026-11-0${day + 6}`, central_estimate: 10, estimate_kind: "MEAN" as const, p10: null, p50: null, p90: null, interval_method: "NONE" as const, postprocessing_policy: "reject-invalid-v1" })),
};
const withQuantiles: SeriesMethod = {
  ...fallback, fallback_used: false, fallback_reason: null,
  actual_provider: { name: "CHRONOS2", adapter_version: "chronos2-univariate-cpu-f32-v1", package_version: "2.3.2", checkpoint: "amazon/chronos-2", checkpoint_revision: "r" },
  points: fallback.points.map((p) => ({ ...p, estimate_kind: "MEDIAN" as const, p10: 8, p50: 10, p90: 12, interval_method: "MODEL_QUANTILES" as const })),
};

const panel = (props: Partial<React.ComponentProps<typeof TrustPanel>> = {}) =>
  render(<TrustPanel label="P-12 · WATER-24" basis={evaluated.basis} score={evaluated.score} method={fallback} donationForecast={null} {...props} />);

it("shows method, fallback reason, missing-day count", () => {
  panel();
  const region = screen.getByRole("region", { name: "Forecast trust: P-12 · WATER-24" });
  expect(region).toHaveTextContent("Method: Moving-average baseline");
  expect(region).toHaveTextContent(/Fallback used: .*INSUFFICIENT_REFERENCE_WEEKDAYS/);
  expect(region).toHaveTextContent("3 missing days in the history, kept as missing (never zero)");
});

it('sales basis label "sales (undercounts demand when shelves were empty)"', () => {
  panel({ basis: "sales" });
  expect(screen.getByText("sales (undercounts demand when shelves were empty)")).toBeVisible();
  const { container } = panel({ basis: "demand" });
  expect(container).not.toHaveTextContent("undercounts");
});

it("quantile band only when provider returned quantiles", () => {
  const { unmount } = panel({ method: withQuantiles });
  expect(screen.getByText(/p10–p90 model quantiles, not a calibrated interval or a shortage probability/)).toBeVisible();
  unmount();
  panel({ method: fallback });
  expect(screen.queryByText(/p10–p90/)).not.toBeInTheDocument();
  expect(screen.getByText("No band: this method gives a point forecast only.")).toBeVisible();
});

it('"accuracy not evaluated: needs 35+ days"', () => {
  panel({ score: short.score });
  expect(screen.getByText("accuracy not evaluated: needs 35+ days")).toBeVisible();
  expect(screen.queryByText(/off by about/)).not.toBeInTheDocument();
});

it('"on your last 4 weeks, this forecast was off by about X%" plus over/under bias', () => {
  const { unmount } = panel();
  expect(screen.getByText("on your last 4 weeks, this forecast was off by about 18%")).toBeVisible();
  // bias_pct -3.1: negative error means under-forecast (V5 §7, error = prediction − actual).
  expect(screen.getByText("It forecast too low by about 3% on average.")).toBeVisible();
  expect(screen.getByText(/No claim is made about future accuracy/)).toBeVisible();
  unmount();
  panel({ score: { ...evaluated.score, bias_pct: "4.6" } });
  expect(screen.getByText("It forecast too high by about 5% on average.")).toBeVisible();
});

it('one evaluated week reads "on your last week", never "last 1 weeks"', () => {
  panel({ score: { ...evaluated.score, origins_evaluated: 1 } });
  expect(screen.getByText("on your last week, this forecast was off by about 18%")).toBeVisible();
});

it('"expected donations (forecast, not confirmed): X"', () => {
  panel({ donationForecast: { units: 120, unit: "case" } });
  expect(screen.getByText("expected donations (forecast, not confirmed): 120 cases")).toBeVisible();
  expect(screen.getByText(/Not counted as supply in any plan or danger score/)).toBeVisible();
});

it("an evaluated score without WAPE says why, and still shows its bias", () => {
  // The contract allows status "evaluated" with a null wape_pct (no recorded demand on the scored days).
  panel({ score: { ...evaluated.score, wape_pct: null, bias_pct: "4.6" } });
  expect(screen.getByText("accuracy not measurable: no recorded demand on the scored days")).toBeVisible();
  expect(screen.queryByText(/needs 35\+ days/)).not.toBeInTheDocument();
  expect(screen.getByText("It forecast too high by about 5% on average.")).toBeVisible();
});
