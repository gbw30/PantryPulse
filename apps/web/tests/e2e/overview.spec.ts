import { expect, test, type Page } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";

// Mockup-only content (docs/design/reference/overview.md) must never reach the app.
const MOCKUP_ONLY = ["Alex Chen", "Phoenix", "Canned Protein", "Riverside Community Pantry", "62%", "4,200"];

async function expectMarkersInsideMap(page: Page) {
  await expect.poll(() => page.locator("[data-atlas-map]").evaluate((map) => {
    const bounds = map.getBoundingClientRect();
    const markers = [...map.querySelectorAll("[data-marker-role]")];
    return markers.length === 7 && markers.every((marker) => {
      const rect = marker.getBoundingClientRect();
      return rect.left >= bounds.left && rect.right <= bounds.right && rect.top >= bounds.top && rect.bottom <= bounds.bottom;
    });
  })).toBe(true);
}

async function chooseProduct(page: Page, name: RegExp) {
  await page.getByRole("combobox", { name: "Product" }).click();
  await page.getByRole("option", { name }).click();
}

for (const [width, height] of [[1440, 900], [1280, 720], [390, 844]]) {
  test(`network atlas at ${width}x${height}`, async ({ page }, testInfo) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await page.setViewportSize({ width, height });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/overview");

    await expect(page.getByRole("heading", { level: 1, name: "Network Atlas" })).toBeVisible();
    await expect(page.getByText("SIMULATED — static design fixture, not model output")).toBeVisible();
    await expect(page.getByText("Illustrative layout — not geography")).toBeVisible();
    await expect(page.getByText("Simulated network", { exact: true })).toBeVisible();

    // Legend: the four beneficiary states, each named in text.
    const legend = page.getByRole("list", { name: "Site status legend" });
    for (const state of ["Shortfall", "Watch", "Covered", "Not evaluated"]) {
      await expect(legend.getByText(state, { exact: true })).toBeVisible();
    }

    // Six beneficiaries plus one hub, all inside the map canvas.
    await expect(page.locator('[data-marker-role="beneficiary"]')).toHaveCount(6);
    await expect(page.locator('[data-marker-role="hub"]')).toHaveCount(1);
    await expectMarkersInsideMap(page);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);

    // The top bar carries no person, avatar or account identity.
    const topBar = page.getByRole("banner");
    await expect(topBar.locator("img")).toHaveCount(0);
    await expect(topBar.locator('[data-slot="avatar"]')).toHaveCount(0);
    for (const text of MOCKUP_ONLY) await expect(page.getByText(text, { exact: false })).toHaveCount(0);
    await expect(page.getByText("No account · read-only demo")).toHaveCount(width >= 768 ? 1 : 0);

    await expectNoSeriousA11yViolations(page, testInfo, `overview ${width}x${height} default`);
    await page.screenshot({ path: testInfo.outputPath(`overview-${width}-map.png`), fullPage: true });

    // Keyboard selection opens the popover; Esc closes it and returns focus to the marker.
    const marker = page.getByRole("button", { name: /^Riverbend Pantry, beneficiary pantry, / });
    await expect(marker).toHaveAccessibleName(/Shortfall/);
    await marker.focus();
    await page.keyboard.press("Enter");
    const popover = page.getByRole("dialog", { name: "Riverbend Pantry" });
    await expect(popover).toBeVisible();
    await expect(popover).toContainText("Shortfall");
    await expect(popover).toContainText("meals");
    await page.keyboard.press("Escape");
    await expect(popover).toBeHidden();
    await expect(marker).toBeFocused();

    // Inspect site opens the inspector with the selected product's units.
    await page.keyboard.press("Enter");
    await page.getByRole("button", { name: "Inspect site" }).click();
    const inspector = page.getByTestId("site-inspector");
    await expect(inspector.getByRole("heading", { name: "Riverbend Pantry" })).toBeVisible();
    await expect(inspector).toContainText("Shelf-stable meals");
    await expect(inspector).toContainText("meals");
    await expect(inspector).not.toContainText("bottle");
    await expect(inspector.getByText("Routes hidden — no saved plan")).toBeVisible();

    // Demand tab: chart with a text summary and a data table alternative.
    await inspector.getByRole("tab", { name: "Demand" }).click();
    await inspector.getByRole("button", { name: "Show data table" }).click();
    const table = inspector.getByRole("table");
    await expect(table).toBeVisible();
    await expect(table.getByRole("row")).toHaveCount(8);
    await expect(table.getByRole("columnheader", { name: "Demand outlook (meals)" })).toBeVisible();
    await expectNoSeriousA11yViolations(page, testInfo, `overview ${width}x${height} inspector`);
    await page.screenshot({ path: testInfo.outputPath(`overview-${width}.png`), fullPage: true });
    await page.keyboard.press("Escape");
    await expect(marker).toBeFocused();

    // Switching product changes the units and statuses shown.
    await chooseProduct(page, /Bottled water/);
    await expect(page.getByRole("button", { name: /^Pine Ridge Pantry, beneficiary pantry, Not evaluated/ })).toBeVisible();
    await marker.focus();
    await page.keyboard.press("Enter");
    await expect(popover).toContainText("bottles");
    await expect(popover).not.toContainText("meal");
    await page.keyboard.press("Escape");
    await expect(marker).toBeFocused();
    expect(pageErrors).toEqual([]);
  });
}

test("site search filters the list and selects a match", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/overview");
  const search = page.getByRole("searchbox", { name: "Search sites, regions, or products" });
  await search.fill("oak");
  const list = page.getByRole("list", { name: "All sites" });
  await expect(list.getByRole("button")).toHaveCount(1);
  await search.press("Enter");
  await expect(page.getByRole("dialog", { name: "Oak Terrace Pantry" })).toBeVisible();
});

test("loading keeps the legend and a stable skeleton", async ({ page }) => {
  await page.goto("/overview?state=loading");
  await expect(page.getByRole("list", { name: "Site status legend" })).toBeVisible();
  await expect(page.getByText("Loading network snapshot")).toBeVisible();
  await expect(page.locator("[data-marker-role]")).toHaveCount(0);
});

test("empty snapshot shows every site as not evaluated", async ({ page }) => {
  await page.goto("/overview?state=empty");
  await expect(page.getByText("No projection is available for this snapshot.", { exact: false })).toBeVisible();
  const markers = page.locator('[data-marker-role="beneficiary"]');
  await expect(markers).toHaveCount(6);
  for (const marker of await markers.all()) await expect(marker).toHaveAccessibleName(/Not evaluated/);
});

test("adapter failure shows an alert and no fabricated data", async ({ page }) => {
  await page.goto("/overview?state=unavailable");
  // Next.js renders its own empty route-announcer alert; target ours by its text.
  await expect(page.getByRole("alert").filter({ hasText: "Network snapshot unavailable" })).toBeVisible();
  await expect(page.locator("[data-marker-role]")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});
