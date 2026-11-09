// covers: V1-A14, V1-A15, V1-A16
import { readFileSync } from "node:fs";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { CONNECTED, NEEDS_BACKEND, REQUIRED, importNetwork, probe, seedForecast, signIn, uniqueName, type TemplateFile } from "./connected";

// W3-W02, connected only: a fictional network is imported through the real proxy, API, PostgreSQL and
// production worker (import.v1, enrichment.v1, or-comparison.v3), then frozen, compared, decided and
// exported in the browser. The forecast run is a FIXTURE (Escalation E-1, approved): the v1 forecast
// routes are 501 until W3-F03 (W4), so seedForecast() inserts one from the set's forecast.json. These
// tests are evidence for import, scenario, comparison, decisions and export, never for forecasting.

const ALL: readonly TemplateFile[] = [...REQUIRED, "routes", "inbound", "donation_history"];
const RETAIL_FILES: readonly TemplateFile[] = [...REQUIRED, "inbound"];
const PANTRY_METHODS = ["No transfers", "Equal share", "Most-urgent-first", "Classical GP", "EGP-PI-inspired"];
const RETAIL_METHODS = ["No transfers", "Soonest-expiry-first", "Optimized (minimize expired + lost sales)"];
const PER_PRODUCT = "optimized per product, with shared capacity split in advance";
const SIMULATED = "simulated plan; no stock was reserved or moved";
// The W2-05 journey's stock tables: a plan, a decision or an export must not change a row of any.
const STOCK = ["net_batches", "net_inbound", "stock_ledger", "stock_commands", "inventory_lots", "receipts", "receipt_lines",
  "receipt_postings", "supply_receipts", "inventory_versions", "expected_supplies"];
// A real solver run; the comparison ceiling is 690 s, but these networks have 4 locations and 2 products.
const COMPARE_TIMEOUT = 300_000;

test.beforeEach(() => test.skip(!CONNECTED, NEEDS_BACKEND));
test.describe.configure({ timeout: 900_000 });

type Opened = { id: string; name: string; section: Locator };

/** Import a fixture set, seed its fixture forecast run and open the comparison for it. */
async function openComparison(page: Page, { base, mode, set, files }: { base: string; mode: "Pantry" | "Retail"; set: string; files: readonly TemplateFile[] }): Promise<Opened> {
  const name = uniqueName(base);
  const id = await importNetwork(page, { name, mode, set, files });
  expect(id).toBeTruthy();
  const run = await seedForecast(page, id!, set);
  await page.goto(`/scenarios?forecast_run_id=${run}`);
  const section = page.getByRole("region", { name: `Method comparison · ${name}` });
  await expect(section).toBeVisible();
  return { id: id!, name, section };
}

/** Freeze one transfer mode; returns the frozen scenario's short id. */
async function freeze(section: Locator, transfer: string, days?: string) {
  await section.getByRole("radio", { name: transfer }).click();
  if (days) await section.getByRole("radio", { name: days }).click();
  await section.getByRole("button", { name: "Freeze scenario" }).click();
  const frozen = section.getByText(new RegExp(`^Frozen scenario [0-9a-f]{8} · ${transfer}$`));
  await expect(frozen).toBeVisible({ timeout: 30_000 });
  return (await frozen.textContent())!.slice("Frozen scenario ".length, "Frozen scenario ".length + 8);
}

/** Compare every method of the mode on the frozen scenario and wait for the saved result. */
async function compare(section: Locator, scenario: string, transfer: string, measure?: "Units" | "USD") {
  if (measure) await section.getByRole("radio", { name: measure }).click();
  await section.getByRole("button", { name: "Compare methods" }).click();
  const results = section.getByRole("region", { name: "Comparison results" });
  await expect(results.getByText(`Same frozen scenario ${scenario} · ${transfer}`)).toBeVisible({ timeout: COMPARE_TIMEOUT });
  return results;
}

/** Every method ran and its published result passed the independent verifier. */
async function expectAllVerified(results: Locator, methods: readonly string[]) {
  for (const name of methods) {
    const card = results.getByRole("region", { name, exact: true });
    await expect(card, name).toContainText("Verified by the independent check");
  }
}

/** Open the method's suggested actions, select them all and export; returns the CSV and the comparison id. */
async function decideAndExport(page: Page, results: Locator, { id, name }: Opened, method: string, code: string) {
  await results.getByRole("link", { name: `Open suggested actions for ${method}` }).click();
  await expect(page).toHaveURL(/\/decisions\?/);
  const comparisonId = new URL(page.url()).searchParams.get("comparison_id")!;
  const section = page.getByRole("region", { name: `Suggested actions · ${name}` });
  const actions = section.getByRole("article");
  await expect(actions.first()).toBeVisible({ timeout: 30_000 });
  const count = await actions.count();
  for (const action of await actions.all()) {
    for (const part of ["Action", "Why", "Effect"]) await expect(action.getByRole("heading", { name: part, exact: true })).toBeVisible();
  }
  await expect(section).toContainText("effect of this action given the rest of the plan; effects don't add up across actions");
  if (count > 1) await section.getByRole("button", { name: "Select all" }).click();
  else await actions.first().getByRole("checkbox", { name: "Include in export" }).check();
  const exportButton = section.getByRole("button", { name: /^Export CSV/ });
  await expect(exportButton).toHaveText(`Export CSV (${count} action${count === 1 ? "" : "s"})`);
  const [download] = await Promise.all([page.waitForEvent("download"), exportButton.click()]);
  expect(download.suggestedFilename()).toBe(`pantrypulse-plan-${comparisonId.slice(0, 8)}-${code}.csv`);
  const csv = readFileSync((await download.path())!, "utf8");
  // The hash the server saved with this comparison, read independently of the page.
  const saved = await page.request.get(`/api/v1/networks/${id}/comparisons/${comparisonId}`);
  expect(saved.status()).toBe(200);
  const hash = ((await saved.json()) as { result: { scenario_hash: string } }).result.scenario_hash;
  return { csv, hash, count, section };
}

test("@V1-A14 pantry: import → scenario (both transfer modes) → 5 methods verified → decisions → export", async ({ page }) => {
  await signIn(page);
  const opened = await openComparison(page, { base: "Journey Pantry", mode: "Pantry", set: "pantry", files: ALL });
  const { section } = opened;
  await expect(section.getByRole("list", { name: "Methods compared" }).getByRole("listitem")).toHaveText(PANTRY_METHODS);

  let results: Locator | null = null;
  for (const transfer of ["Hub → pantries only", "Hub and pantries → pantries"]) {
    const scenario = await freeze(section, transfer, transfer.startsWith("Hub →") ? "2 days" : undefined);
    results = await compare(section, scenario, transfer);
    await expectAllVerified(results, PANTRY_METHODS);
    for (const optimizer of ["Classical GP", "EGP-PI-inspired"]) {
      const card = results.getByRole("region", { name: optimizer, exact: true });
      await expect(card).toContainText(PER_PRODUCT);
      await expect(card).toContainText(/Products solved: .*Rice/);
    }
  }

  // Locations are named, never shown as bare IDs (fixtures/v1-connected/pantry/locations.csv).
  const NAME = "(North Hub|Pantry One|Pantry Two|Pantry Three)";
  const effects = results!.getByRole("region", { name: /^Effects table for EGP-PI-inspired/ }).getByRole("rowheader");
  for (const header of await effects.allTextContents()) expect(header).toMatch(new RegExp(`^${NAME}$`));

  const { csv, hash, section: decisions } = await decideAndExport(page, results!, opened, "EGP-PI-inspired", "EGP_PI_INSPIRED");
  expect(csv).toContain(hash);
  expect(csv).toContain(SIMULATED);
  for (const action of await decisions.getByRole("article").all()) {
    await expect(action).toContainText(new RegExp(`from ${NAME} to ${NAME}`));
    await expect(action).not.toContainText(/\b(H1|P[1-3])\b/);
  }
});

test("@V1-A15 retail: 3 methods units and USD, USD unavailable with reason on a no-price variant", async ({ page }) => {
  await signIn(page);
  const transfer = "DC → stores only";

  // Priced: every product has unit_value_usd, so both measures run.
  const priced = await openComparison(page, { base: "Journey Retail", mode: "Retail", set: "retail", files: RETAIL_FILES });
  await expect(priced.section.getByRole("list", { name: "Methods compared" }).getByRole("listitem")).toHaveText(RETAIL_METHODS);
  const scenario = await freeze(priced.section, transfer);
  await expect(priced.section.getByRole("radio", { name: "USD" })).toBeEnabled();
  for (const measure of ["Units", "USD"] as const) {
    const results = await compare(priced.section, scenario, transfer, measure);
    await expect(results).toContainText(measure === "USD" ? "Measure: USD (effects below stay in units)" : "Measure: units");
    await expect(results).not.toContainText("USD unavailable");
    await expectAllVerified(results, RETAIL_METHODS);
    await expect(results.getByRole("region", { name: RETAIL_METHODS[2], exact: true })).toContainText("Weights: expired ×1, lost sales ×1");
  }

  // No prices: USD can't be chosen, and both the setup and the result say why.
  const unpriced = await openComparison(page, { base: "Journey Retail no prices", mode: "Retail", set: "retail-noprice", files: RETAIL_FILES });
  const bare = await freeze(unpriced.section, transfer);
  await expect(unpriced.section.getByRole("radio", { name: "USD" })).toBeDisabled();
  await expect(unpriced.section.getByText(/^USD unavailable: no unit_value_usd in products\.csv for (Milk, Bread|Bread, Milk)\.$/)).toBeVisible();
  const results = await compare(unpriced.section, bare, transfer, "Units");
  await expect(results).toContainText(/Measure: units · USD unavailable: \S/);
  await expectAllVerified(results, RETAIL_METHODS);
});

test("@V1-A16 export CSV contains hash and simulated text; stock tables unchanged", async ({ page }) => {
  await signIn(page);
  const opened = await openComparison(page, { base: "Export Pantry", mode: "Pantry", set: "pantry", files: ALL });
  const before = probe(STOCK);

  const transfer = "Hub → pantries only";
  const scenario = await freeze(opened.section, transfer, "3 days");
  const results = await compare(opened.section, scenario, transfer);
  await expectAllVerified(results, PANTRY_METHODS);
  const { csv, hash, count, section } = await decideAndExport(page, results, opened, "Classical GP", "CLASSICAL_GP");

  const [header, ...rows] = csv.trimEnd().split("\n");
  // W1-S07 columns (docs/plans/v1/wave-1.md, test_export_columns).
  expect(header).toBe("scenario_id,scenario_hash,method,network_mode,product,unit,quantity,from,to,ship_date,arrival_date,why,effect,note");
  expect(rows).toHaveLength(count);
  for (const row of rows) {
    expect(row).toContain(hash);
    expect(row).toContain(SIMULATED);
  }

  // The print page carries the same hash and the simulated-plan text.
  await section.getByRole("link", { name: `Print page (${count} action${count === 1 ? "" : "s"})` }).click();
  await expect(page.getByRole("table", { name: "Selected actions" }).locator("tbody tr")).toHaveCount(count);
  await expect(page.getByText(new RegExp(`· hash ${hash}$`))).toBeVisible();
  await expect(page.getByText(SIMULATED)).toBeVisible();

  // Freezing, comparing, deciding, exporting and printing changed no stock row (W1-S07; no reservation, no dispatch).
  expect(probe(STOCK)).toEqual(before);
});
