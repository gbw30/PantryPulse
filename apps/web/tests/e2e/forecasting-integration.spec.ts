import { expect, test } from "@playwright/test";
import type { components } from "../../../../packages/contracts/src/schema";
import { expectNoSeriousA11yViolations } from "./a11y";
import type { Methodology } from "../../src/lib/planning-api";

type Schema = components["schemas"];
const id = (n: number) => `${String(n).padStart(8, "0")}-0000-4000-8000-000000000000`;
const recorded = "2026-10-25T12:00:00Z";
const saved = { id: id(1), recorded_at: recorded, label: "Existing baseline" };
const jobId = id(2);
const methodology: Methodology = {
  methods: ["CLASSICAL_GP", "EGP_PI_INSPIRED"], transfer_modes: ["HUB_ONLY", "HUB_AND_PANTRY"], default_transfer_mode: null,
  decision_ids: [], expiry: "FEFO", search_seconds: { default: 120, maximum: 300 }, donor_protection_days: 3,
  planning_window_days: [1, 2, 3], stock_effect: "NONE_SIMULATION_ONLY", limitations: [],
};

function result(fallback: boolean): Schema["ForecastResult"] {
  const provider: Schema["ProviderIdentity"] = {
    name: fallback ? "MOVING_AVERAGE" : "CHRONOS2",
    adapter_version: fallback ? "core-v1" : "chronos2-univariate-cpu-f32-v1",
    package_version: fallback ? null : "2.3.2",
    checkpoint: fallback ? null : "amazon/chronos-2",
    checkpoint_revision: fallback ? null : "29ec3766d36d6f73f0696f85560a422f50e8498c",
  };
  const series = (["DEMAND", "DONATION"] as const).map((target, index): Schema["ForecastSeriesResult"] => {
    const available = fallback || target === "DEMAND";
    return {
      result_id: id(20 + index),
      scope: { key: { organization_id: id(30), site_id: id(40), product_id: id(50), target_type: target },
        unit: "meal", timezone: "America/New_York", calendar_version: "site-local-v1", unit_version: "base-unit-v1", required: true },
      status: available ? "AVAILABLE" : "FAILED", target_basis: target === "DEMAND" ? "REQUESTED" : "RECEIVED",
      diagnostics: { observed_count: 90, missing_count: 0, proxy_fraction: 0, reference_weekday_count: 12, trailing_sample_count: 14 },
      actual_provider: available ? provider : null, fallback_used: fallback,
      fallback_reason: fallback ? "INVALID_PROVIDER_OUTPUT" : null,
      input_hash: "a".repeat(64), generated_at: recorded, warnings: [],
      errors: available ? [] : [{ code: "INVALID_PROVIDER_OUTPUT", message: "Negative raw quantile", category: "PROVIDER", retryable: false }],
      points: available ? Array.from({ length: 7 }, (_, day) => ({
        day: `2026-10-${String(25 + day).padStart(2, "0")}`, central_estimate: 10,
        estimate_kind: fallback ? "MEAN" : "MEDIAN", p10: fallback ? null : 8,
        p50: fallback ? null : 10, p90: fallback ? null : 12,
        interval_method: fallback ? "NONE" : "MODEL_QUANTILES", postprocessing_policy: "reject-invalid-v1",
      })) : [],
    };
  });
  return {
    job_id: jobId, attempt_id: id(3), planning_ready: fallback, published_at: recorded,
    forecast: { schema_version: "forecast-output-experimental-v1", run_id: jobId, input_hash: "a".repeat(64),
      data_cutoff_date: "2026-10-24", generated_at: recorded, completed_at: recorded,
      ready_for_publication: fallback, partial_scope: false, actual_providers: [provider.name], warnings: [], series },
  };
}

// Scenario Lab contract tests; real inference/publication/visitor reads are covered by smoke_chronos_jobs.
for (const fallback of [false, true]) {
  for (const [width, height] of [[1440, 900], [390, 844]]) {
    test(`Scenario Lab displays ${fallback ? "baseline fallback" : "partial Chronos"} at ${width}px`, async ({ page }, testInfo) => {
      let generated = false;
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.context().addCookies([{ name: "pp_csrf", value: "token", url: `http://127.0.0.1:${process.env.PLAYWRIGHT_PORT ?? "3000"}` }]);
      await page.route("**/api/v1/**", async (route) => {
        const request = route.request();
        const pathname = new URL(request.url()).pathname;
        let body: unknown;
        let status = 200;
        if (pathname.endsWith("/allocation-methodology")) {
          body = methodology;
        } else if (pathname.endsWith("/planning-catalog")) {
          body = { source_revision: "a".repeat(64), assumptions: [],
            forecasts: generated && fallback ? [{ ...saved, id: jobId }, saved] : [saved],
            scenarios: [], comparisons: [], next_before: null, next_before_id: null } satisfies Schema["PlanningCatalog"];
        } else if (pathname.endsWith("/forecast-catalog")) {
          body = { sites: [{ id: id(40), name: "Demo pantry", role: "BENEFICIARY", timezone: "America/New_York" }],
            products: [{ id: id(50), name: "Meals", base_unit: "meal" }],
            sources: [{ id: id(60), name: "Simulated history", classification: "SIMULATED" }] } satisfies Schema["ForecastCatalog"];
        } else if (pathname.endsWith("/forecasts") && request.method() === "POST") {
          const submitted = request.postDataJSON() as Schema["ForecastRequest"];
          expect(submitted.policy.strategy).toBe("CHRONOS2");
          expect(submitted.policy.allow_fallback).toBe(true);
          generated = true;
          status = 202;
          body = { job_id: jobId, attempt_id: id(3), state: "QUEUED", replayed: false,
            status_url: `/api/v1/jobs/${jobId}`, result_url: `/api/v1/forecasts/${jobId}` } satisfies Schema["ForecastAccepted"];
        } else if (pathname.endsWith(`/jobs/${jobId}`)) {
          body = { job_id: jobId, current_attempt_id: id(3), state: "SUCCEEDED", attempts: [] } satisfies Schema["ForecastJob"];
        } else if (pathname.endsWith(`/forecasts/${jobId}`)) {
          body = result(fallback);
        } else {
          throw new Error(`Unexpected API request: ${request.method()} ${pathname}`);
        }
        await route.fulfill({ status, json: body });
      });
      await page.setViewportSize({ width, height });
      await page.emulateMedia({ reducedMotion: "reduce" });
      await page.goto("/scenarios");
      await expect(page.getByRole("combobox", { name: "Forecast method" })).toHaveText("Seasonal naive");
      await page.getByRole("combobox", { name: "Forecast method" }).click();
      await page.getByRole("option", { name: "Chronos-2 · experimental" }).click();
      await page.getByRole("button", { name: "Generate forecast", exact: true }).click();
      await expect(page.locator("[data-job-state]")).toHaveAttribute("data-job-state", "SUCCEEDED");
      const provenance = page.getByRole("status", { name: "Last generated forecast" });
      await expect(provenance).toContainText(fallback ? "planning ready. Actual providers: MOVING_AVERAGE. Baseline fallback was used." : "incomplete; unavailable for planning. Actual providers: CHRONOS2.");
      await expect(page.getByRole("combobox", { name: "Planning-ready forecast" })).toContainText((fallback ? jobId : saved.id).slice(0, 8));
      if (!fallback) await expect(page.getByRole("main").getByRole("alert")).toContainText("The forecast was saved but is not planning ready");
      await expect(page.getByRole("banner")).toBeVisible();
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await expectNoSeriousA11yViolations(page, testInfo, `forecast result ${fallback} ${width}`);
      // Old workspace bookmarks use the plural kind; the redirect must restore forecast reads.
      await page.goto(`/optimization?job=${jobId}&kind=forecasts`);
      await expect(page).toHaveURL(/\/scenarios\?/);
      await expect(provenance).toContainText(fallback ? "MOVING_AVERAGE" : "CHRONOS2");
      if (fallback) {
        await page.getByRole("combobox", { name: "Planning-ready forecast" }).click();
        await page.getByRole("option").filter({ hasText: saved.id.slice(0, 8) }).click();
        await expect(provenance).toHaveCount(0);
      }
      expect(errors).toEqual([]);
    });
  }
}

for (const width of [1440, 390]) {
  test(`Scenario Lab exposes all eight product multipliers at ${width}px`, async ({ page }, testInfo) => {
    await page.context().addCookies([{ name: "pp_csrf", value: "token", url: `http://127.0.0.1:${process.env.PLAYWRIGHT_PORT ?? "3000"}` }]);
    const network: Schema["ForecastCatalog"] = {
      sources: [], sites: [{ id: id(40), name: "Demo pantry", role: "BENEFICIARY", timezone: "America/New_York" }],
      products: Array.from({ length: 8 }, (_, n) => ({ id: id(50 + n), name: `Product ${n + 1}`, base_unit: `unit${n + 1}` })),
    };
    await page.route("**/api/v1/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      const body = path.endsWith("/allocation-methodology") ? methodology : path.endsWith("/forecast-catalog") ? network : {
        source_revision: "a".repeat(64), assumptions: [], forecasts: [], scenarios: [], comparisons: [], next_before: null, next_before_id: null,
      } satisfies Schema["PlanningCatalog"];
      await route.fulfill({ json: body });
    });
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/scenarios");
    await expect(page.getByText("Scope (fixed):", { exact: false })).toContainText("8 products");
    if (width < 768) {
      await page.getByRole("button", { name: "Next step" }).click();
      await page.getByRole("button", { name: "Next step" }).click();
    }
    const multipliers = page.getByRole("textbox", { name: /demand multiplier/ });
    await expect(multipliers).toHaveCount(8);
    const last = page.getByRole("textbox", { name: "Demo pantry · Product 8 demand multiplier" });
    await last.fill("1.5");
    await expect(last).toHaveValue("1.5");
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expectNoSeriousA11yViolations(page, testInfo, `eight products ${width}`);
  });
}
