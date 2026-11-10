// covers: V1-A05, V1-A06, V1-A12, V1-A13, V1-A14, V1-A15, V1-A16, V1-A23
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import {
  CONNECTED, FORECAST_TIMEOUT, NEEDS_BACKEND, REQUIRED, chooseNetwork, datasetOf, importNetwork, probe, runForecast, seedSamples, signIn,
  uniqueName, type Samples, type TemplateFile,
} from "./connected";
import { PANTRY_METHODS, RETAIL_METHODS, SIMULATED, STOCK, compare, decideAndExport, expectAllVerified, freeze } from "./connected-plan";

// W4-02, connected only: the V1-SPEC journey on the fictional samples a first start seeds, through the real
// proxy, API, PostgreSQL and production worker. Every forecast is a real forecast.v1 run, submitted from the
// Overview's "Run forecast" control; every comparison runs through the real queue. Nothing here mocks a route.

const SAMPLE_LABEL = "Sample data — fictional";
const EXAMPLES = path.resolve(__dirname, "../../../../data/templates/examples");
const TEMPLATES = ["locations", "products", "inventory", "demand_history", "routes", "inbound", "donation_history"] as const;
const METHOD_LABEL: Record<string, string> = {
  NO_TRANSFERS: "No transfers", EQUAL_SHARE: "Equal share", MOST_URGENT_FIRST: "Most-urgent-first", CLASSICAL_GP: "Classical GP",
  EGP_PI_INSPIRED: "EGP-PI-inspired", SOONEST_EXPIRY_FIRST: "Soonest-expiry-first", RETAIL_OPTIMIZED: "Optimized (minimize expired + lost sales)",
};
const sha256 = (bytes: Buffer) => createHash("sha256").update(bytes).digest("hex");

let samples: Samples;
test.beforeEach(() => test.skip(!CONNECTED, NEEDS_BACKEND));
// The first-start seed, once per worker: idempotent, like every start (connected/seed_samples.py).
test.beforeAll(() => { if (CONNECTED) samples = seedSamples(); });
test.describe.configure({ timeout: 1_800_000 });

type DangerRow = { location_id: string; rank: number };

async function json<T>(page: Page, url: string): Promise<T> {
  const response = await page.request.get(url);
  expect(response.status(), url).toBe(200);
  return (await response.json()) as T;
}

/** "Name (ID)" per location, as the ranking and the inspector name them. */
async function labels(page: Page, networkId: string) {
  const { locations } = await json<{ locations: { location_id: string; name: string }[] }>(page, `/api/v1/networks/${networkId}/locations`);
  return new Map(locations.map((l) => [l.location_id, `${l.name} (${l.location_id})`]));
}

const danger = (page: Page, networkId: string, run: string) =>
  json<{ rows: DangerRow[] }>(page, `/api/v1/networks/${networkId}/danger?forecast_run_id=${run}`);

/**
 * Freeze, compare and verify every method, count each method's suggested actions (read from the API), then
 * decide and export the method with the most. Returns the counts, recorded for the export and print limits.
 */
async function planAndExport(page: Page, { id, name }: { id: string; name: string }, { transfer, days, methods, measure }: { transfer: string; days?: string; methods: readonly string[]; measure?: "Units" | "USD" }) {
  await page.goto("/scenarios");
  const section = page.getByRole("region", { name: `Method comparison · ${name}` });
  await expect(section.getByRole("list", { name: "Methods compared" }).getByRole("listitem")).toHaveText([...methods]);
  const scenario = await freeze(section, transfer, days);
  const results = await compare(section, scenario, transfer, measure);
  await expectAllVerified(results, methods);

  const href = await results.getByRole("link", { name: /^Open suggested actions for / }).first().getAttribute("href");
  const comparisonId = new URL(href!, "http://local").searchParams.get("comparison_id")!;
  const saved = await json<{ result: { methods: { method: string }[] } }>(page, `/api/v1/networks/${id}/comparisons/${comparisonId}`);
  const counts: Record<string, number> = {};
  for (const { method } of saved.result.methods) {
    const listed = await json<{ actions: unknown[] }>(page, `/api/v1/networks/${id}/comparisons/${comparisonId}/methods/${method}/actions`);
    counts[method] = listed.actions.length;
  }
  console.log(`[W4-02 action counts] ${name} · ${transfer}: ${JSON.stringify(counts)}`);
  test.info().annotations.push({ type: "action counts", description: `${name} · ${transfer}: ${JSON.stringify(counts)}` });
  const [code, most] = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
  expect(most, `a method of ${name} suggests at least one action`).toBeGreaterThan(0);

  const exported = await decideAndExport(page, results, { id, name, section }, METHOD_LABEL[code], code);
  expect(exported.count).toBe(most);
  const [header, ...rows] = exported.csv.trimEnd().split("\n");
  expect(header).toBe("scenario_id,scenario_hash,method,network_mode,product,unit,quantity,from,to,ship_date,arrival_date,why,effect,note");
  expect(rows).toHaveLength(most);
  for (const row of rows) {
    expect(row).toContain(exported.hash);
    expect(row).toContain(SIMULATED);
  }
  // The print page carries every selected action, the same hash and the simulated-plan text.
  await exported.section.getByRole("link", { name: `Print page (${most} action${most === 1 ? "" : "s"})` }).click();
  await expect(page.getByRole("table", { name: "Selected actions" }).locator("tbody tr")).toHaveCount(most);
  await expect(page.getByText(new RegExp(`· hash ${exported.hash}$`))).toBeVisible();
  await expect(page.getByText(SIMULATED)).toBeVisible();
  return counts;
}

test("@V1-A05 both samples are present after first start, each labeled fictional", async ({ page }) => {
  await signIn(page, "/overview");
  expect(samples.PANTRY.name).toBe("Sample Pantry Network (North Central Florida)");
  expect(samples.RETAIL.name).toMatch(/ — sample retail network$/);
  const { networks } = await json<{ networks: { id: string; is_sample: boolean; mode: string }[] }>(page, "/api/v1/networks");
  for (const mode of ["PANTRY", "RETAIL"] as const) {
    expect(networks.find((n) => n.id === samples[mode].id), mode).toMatchObject({ is_sample: true, mode });
  }

  const switcher = page.getByRole("combobox", { name: "Network", exact: true });
  await switcher.click();
  for (const { name } of Object.values(samples)) await expect(page.getByRole("option", { name: `${name} (sample)`, exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  for (const { name } of Object.values(samples)) {
    await chooseNetwork(page, name);
    await expect(page.getByRole("region", { name: `Danger ranking · ${name}` }).getByText(SAMPLE_LABEL, { exact: true })).toBeVisible();
  }
});

test("@V1-A06 example downloads equal data/templates/examples byte for byte, Pantry and Retail", async ({ page }) => {
  await signIn(page, "/import");
  for (const [mode, folder] of [["PANTRY", EXAMPLES], ["RETAIL", path.join(EXAMPLES, "retail")]] as const) {
    // A tab per mode: Chrome blocks a tab's automatic downloads after about ten in a row.
    const tab = await page.context().newPage();
    await tab.goto("/import");
    const section = (name: string) => tab.getByRole("region", { name: new RegExp(`^${name}\\.csv`) });
    // A Retail import's links name RETAIL, and the files are the Retail examples (W3 carry-in).
    await tab.getByRole("radio", { name: new RegExp(`^${mode === "PANTRY" ? "Pantry" : "Retail"} network`) }).click();
    for (const file of TEMPLATES) {
      const link = section(file).getByRole("link", { name: `Download example ${file}.csv` });
      await expect(link).toHaveAttribute("href", `/api/v1/templates/${file}.csv?kind=example&mode=${mode}`);
      const [download] = await Promise.all([tab.waitForEvent("download", { timeout: 60_000 }), link.click()]);
      const got = readFileSync((await download.path())!);
      const want = readFileSync(path.join(folder, `${file}.csv`));
      expect({ bytes: got.length, sha256: sha256(got) }, `${mode} ${file}.csv`).toEqual({ bytes: want.length, sha256: sha256(want) });
    }
    await tab.close();
  }
});

test.describe("Pantry sample", () => {
  test.describe.configure({ mode: "serial" });

  test("@V1-A12 a real forecast.v1 run shows its backtest: WAPE and bias, or accuracy not evaluated", async ({ page }) => {
    await signIn(page, "/overview");
    const { id, name } = samples.PANTRY;
    await chooseNetwork(page, name);
    const run = await runForecast(page, name);
    const backtest = await json<{ forecast_job_id: string; locations: { location_id: string; unit: string; score: { status: string; wape_pct: string | null } }[] }>(
      page, `/api/v1/forecasts/${run.jobId}/backtest`);
    expect(backtest.forecast_job_id).toBe(run.jobId);
    expect(backtest.locations.some((l) => l.score.status === "evaluated"), "90 days of history are enough to score").toBe(true);

    await page.goto("/data");
    const trust = page.getByRole("region", { name: `Forecast trust · ${name}` });
    await expect(trust).toContainText("Forecasts are projections.");
    const table = trust.getByRole("table", { name: "Accuracy by location and unit" });
    const rows = table.getByRole("row");
    await expect(rows).toHaveCount(backtest.locations.length + 1, { timeout: 30_000 });
    const names = await labels(page, id);
    for (const location of backtest.locations) {
      const row = rows.filter({ hasText: names.get(location.location_id)! }).filter({ hasText: location.unit });
      await expect(row.first()).toContainText(location.score.status === "evaluated"
        ? `off by about ${Math.round(Math.abs(Number(location.score.wape_pct)))}%`
        : /accuracy not (evaluated|measurable)/);
    }
    // Each series names its method (the actual provider or its fallback) and how far it was off and leaned.
    const panel = trust.getByRole("region", { name: /^Forecast trust: / }).first();
    await expect(panel).toContainText(/Method: /);
    await expect(panel).toContainText(/off by about \d+%|accuracy not (evaluated|measurable)/);
    await expect(trust).toContainText(/It forecast too (low|high) by about \d+% on average\.|It showed no overall lean too high or too low\./);
    await expect(trust).not.toContainText(/probabilit|confidence interval/i);
  });

  test("@V1-A13 the atlas ranking equals GET /danger and its table, and a row opens the live site inspector", async ({ page }) => {
    await signIn(page, "/overview");
    const { id, name } = samples.PANTRY;
    await chooseNetwork(page, name);
    const { runs } = await json<{ runs: { forecast_run_id: string | null; dataset_version_id: string }[] }>(page, `/api/v1/networks/${id}/forecasts`);
    const dataset = await datasetOf(page, id);
    const run = runs.find((r) => r.dataset_version_id === dataset && r.forecast_run_id)?.forecast_run_id;
    expect(run, "the run the A12 step published").toBeTruthy();
    const { rows } = await danger(page, id, run!);
    expect(rows.length).toBeGreaterThan(0);
    const names = await labels(page, id);
    const expected = [...rows].sort((a, b) => a.rank - b.rank).map((r) => names.get(r.location_id));

    const section = page.getByRole("region", { name: `Danger ranking · ${name}` });
    const list = section.getByRole("list", { name: "Locations by danger" }).getByRole("listitem");
    await expect(list).toHaveCount(rows.length);
    const listed = await list.evaluateAll((items) => items.map((li) => li.getAttribute("aria-label")!.split(", rank ")[0]));
    expect(listed).toEqual(expected);
    await section.getByRole("button", { name: "Table", exact: true }).click();
    const cells = section.getByRole("table", { name: /Danger ranking/ }).locator("tbody tr");
    await expect(cells).toHaveCount(rows.length);
    expect(await cells.evaluateAll((trs) => trs.map((tr) => tr.querySelector("td")!.textContent))).toEqual(expected);
    await section.getByRole("button", { name: "List", exact: true }).click();

    const top = rows.find((r) => r.rank === 1)!;
    const projection = page.waitForResponse((r) => r.url().includes(`/api/v1/networks/${id}/projection?`));
    await section.getByRole("button", { name: names.get(top.location_id)!, exact: true }).click();
    const response = await projection;
    expect(response.status()).toBe(200);
    expect(Object.fromEntries(new URL(response.url()).searchParams)).toEqual({ forecast_run_id: run, location_id: top.location_id });
    const inspector = page.getByRole("region", { name: `Site inspector · ${names.get(top.location_id)!.replace(/ \([^)]*\)$/, "")}` });
    await expect(inspector).toContainText(`Forecast run ${run!.slice(0, 8)}. Forecasts are projections.`);
    await expect(inspector.getByRole("table").first()).toBeVisible();
    await expect(inspector).not.toContainText(/total/i);
  });

  test("@V1-A14 @V1-A16 compare → decisions → export through the real queue; stock tables unchanged", async ({ page }) => {
    await signIn(page, "/overview");
    const { id, name } = samples.PANTRY;
    await chooseNetwork(page, name);
    const before = probe(STOCK, await datasetOf(page, id));
    await planAndExport(page, { id, name }, { transfer: "Hub → pantries only", days: "2 days", methods: PANTRY_METHODS });
    expect(probe(STOCK, await datasetOf(page, id))).toEqual(before);
  });
});

test("@V1-A15 @V1-A16 Retail sample: forecast, compare → decisions → export through the real queue; stock tables unchanged", async ({ page }) => {
  await signIn(page, "/overview");
  const { id, name } = samples.RETAIL;
  await chooseNetwork(page, name);
  await runForecast(page, name);
  const before = probe(STOCK, await datasetOf(page, id));
  await planAndExport(page, { id, name }, { transfer: "DC → stores only", methods: RETAIL_METHODS, measure: "Units" });
  expect(probe(STOCK, await datasetOf(page, id))).toEqual(before);
});

test("@V1-A23 the donation forecast is shown not confirmed, and danger is the same with and without it", async ({ page }) => {
  await signIn(page);
  // The same fictional set twice, once without donation_history.csv (fixtures/v1-connected/pantry).
  const files: readonly TemplateFile[] = [...REQUIRED, "routes", "inbound"];
  const ranked: DangerRow[][] = [];
  let withDonations = { id: "", name: "", run: "" };
  for (const donations of [true, false]) {
    const name = uniqueName(donations ? "Donations Pantry" : "No Donations Pantry");
    const id = (await importNetwork(page, { name, mode: "Pantry", set: "pantry", files: donations ? [...files, "donation_history"] : files }))!;
    const run = await runForecast(page, name);
    ranked.push((await danger(page, id, run.forecastRunId)).rows);
    if (donations) withDonations = { id, name, run: run.forecastRunId };
  }
  expect(ranked[0].length).toBeGreaterThan(0);
  expect(ranked[0]).toEqual(ranked[1]);

  // With donations: the inspector and the trust view show the donation forecast, labeled not confirmed.
  await chooseNetwork(page, withDonations.name);
  await page.goto("/overview");
  const section = page.getByRole("region", { name: `Danger ranking · ${withDonations.name}` });
  await section.getByRole("button", { name: "Pantry One (P1)", exact: true }).click({ timeout: FORECAST_TIMEOUT });
  await expect(page.getByRole("region", { name: "Site inspector · Pantry One" })).toContainText("Donations (forecast, not confirmed)");
  await page.goto("/data");
  await expect(page.getByRole("region", { name: "Forecast trust: Pantry One (P1) · RICE" })).toContainText("expected donations (forecast, not confirmed):");
});
