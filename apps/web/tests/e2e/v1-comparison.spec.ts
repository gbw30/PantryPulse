// covers: V1-A14, V1-A15
import { expect, test, type Page } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";
import { example, mockV1, type Call, type Schemas } from "./v1-mocks";

// Mocked against packages/contracts/examples/v1 (ScenarioV3, SavedComparisonV3, ForecastAccepted,
// NetworkList, Network): proves UI behavior, not the connected app. The examples are a Pantry
// network; the Retail variants below are clones with the mode, roles, prices and methods changed.
// The forecast run comes from the URL until a network's runs can be listed (CR-w1-web-2).

type Scenario = Schemas["ScenarioV3"];
type Saved = Schemas["SavedComparisonV3"];
const accepted = example("ForecastAccepted");
const RUN = example("ScenarioV3").payload.forecast_run_id;
const PANTRY_METHODS = ["NO_TRANSFERS", "EQUAL_SHARE", "MOST_URGENT_FIRST", "CLASSICAL_GP", "EGP_PI_INSPIRED"];
const RETAIL_METHODS = ["NO_TRANSFERS", "SOONEST_EXPIRY_FIRST", "RETAIL_OPTIMIZED"];

/** The ForecastJob a finished job reports, built from the accepted example's identities. */
const finishedJob = (): Schemas["ForecastJob"] => ({ job_id: accepted.job_id, current_attempt_id: accepted.attempt_id, state: "SUCCEEDED", attempts: [] });

function retailNetwork(): Schemas["Network"] {
  const retail = example("NetworkList").networks.find((n) => n.mode === "RETAIL")!;
  // The listed retail sample has no dataset yet; give it the example's dataset so it can be frozen.
  return { ...retail, dataset_version_id: example("Network").dataset_version_id };
}

function retailScenario(network: Schemas["Network"], priced: boolean): Scenario {
  const s = example("ScenarioV3");
  const role = { hub: "distribution_center", pantry: "store" } as const;
  s.network_id = network.id;
  s.payload = { ...s.payload, network_id: network.id, mode: "RETAIL", retail_weights: { w_exp: 1, w_lost: 1 }, vulnerability: [],
    locations: s.payload.locations.map((l) => ({ ...l, role: role[l.role as keyof typeof role] })),
    products: s.payload.products.map((p, i) => ({ ...p, unit_value_usd: priced ? ["4.50", "6.25"][i] : null })) };
  return s;
}

function retailComparison(network: Schemas["Network"], measure: "UNITS" | "USD"): Saved {
  const saved = example("SavedComparisonV3");
  const [none, classical] = saved.result.methods;
  const reason = measure === "USD" ? null : none.usd_unavailable_reason;
  const weights = { w_exp: 1, w_lost: 1 };
  saved.network_id = network.id;
  saved.result = { ...saved.result, mode: "RETAIL", measure, methods: [
    { ...none, measure, usd_unavailable_reason: reason },
    { ...none, method: "SOONEST_EXPIRY_FIRST", measure, usd_unavailable_reason: reason, transfers: classical.transfers, effects: [{ ...classical.effects[0], unmet_with_plan: 30 }] },
    { ...classical, method: "RETAIL_OPTIMIZED", measure, usd_unavailable_reason: reason, retail_weights: weights },
  ] };
  return saved;
}

async function open(page: Page, network: Schemas["Network"], scenarioFor: (body: Schemas["ScenarioOptions"]) => Scenario, comparisonFor: (body: Schemas["ComparisonRequestV3"]) => Saved) {
  let last: Saved | null = null;
  const calls = await mockV1(page, {
    "GET networks": { body: { networks: [network] } },
    [`POST networks/${network.id}/scenarios`]: (call: Call) => ({ status: 201, body: scenarioFor(JSON.parse(call.body!)) }),
    [`POST networks/${network.id}/comparisons`]: (call: Call) => {
      last = comparisonFor(JSON.parse(call.body!));
      return { status: 202, body: { ...accepted, result_url: `/api/v1/networks/${network.id}/comparisons/${last.id}` } };
    },
    [`GET jobs/${accepted.job_id}`]: { body: finishedJob() },
    [`GET networks/${network.id}/comparisons/${example("SavedComparisonV3").id}`]: () => ({ body: last }),
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`/scenarios?forecast_run_id=${RUN}`);
  return { calls, section: page.getByRole("region", { name: `Method comparison · ${network.name}` }) };
}

const posted = (calls: Call[], suffix: string) => calls.filter((c) => c.method === "POST" && c.path.endsWith(suffix)).map((c) => JSON.parse(c.body!));

test("@V1-A14 pantry comparison mocked in both transfer modes", async ({ page }, testInfo) => {
  const network = example("NetworkList").networks.find((n) => n.mode === "PANTRY")!;
  const { calls, section } = await open(page, network,
    (body) => { const s = example("ScenarioV3"); s.payload.transfer_mode = body.transfer_mode; return s; },
    () => example("SavedComparisonV3"));

  await expect(section.getByRole("list", { name: "Methods compared" }).getByRole("listitem")).toHaveCount(5);
  for (const [mode, label] of [["HUB_ONLY", "Hub → pantries only"], ["HUB_AND_PANTRY", "Hub and pantries → pantries"]] as const) {
    await section.getByRole("radio", { name: label }).click();
    await section.getByRole("button", { name: "Freeze scenario" }).click();
    await expect(section.getByText(`Frozen scenario 7293a415 · ${label}`)).toBeVisible();
    await section.getByRole("button", { name: "Compare methods" }).click();

    const results = section.getByRole("region", { name: "Comparison results" });
    await expect(results.getByText(`Same frozen scenario 7293a415 · ${label}`)).toBeVisible();
    for (const name of ["No transfers", "Equal share", "Most-urgent-first", "Classical GP", "EGP-PI-inspired"]) {
      await expect(results.getByRole("region", { name, exact: true })).toBeVisible();
    }
    await expect(results.getByRole("region", { name: "Classical GP", exact: true })).toContainText("Verified by the independent check");
    await expect(results.getByRole("region", { name: "Classical GP", exact: true })).toContainText("optimized per product, with shared capacity split in advance");
    await expect(results.getByRole("region", { name: "EGP-PI-inspired", exact: true })).toContainText("Solver status: UNKNOWN (native)");
    await expect(results.getByRole("region", { name: "EGP-PI-inspired", exact: true }).getByRole("table")).toHaveCount(0);

    expect(posted(calls, "/scenarios").at(-1)).toMatchObject({ transfer_mode: mode, forecast_run_id: RUN, dataset_version_id: network.dataset_version_id });
    expect(posted(calls, "/comparisons").at(-1)).toEqual({ scenario_id: example("ScenarioV3").id, methods: PANTRY_METHODS, measure: "UNITS" });
  }
  await expectNoSeriousA11yViolations(page, testInfo, "v1 pantry comparison");
});

test("@V1-A15 retail comparison mocked in units and USD", async ({ page }) => {
  const network = retailNetwork();
  let priced = false;
  const { calls, section } = await open(page, network,
    (body) => { const s = retailScenario(network, priced); s.payload.transfer_mode = body.transfer_mode; return s; },
    (body) => retailComparison(network, body.measure));

  await expect(section.getByRole("list", { name: "Methods compared" }).getByRole("listitem")).toHaveCount(3);
  // Units: products.csv has no prices, so USD is unavailable and says why.
  await section.getByRole("radio", { name: "DC → stores only" }).click();
  await section.getByLabel("Weight on lost sales").fill("2");
  await section.getByRole("button", { name: "Freeze scenario" }).click();
  await expect(section.getByRole("radio", { name: "USD" })).toBeDisabled();
  await expect(section.getByText("USD unavailable: no unit_value_usd in products.csv for Bottled water, Rice, 5 lb.")).toBeVisible();
  await section.getByRole("radio", { name: "Units" }).click();
  await section.getByRole("button", { name: "Compare methods" }).click();
  const results = section.getByRole("region", { name: "Comparison results" });
  const optimized = results.getByRole("region", { name: "Optimized (minimize expired + lost sales)", exact: true });
  await expect(optimized.getByRole("table", { name: /effects by location/ }).getByRole("columnheader", { name: "Lost sales with plan" })).toBeVisible();
  await expect(optimized).toContainText("Weights: expired ×1, lost sales ×1");
  await expect(results).toContainText("Measure: units · USD unavailable: no unit values in products.csv");
  expect(posted(calls, "/scenarios").at(-1)).toMatchObject({ transfer_mode: "HUB_ONLY", retail_weights: { w_exp: 1, w_lost: 2 } });
  expect(posted(calls, "/comparisons").at(-1)).toMatchObject({ methods: RETAIL_METHODS, measure: "UNITS" });

  // USD: re-freeze after prices are present.
  priced = true;
  await section.getByRole("radio", { name: "DC and stores → stores" }).click();
  await section.getByRole("button", { name: "Freeze scenario" }).click();
  await expect(section.getByText("Frozen scenario 7293a415 · DC and stores → stores")).toBeVisible();
  await section.getByRole("radio", { name: "USD" }).click();
  await section.getByRole("button", { name: "Compare methods" }).click();
  await expect(results).toContainText("Measure: USD");
  await expect(results).not.toContainText("USD unavailable");
  expect(posted(calls, "/comparisons").at(-1)).toMatchObject({ methods: RETAIL_METHODS, measure: "USD" });
});
