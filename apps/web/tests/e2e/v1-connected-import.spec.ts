// covers: V1-A06, V1-A07, V1-A10, V1-A11, V1-A23
import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { CONNECTED, NEEDS_BACKEND, REQUIRED, fixtureText, importNetwork, probe, seedSample, signIn, startImport, uniqueName, type TemplateFile } from "./connected";

// W3-W01, connected only: these import fictional CSV sets (fixtures/v1-connected) through the real
// proxy, API, PostgreSQL and import.v1/enrichment.v1 worker. They count as evidence only in the
// connected run (PP_RUN_CONNECTED=1, as in the CI connected step).

const ALL: readonly TemplateFile[] = [...REQUIRED, "routes", "inbound", "donation_history"];
const NO_EGRESS = "Run the API and worker with no outbound network and set PP_E2E_NO_EGRESS=1 (status/w3-web.md, connected run)";

test.beforeEach(() => test.skip(!CONNECTED, NEEDS_BACKEND));

/** Every text a `role=status` element shows from now on, in order (progress can pass in under a second). */
async function recordStatuses(page: Page) {
  await page.evaluate(() => {
    const seen: string[] = [];
    (window as unknown as { __statuses: string[] }).__statuses = seen;
    new MutationObserver(() => {
      for (const el of document.querySelectorAll('[role="status"]')) {
        const text = el.textContent?.trim();
        if (text && !seen.includes(text)) seen.push(text);
      }
    }).observe(document.body, { subtree: true, childList: true, characterData: true });
  });
  return () => page.evaluate(() => (window as unknown as { __statuses: string[] }).__statuses);
}

test("@V1-A06 @V1-A23 good template set with inbound and donation_history imports and shows progress", async ({ page }) => {
  await signIn(page);
  // V1-SPEC §2 anti-goal: the page says which rows leave the machine, and where (W2-06 carry-in).
  await expect(page.getByText(/addresses? without latitude and longitude .* sent to the US Census Geocoder/i)).toBeVisible();
  // W2-06 carry-in: a pantry given coordinates is never looked up, so it needs both rates or an exclusion.
  await expect(page.getByRole("region", { name: /^locations\.csv/ })).toContainText(/given latitude and longitude.*both poverty_rate and snap_rate.*exclude/i);

  // V1-A06: every template's blank download is exactly the columns its guide explains.
  const sections = page.getByRole("region", { name: /^\w+\.csv/ });
  await expect(sections).toHaveCount(7);
  for (const section of await sections.all()) {
    const columns = await section.locator("tbody th[scope=row]").allTextContents();
    expect(columns.length).toBeGreaterThan(0);
    const [download] = await Promise.all([page.waitForEvent("download"), section.getByRole("link", { name: /^Download blank / }).click()]);
    const header = readFileSync(await download.path(), "utf8").split(/\r?\n/)[0];
    expect(header.split(","), download.suggestedFilename()).toEqual(columns);
  }

  const name = uniqueName("Connected Pantry");
  const statuses = await recordStatuses(page);
  await importNetwork(page, { name, mode: "Pantry", set: "pantry", files: ALL });
  const seen = await statuses();
  expect(seen.some((s) => /^Uploading files: [1-7] of 7$/.test(s)), seen.join(" | ")).toBe(true);
  expect(seen.some((s) => /Starting the checks|Reading files|Checking every row|Saving the network/.test(s)), seen.join(" | ")).toBe(true);

  const summary = page.getByRole("region", { name: "Import finished" });
  // The default as_of_date is the day after the last demand_history date (2026-11-03).
  await expect(summary).toContainText("stock snapshot date 2026-11-04");
  for (const file of ALL) await expect(summary).toContainText(`${file}.csv`);
  await expect(summary).toContainText("Scheduled deliveries: from inbound.csv");
  // V1-A23: the delivery after the 7-day horizon is kept and listed, not planned.
  const outside = summary.getByRole("table", { name: /outside the 7-day horizon/ });
  await expect(outside.getByRole("row")).toHaveCount(2);
  await expect(outside.getByRole("row").nth(1)).toContainText(/P1\s*BEANS\s*5\s*2026-11-20/);

  // W2-06 carry-ins: a real import is not labeled simulated, and the header shows its snapshot date.
  const banner = page.getByRole("banner");
  await expect(banner).toContainText("Snapshot Nov 4, 2026");
  await expect(banner).not.toContainText(/simulated/i);
  await expect(page.getByText(/simulated (network|demo)/i)).toHaveCount(0);

  // W2-06 carry-ins: the overview shows this network's own ranking, not the legacy demo atlas above it
  // (its "Live · simulated network" chip, subtitle and a product picker stuck on "Loading products…").
  await page.goto("/overview");
  await expect(page.getByRole("region", { name: `Danger ranking · ${name}` })).toBeVisible();
  await expect(page.locator("[data-overview-source]")).toHaveCount(0);
  await expect(page.getByText(/simulated/i)).toHaveCount(0);
  await expect(page.getByText(/Loading (products|dates)…/)).toHaveCount(0);
});

test("@V1-A07 bad file rejected: failure message and per-row fixes shown, and no network or dataset version created", async ({ page }) => {
  await signIn(page);
  const tables = ["networks", "dataset_versions", "net_locations", "net_products", "net_batches"];
  const before = probe(tables);
  const name = uniqueName("Rejected Pantry");
  await startImport(page, { name, mode: "Pantry", set: "bad", files: REQUIRED });

  const failure = page.getByRole("alert").filter({ hasText: /^Import failed/ });
  await expect(failure).toBeVisible({ timeout: 90_000 });
  await expect(failure).toContainText(/nothing (was|is) saved/i);
  await expect(failure.getByRole("listitem").first()).toBeVisible(); // at least one next step
  const table = page.getByRole("table", { name: /^Rows to fix/ });
  // One row per rejected class, each with its file, line and a fix (fixtures/v1-connected/bad).
  const expected: [string, number, RegExp][] = [
    ["products", 3, /product_id/], ["inventory", 2, /quantity/], ["inventory", 3, /quantity/],
    ["inventory", 4, /location_id/], ["inventory", 5, /expiry_date|non_expiring/], ["demand_history", 3, /date/],
  ];
  for (const [file, line, column] of expected) {
    const row = table.getByRole("row").filter({ has: page.getByRole("cell", { name: `${file}.csv`, exact: true }) })
      .filter({ has: page.getByRole("cell", { name: String(line), exact: true }) }).filter({ hasText: column });
    await expect(row.first(), `${file}.csv line ${line}`).toBeVisible();
    await expect(row.first().getByRole("cell").last()).not.toHaveText("");
  }

  // Nothing was saved: no network, dataset version or data row, and the switcher doesn't list it.
  expect(probe(tables)).toEqual(before);
  const listed = await page.request.get("/api/v1/networks");
  expect(listed.status()).toBe(200);
  expect(((await listed.json()) as { networks: { name: string }[] }).networks.map((n) => n.name)).not.toContain(name);
  await expect(page.getByRole("region", { name: "Current network" })).not.toContainText(name);
});

test("@V1-A10 offline enrichment marks unknown with retry", async ({ page }) => {
  expect(process.env.PP_E2E_NO_EGRESS, NO_EGRESS).toBe("1");
  await signIn(page);
  expect(fixtureText("unlocated", "locations")).toMatch(/^P4,.*,,,,,$/m); // P4 has no coordinates: it must be looked up
  const name = uniqueName("Offline Pantry");
  await importNetwork(page, { name, mode: "Pantry", set: "unlocated", files: REQUIRED });

  await page.goto("/settings");
  const locations = page.getByRole("region", { name: `Locations in ${name}` });
  // The import queued enrichment.v1; with no egress the Census lookup fails. The page follows the job.
  await expect(locations).toContainText("Address and Census lookups: failed", { timeout: 60_000 });
  const notFound = locations.getByRole("region", { name: "Addresses not found" });
  await expect(notFound).toContainText("The lookup service could not be reached. Affected values stay unknown until a retry succeeds.");
  const blockers = locations.getByRole("alert").filter({ hasText: "EGP_PI_INSPIRED is blocked" });
  await expect(blockers).toContainText("P4: poverty rate, SNAP rate");
  await expect(blockers.getByRole("listitem")).toHaveCount(1); // located pantries came with both rates

  // Retry queues a new lookup; still offline, P4 stays unknown and the retry stays available.
  await notFound.getByRole("button", { name: "Retry lookups" }).click();
  await expect(notFound.getByRole("status")).toContainText(/Lookups queued \(job [0-9a-f]{8}\)/);
  await expect(locations).toContainText("Address and Census lookups: failed", { timeout: 60_000 });
  await expect(blockers).toContainText("P4: poverty rate, SNAP rate");
  await expect(locations.getByRole("button", { name: "Retry lookups" })).toBeEnabled();
});

test('@V1-A10 a sample network\'s pre-filled rates read "sample values"; an import\'s own rates read "entered by you"', async ({ page }) => {
  await signIn(page);
  // Both read fixtures/v1-connected/pantry/locations.csv, where P1–P3 carry poverty and SNAP rates.
  const own = uniqueName("Own Rates Pantry");
  await importNetwork(page, { name: own, mode: "Pantry", set: "pantry", files: REQUIRED });
  await page.goto("/settings");
  const ownLocations = page.getByRole("region", { name: `Locations in ${own}` });
  for (const id of ["P1", "P2", "P3"]) await expect(ownLocations.getByRole("group", { name: `${id} attributes` })).toContainText("Source: entered by you");

  const sample = uniqueName("Sample Pantry");
  seedSample(sample, "PANTRY", "pantry");
  await page.reload();
  await page.getByRole("combobox", { name: "Network", exact: true }).click();
  await page.getByRole("option", { name: new RegExp(sample) }).click();
  const sampleLocations = page.getByRole("region", { name: `Locations in ${sample}` });
  for (const id of ["P1", "P2", "P3"]) {
    const rates = sampleLocations.getByRole("group", { name: `${id} attributes` });
    await expect(rates).toContainText("Source: sample values");
    await expect(rates).not.toContainText("entered by you");
  }
});

test("@V1-A11 route labels", async ({ page }) => {
  await signIn(page);
  const name = uniqueName("Routed Pantry");
  await importNetwork(page, { name, mode: "Pantry", set: "pantry", files: ALL });

  await page.goto("/settings");
  const routes = page.getByRole("region", { name: `Routes in ${name}` }).getByRole("table", { name: /^Routes \(\d+\)/ });
  // Cells concatenate without spaces in textContent; the row's accessible name keeps them apart.
  const row = (from: string, to: string) => routes.getByRole("row", { name: new RegExp(`^${from} ${to} `) });
  // routes.csv overrides the computed value; the disabled route is labeled as such.
  await expect(row("H1", "P1")).toContainText("1 day");
  await expect(row("H1", "P1")).toContainText("from routes.csv");
  await expect(row("H1", "P3")).toContainText("disabled by routes.csv");
  // Every other candidate route is a labeled straight-line estimate (no Google key configured).
  await expect(row("H1", "P2")).toContainText("straight-line estimate");
  for (const text of await routes.locator("tbody tr").allTextContents()) {
    expect(text).toMatch(/straight-line estimate|from routes\.csv/);
    expect(text).not.toMatch(/Google road distance/);
  }
});
