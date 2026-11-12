// covers: V1-A12, V1-A20
import { expect, test } from "@playwright/test";
import { example, mockV1, publishedRun, envelope } from "./v1-mocks";

// W5-UI02.1 (W4-03 ux-critic finding 1): with a v1 network chosen, /data shows only that network.
// The legacy reads answer 403, which loads the legacy design fixture (Riverbend, Gator Hub, bottles),
// so the test fails if the legacy block renders at all. Mocked against packages/contracts/examples/v1.
const backtest = example("BacktestResult");
const run = example("NetworkForecastRun");
const network = { ...example("NetworkList").networks.find((n) => n.id === backtest.network_id)!, is_sample: true };
const LEGACY = ["forecast-catalog", "dashboard/summary"];
const WIDTHS = [[1440, 900], [1280, 720], [390, 844]] as const;

for (const [width, height] of WIDTHS) {
  test(`@V1-A12 /data shows only the chosen Pantry sample network at ${width}x${height}`, async ({ page }) => {
    const calls = await mockV1(page, {
      "GET networks": { body: { networks: [network] } },
      ...publishedRun(network, run.forecast_run_id),
      [`GET networks/${network.id}/forecasts/${run.forecast_run_id}`]: { body: run },
      [`GET forecasts/${run.job_id}/backtest`]: { body: backtest },
      [`GET networks/${network.id}/locations`]: { body: example("LocationList") },
      ...Object.fromEntries(LEGACY.map((path) => [`GET ${path}`, { status: 403, body: envelope("PRESENTER_REQUIRED") }])),
    });
    await page.setViewportSize({ width, height });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/data");
    await expect(page.getByRole("heading", { level: 1, name: "Data Explorer" })).toBeVisible();
    await expect(page.getByRole("region", { name: `Forecast trust · ${network.name}` })).toContainText("on your last 4 weeks");

    const text = await page.locator("body").innerText();
    for (const word of ["Riverbend", "Gator", "bottles", "simulated network"]) expect(text, `legacy content "${word}"`).not.toContain(word);
    expect(calls.filter((call) => LEGACY.includes(call.path) || call.path.startsWith("shortages/")), "legacy reads").toEqual([]);
  });
}

// W5-UI02.1b (D03 copy, Gabriel 2026-11-12): a backtest whose actuals were all zero can't be scored. It says so,
// never "needs 35+ days" and never a percentage; the short-history series keeps its own wording.
test("@V1-A12 an all-zero backtest says accuracy can't be measured; short history keeps 'needs 35+ days'", async ({ page }) => {
  const zero = example("BacktestResult");
  const good = zero.series.find((s) => s.score?.status === "evaluated")!;
  const unscorable = { status: "not_evaluated_zero_actual" as const, reason: "sum_actual_zero", wape_pct: null, bias_pct: null, origins_evaluated: 4, scored_points: 28 };
  good.score = unscorable;
  zero.locations = zero.locations.map((row) => (row.location_id === good.location_id ? { ...row, score: unscorable } : row));
  await mockV1(page, {
    "GET networks": { body: { networks: [network] } },
    ...publishedRun(network, run.forecast_run_id),
    [`GET networks/${network.id}/forecasts/${run.forecast_run_id}`]: { body: run },
    [`GET forecasts/${run.job_id}/backtest`]: { body: zero },
    [`GET networks/${network.id}/locations`]: { body: example("LocationList") },
  });
  await page.goto("/data");
  const section = page.getByRole("region", { name: `Forecast trust · ${network.name}` });
  const panel = section.getByRole("region", { name: "Forecast trust: Archer Road Pantry (P-12) · WATER-24" });
  await expect(panel).toContainText("accuracy not measurable: every scored day's actual was zero");
  await expect(panel).not.toContainText("35+ days");
  await expect(panel).not.toContainText("%");
  const row = section.getByRole("table", { name: "Accuracy by location and unit" }).getByRole("row", { name: /Archer Road Pantry/ });
  await expect(row).toContainText("accuracy not measurable: every scored day's actual was zero");
  await expect(row).not.toContainText("35+ days");
  // Unchanged: the short-history series and its location row.
  await expect(section.getByRole("region", { name: "Forecast trust: Eastside Pantry (P-07) · WATER-24" })).toContainText("accuracy not evaluated: needs 35+ days");
  await expect(section.getByRole("table", { name: "Accuracy by location and unit" }).getByRole("row", { name: /Eastside Pantry/ })).toContainText("accuracy not evaluated: needs 35+ days");
});
