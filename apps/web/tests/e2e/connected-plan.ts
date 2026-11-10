import { readFileSync } from "node:fs";
import { expect, type Locator, type Page } from "@playwright/test";

// Plan steps shared by the connected v1 specs: freeze a scenario, compare its methods through the real queue,
// then decide and export in the browser (W3-W02, W4-02).

export const PANTRY_METHODS = ["No transfers", "Equal share", "Most-urgent-first", "Classical GP", "EGP-PI-inspired"];
export const RETAIL_METHODS = ["No transfers", "Soonest-expiry-first", "Optimized (minimize expired + lost sales)"];
export const PER_PRODUCT = "optimized per product, with shared capacity split in advance";
export const SIMULATED = "simulated plan; no stock was reserved or moved";
// The W2-05 journey's stock tables: a plan, a decision or an export must not change a row of any.
export const STOCK = ["net_batches", "net_inbound", "stock_ledger", "stock_commands", "inventory_lots", "receipts", "receipt_lines",
  "receipt_postings", "supply_receipts", "inventory_versions", "expected_supplies"];
// A real solver run, up to the comparison ceiling (690 s) plus the queue ahead of it.
export const COMPARE_TIMEOUT = 720_000;

export type Opened = { id: string; name: string; section: Locator };

/** Freeze one transfer mode; returns the frozen scenario's short id. */
export async function freeze(section: Locator, transfer: string, days?: string) {
  await section.getByRole("radio", { name: transfer }).click();
  if (days) await section.getByRole("radio", { name: days }).click();
  const freezeButton = section.getByRole("button", { name: "Freeze scenario" });
  await expect(freezeButton).toBeEnabled(); // a click would wait without limit
  await freezeButton.click();
  const frozen = section.getByText(new RegExp(`^Frozen scenario [0-9a-f]{8} · ${transfer}$`));
  await expect(frozen).toBeVisible({ timeout: 30_000 });
  return (await frozen.textContent())!.slice("Frozen scenario ".length, "Frozen scenario ".length + 8);
}

/** Compare every method of the mode on the frozen scenario and wait for the saved result. */
export async function compare(section: Locator, scenario: string, transfer: string, measure?: "Units" | "USD") {
  if (measure) await section.getByRole("radio", { name: measure }).click();
  const button = section.getByRole("button", { name: "Compare methods" });
  const busy = section.getByRole("status").filter({ hasText: "Comparing methods…" });
  const full = section.getByRole("alert").filter({ hasText: "compute queue full (COMPUTE_QUEUE_FULL)" });
  const deadline = Date.now() + COMPARE_TIMEOUT;
  for (;;) {
    await expect(button).toBeEnabled(); // a click would wait without limit; Retail needs a measure chosen
    await button.click();
    // The previous result stays on screen while the new job runs, so wait for the job, not for a result.
    await expect(busy).toHaveCount(0, { timeout: Math.max(1, deadline - Date.now()) });
    if (!(await full.isVisible())) break;
    // The API queues 2 jobs per kind and the parallel specs share it: wait, as a person would, and compare again.
    expect(Date.now() + 15_000, "the job queue had room before the timeout").toBeLessThan(deadline);
    await section.page().waitForTimeout(15_000);
  }
  await expect(section.getByRole("alert")).toHaveCount(0);
  const results = section.getByRole("region", { name: "Comparison results" });
  await expect(results.getByText(`Same frozen scenario ${scenario} · ${transfer}`)).toBeVisible({ timeout: COMPARE_TIMEOUT });
  return results;
}

/** Every method ran and its published result passed the independent verifier. */
export async function expectAllVerified(results: Locator, methods: readonly string[]) {
  for (const name of methods) {
    const card = results.getByRole("region", { name, exact: true });
    await expect(card, name).toContainText("Verified by the independent check");
  }
}

/** Open the method's suggested actions, select them all and export; returns the CSV and the comparison id. */
export async function decideAndExport(page: Page, results: Locator, { id, name }: Opened, method: string, code: string) {
  await results.getByRole("link", { name: `Open suggested actions for ${method}` }).click();
  await expect(page).toHaveURL(/\/decisions\?/);
  const comparisonId = new URL(page.url()).searchParams.get("comparison_id")!;
  const section = page.getByRole("region", { name: `Suggested actions · ${name}` });
  const actions = section.getByRole("article");
  await expect(actions.first()).toBeVisible({ timeout: 30_000 });
  const count = await actions.count();
  // Every action reads Action, Why and Effect; the first 20 are checked, as a sample plan may list hundreds.
  for (const action of (await actions.all()).slice(0, 20)) {
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
