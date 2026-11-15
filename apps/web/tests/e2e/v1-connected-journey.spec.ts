// covers: V1-A14, V1-A15, V1-A16
import { expect, test, type Locator, type Page } from "@playwright/test";
import { CONNECTED, NEEDS_BACKEND, REQUIRED, datasetOf, importNetwork, probe, runForecast, signIn, uniqueName, type TemplateFile } from "./connected";
import { PANTRY_METHODS, PER_PRODUCT, RETAIL_METHODS, SIMULATED, STOCK, compare, decideAndExport, expectAllVerified, freeze, type Opened } from "./connected-plan";

// W3-W02, connected only: a fictional network is imported through the real proxy, API, PostgreSQL and
// production worker (import.v1, enrichment.v1, forecast.v1, or-comparison.v3), forecast from the Overview's
// "Run forecast" control, then frozen, compared, decided and exported in the browser. W4-02 closed
// Escalation E-1: the forecast is a real forecast.v1 run of the set's 42 days of history, not a fixture.

const ALL: readonly TemplateFile[] = [...REQUIRED, "routes", "inbound", "donation_history"];
const RETAIL_FILES: readonly TemplateFile[] = [...REQUIRED, "inbound"];

test.beforeEach(() => test.skip(!CONNECTED, NEEDS_BACKEND));
test.describe.configure({ timeout: 900_000 });

/** Import a fixture set, run its forecast from the Overview and open the comparison for it. */
async function openComparison(page: Page, { base, mode, set, files }: { base: string; mode: "Pantry" | "Retail"; set: string; files: readonly TemplateFile[] }): Promise<Opened> {
  const name = uniqueName(base);
  const id = await importNetwork(page, { name, mode, set, files });
  expect(id).toBeTruthy();
  await runForecast(page, name);
  await page.goto("/scenarios");
  const section = page.getByRole("region", { name: `Method comparison · ${name}` });
  await expect(section).toBeVisible();
  // A chosen v1 network shows only its own comparison: the legacy builder is gone (W3 lead decision).
  await expect(page.getByRole("form", { name: "Scenario builder" })).toHaveCount(0);
  return { id: id!, name, section };
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
  await results!.getByRole("region", { name: "EGP-PI-inspired", exact: true }).getByText("Show rows").click();
  const effects = results!.getByRole("region", { name: /^Effects table for EGP-PI-inspired/ }).getByRole("rowheader");
  for (const header of await effects.allTextContents()) expect(header).toMatch(new RegExp(`^${NAME}$`));
  expect(await effects.count()).toBeGreaterThan(0);

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
  const dataset = await datasetOf(page, opened.id);
  const before = probe(STOCK, dataset);

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

  // Freezing, comparing, deciding, exporting and printing changed no stock row and wrote no new dataset
  // version (W1-S07; no reservation, no dispatch).
  expect(await datasetOf(page, opened.id), "a decision creates no dataset version").toBe(dataset);
  expect(probe(STOCK, dataset)).toEqual(before);
});
