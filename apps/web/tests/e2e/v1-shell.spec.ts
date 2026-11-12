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

// W5-UI05 (W4-03 ux-critic notes): a long network name widened the selector past the sidebar, over page titles.
for (const [width, height] of [[1440, 900], [1280, 720]] as const) {
  test(`@V1-A20 the network selector stays inside the sidebar at ${width}x${height}`, async ({ page }) => {
    const long = { ...sample, name: "Heronfield Market and Partner Stores of the Greater North Central Region — sample retail network" };
    await page.unrouteAll();
    await mockV1(page, { "GET networks": { body: { networks: [long] } } });
    await page.setViewportSize({ width, height });
    await page.goto("/settings");
    // shortcut: the full name joins the accessible name after w5-screens merges (data-label.spec.ts finds "Network" exactly).
    const trigger = page.getByRole("combobox", { name: "Network", exact: true });
    await expect(trigger).toContainText("Heronfield Market");
    const sidebar = (await page.locator("[data-sidebar='sidebar']").first().boundingBox())!;
    const box = (await trigger.boundingBox())!;
    expect(box.x + box.width, "the trigger ends inside the sidebar").toBeLessThanOrEqual(sidebar.x + sidebar.width);
    const title = (await page.getByRole("heading", { level: 1 }).boundingBox())!;
    expect(box.x + box.width <= title.x || box.y + box.height <= title.y || title.y + title.height <= box.y, "the trigger never covers the page title").toBe(true);
  });
}

// W5-UI05 (orchestrator, from w5-screens' connected captures): at 390 the top bar's right-hand group (sample
// label, snapshot date, theme toggle) refused to shrink, so every v1 screen was 481 px wide and scrolled sideways.
for (const path of ["/overview", "/data", "/scenarios", "/import", "/settings"]) {
  test(`@V1-A20 ${path} at 390x844 with a sample network chosen never scrolls sideways`, async ({ page }) => {
    const chosen = { ...sample, name: "Heronfield Market — sample retail network", as_of_date: "2026-11-12" };
    await page.unrouteAll();
    await mockV1(page, { "GET networks": { body: { networks: [chosen] } } });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(path);
    const banner = page.getByRole("banner");
    await expect(banner).toContainText("Sample data — fictional");
    await expect(banner).toContainText("Snapshot Nov 12, 2026");
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  });
}
