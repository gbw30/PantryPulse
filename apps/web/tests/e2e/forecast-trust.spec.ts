// covers: V1-A12, V1-A08
import { expect, test } from "@playwright/test";
import { example, mockV1 } from "./v1-mocks";

// Mocked against packages/contracts/examples/v1 (BacktestResult, NetworkList): proves UI behavior, not
// the connected app. The forecast job comes from the URL until runs can be listed (CR-w1-web-2).
const backtest = example("BacktestResult");
const network = example("NetworkList").networks.find((n) => n.id === backtest.network_id)!;

test("@V1-A12 @V1-A08 trust panel with mocked BacktestResult", async ({ page }) => {
  await mockV1(page, {
    "GET networks": { body: { networks: [network] } },
    [`GET forecasts/${backtest.forecast_job_id}/backtest`]: { body: backtest },
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`/data?forecast_job_id=${backtest.forecast_job_id}`);
  const section = page.getByRole("region", { name: `Forecast trust · ${network.name}` });

  const good = section.getByRole("region", { name: "Forecast trust: P-12 · WATER-24" });
  await expect(good).toContainText("on your last 4 weeks, this forecast was off by about 18%");
  await expect(good).toContainText("It forecast too low by about 3% on average.");
  await expect(good).toContainText("Basis: demand");

  const salesSeries = section.getByRole("region", { name: "Forecast trust: P-07 · WATER-24" });
  await expect(salesSeries).toContainText("sales (undercounts demand when shelves were empty)");
  await expect(salesSeries).toContainText("accuracy not evaluated: needs 35+ days");

  for (const row of backtest.ineligible) {
    await expect(section.getByRole("list", { name: "Not forecast" })).toContainText(`${row.location_id} · ${row.product_id}: ${row.reason}`);
  }
});
