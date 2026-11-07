// covers: V1-A05, V1-A14, V1-A15
import { expect, test, type Page } from "@playwright/test";
import { example, mockV1 } from "./v1-mocks";

// Mocked against packages/contracts/examples/v1 (NetworkList): proves UI behavior, not the connected app.
const list = example("NetworkList");
const pantry = list.networks.find((n) => n.mode === "PANTRY" && !n.is_sample)!;
const sample = list.networks.find((n) => n.is_sample)!;

async function chooseNetwork(page: Page, name: string) {
  await page.getByRole("combobox", { name: "Network", exact: true }).click();
  await page.getByRole("option", { name: new RegExp(name) }).click();
}

test.beforeEach(async ({ page }) => {
  await mockV1(page, { "GET networks": { body: list } });
  await page.emulateMedia({ reducedMotion: "reduce" });
});

test(`@V1-A05 sample network shows "Sample data — fictional"`, async ({ page }) => {
  await page.goto("/overview");
  const switcher = page.getByRole("region", { name: "Current network" });
  await chooseNetwork(page, pantry.name);
  await expect(switcher.getByText("Sample data — fictional")).toHaveCount(0);
  await chooseNetwork(page, sample.name);
  await expect(switcher.getByText("Sample data — fictional")).toBeVisible();
});

test("@V1-A14 receipts, posting, adjustments and lot declarations are not in v1 navigation", async ({ page }) => {
  await page.goto("/data");
  const explorerTabs = page.getByRole("navigation", { name: "Data Explorer views" });
  await expect(explorerTabs.getByRole("link", { name: "Dashboard" })).toBeVisible();
  for (const nav of [explorerTabs, page.getByRole("navigation", { name: "Primary" })]) {
    for (const href of ["/data/operations", "/data/inventory", "/data/inputs"]) {
      await expect(nav.locator(`a[href^="${href}"]`)).toHaveCount(0);
    }
    await expect(nav.getByText(/receipt|posting|adjustment|lot declaration|Operations Board|Inventory & Lots|Data input/i)).toHaveCount(0);
  }
});

test("switching network updates vocabulary", async ({ page }) => {
  await page.goto("/overview");
  const switcher = page.getByRole("region", { name: "Current network" });
  await chooseNetwork(page, pantry.name);
  await expect(switcher).toContainText("Pantry mode · hubs and pantries");
  await chooseNetwork(page, sample.name);
  await expect(switcher).toContainText("Retail mode · distribution centers and stores");
  await expect(switcher).not.toContainText("Pantry mode");
  // The choice survives a reload (per-browser convenience only).
  await page.reload();
  await expect(page.getByRole("combobox", { name: "Network", exact: true })).toContainText(sample.name);
});
