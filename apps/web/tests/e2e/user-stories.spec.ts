import { expect, test, type Page } from "@playwright/test";

// SOURCE-SPEC §4 US-01–12, as amended by SPEC-V5 §§2, 16 (six beneficiaries + hub).
// These are prototype journeys. No browser route is mocked and no test claims
// that authored fixture quantities are a live forecast, allocation or stock write.
const siteMarker = (page: Page, name: string) => page.getByRole("button", { name: new RegExp(`^${name}, `) });

async function choose(page: Page, label: string, option: string | RegExp) {
  await page.getByRole("combobox", { name: label, exact: true }).click();
  await page.getByRole("option", { name: option, exact: typeof option === "string" }).click();
}

async function inspect(page: Page, name: string) {
  await siteMarker(page, name).click();
  await page.getByRole("dialog", { name, exact: true }).getByRole("button", { name: "Inspect site" }).click();
  const inspector = page.getByTestId("site-inspector");
  await expect(inspector.getByRole("heading", { name, exact: true })).toBeVisible();
  return inspector;
}

for (const width of [1440, 390]) {
  test(`US-01 US-04 US-05 US-06 US-12 @story coordinator identifies a deficit and inspects seven daily values at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    await expect(page).toHaveURL(/\/overview$/);
    await expect(page.locator('[data-marker-role="beneficiary"]')).toHaveCount(6);
    await expect(page.locator('[data-marker-role="hub"]')).toHaveCount(1);
    await expect(siteMarker(page, "Riverbend Pantry")).toHaveAccessibleName(/Shortfall.*20 meals unmet/);
    const inspector = await inspect(page, "Riverbend Pantry");
    await expect(inspector).toContainText("40 meals");
    await expect(inspector).toContainText("Sat, Oct 24 · 20 meals unmet");
    await expect(inspector).toContainText("Static fixture · simulated");
    await expect(inspector).toContainText("Routes hidden — no saved plan");
    await inspector.getByRole("tab", { name: "Demand", exact: true }).click();
    await expect(inspector).toContainText("Demand outlook totals 491 meals");
    await expect(inspector).toContainText("Projected unmet: 361 meals, first on Sat, Oct 24");
    await expect(inspector).toContainText("no interval available");
    await inspector.getByRole("button", { name: "Show data table" }).click();
    const table = inspector.getByRole("table");
    await expect(table.getByRole("row")).toHaveCount(8);
    await expect(table.getByRole("row", { name: /Sat,\s*Oct 24/ }).getByRole("cell")).toHaveText(["70", "10", "50", "20"]);
    await expect(table.getByRole("row", { name: /Fri,\s*Oct 30/ }).getByRole("cell")).toHaveText(["60", "10", "10", "50"]);
    await inspector.getByRole("button", { name: "Hide data table" }).click();
    await expect(table).toBeHidden();
    await page.keyboard.press("Escape");
    await expect(siteMarker(page, "Riverbend Pantry")).toBeFocused();
    await choose(page, "Product", /Bottled water/);
    await expect(siteMarker(page, "Riverbend Pantry")).toHaveAccessibleName(/Covered/);
    const water = await inspect(page, "Riverbend Pantry");
    await expect(water).toContainText("400 bottles");
    await expect(water).not.toContainText("meals");
  });
}

test("US-01 US-05 @story a later local day clears past deficits while preserving future warnings", async ({ page }) => {
  await page.goto("/overview");
  await expect(siteMarker(page, "Pine Ridge Pantry")).toHaveAccessibleName(/Shortfall.*14 meals unmet/);
  await choose(page, "Local day", "Sun, Oct 25");
  await expect(siteMarker(page, "Pine Ridge Pantry")).toHaveAccessibleName(/Covered.*no projected deficit from Sun, Oct 25/);
  await expect(siteMarker(page, "Oak Terrace Pantry")).toHaveAccessibleName(/Watch.*Tue, Oct 27/);
  await choose(page, "Local day", "Tue, Oct 27");
  await expect(siteMarker(page, "Oak Terrace Pantry")).toHaveAccessibleName(/Shortfall.*35 meals unmet/);
  await choose(page, "Local day", "Fri, Oct 30");
  await expect(siteMarker(page, "Pine Ridge Pantry")).toHaveAccessibleName(/Covered/);
  await choose(page, "Local day", "Sat, Oct 24");
  await expect(siteMarker(page, "Pine Ridge Pantry")).toHaveAccessibleName(/Shortfall/);
});

test("US-04 US-12 @story insufficient water history is explained without a zero-demand forecast", async ({ page }) => {
  await page.goto("/overview");
  await choose(page, "Product", /Bottled water/);
  await expect(siteMarker(page, "Pine Ridge Pantry")).toHaveAccessibleName(/Not evaluated.*insufficient data/);
  const inspector = await inspect(page, "Pine Ridge Pantry");
  await expect(inspector).toContainText("96 bottles");
  await inspector.getByRole("tab", { name: "Demand", exact: true }).click();
  await expect(inspector).toContainText("No outlook for bottled water at this site: insufficient data.");
  await expect(inspector.getByRole("table")).toHaveCount(0);
  await expect(inspector.getByRole("figure")).toHaveCount(0);
});

test("US-01 @story search has a recoverable no-match state", async ({ page }) => {
  await page.goto("/overview");
  const search = page.getByRole("searchbox", { name: "Search sites or products" });
  await search.fill("unlisted-site-123");
  await expect(page.getByRole("status").filter({ hasText: "No sites match" })).toBeVisible();
  await search.press("Enter");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await search.fill("  OAK  ");
  await search.press("Enter");
  await expect(page.getByRole("dialog", { name: "Oak Terrace Pantry" })).toBeVisible();
  await page.keyboard.press("Escape");
  await search.fill("");
  await expect(page.getByRole("list", { name: "All sites" }).getByRole("button")).toHaveCount(7);
});

test("US-01 US-12 @story retrying a persistent adapter error keeps the alert and empty map", async ({ page }) => {
  await page.goto("/overview?state=unavailable");
  const alert = page.getByRole("alert").filter({ hasText: "Network snapshot unavailable" });
  await expect(alert).toBeVisible();
  await alert.getByRole("button", { name: "Retry" }).click();
  await expect(alert).toBeVisible();
  await expect(page.locator("[data-marker-role]")).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: "Product", exact: true })).toBeDisabled();
  await expect(page).toHaveURL(/state=unavailable/);
});

test("US-02 US-03 US-07 US-09 @story unfinished workflows remain visibly unavailable", async ({ page }) => {
  await page.goto("/overview");
  for (const name of ["Data Explorer", "Recommendations", "Scenario Lab"]) {
    await expect(page.getByRole("button", { name: `${name} (not built yet)`, exact: true })).toBeDisabled();
  }
  const inspector = await inspect(page, "Riverbend Pantry");
  await expect(inspector.getByRole("button", { name: "Go to Site Details" })).toBeDisabled();
  await expect(page.getByText("Allocation engines are not implemented yet.", { exact: false })).toBeVisible();
});

test("US-08 US-10 US-12 @story illustrative proposal explains the residual gap and resets disclosures on site change", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/design-lab");
  await expect(page.locator(".lab-route-card")).toContainText("Gator Hub");
  await expect(page.locator(".lab-route-card")).toContainText("Riverbend");
  await expect(page.locator(".lab-figures")).toHaveText(/120meals needed80can be sent40still needed/);
  const explanation = page.getByRole("button", { name: "Why is this location highlighted?" });
  const notes = page.getByRole("button", { name: "Forecast notes" });
  await explanation.click();
  await expect(explanation).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByText("Expected demand exceeds the meals currently available to this pantry in the example scenario.")).toBeVisible();
  await notes.click();
  await expect(page.getByText("Forecasts do not change physical inventory.", { exact: false })).toBeVisible();
  await page.getByRole("combobox", { name: "Location", exact: true }).selectOption("cedar");
  await expect(page.getByRole("heading", { name: "Cedar Grove", exact: true })).toBeVisible();
  await expect(explanation).toHaveAttribute("aria-expanded", "false");
  await expect(notes).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator(".lab-route-card")).toHaveCount(0);
  await explanation.click();
  await expect(page.getByText("The example scenario shows this location covered for the selected week.")).toBeVisible();
  await page.getByRole("button", { name: "Needs support", exact: true }).click();
  await expect(page.locator(".lab-node.lab-dimmed")).not.toHaveCount(0);
  await page.getByRole("button", { name: "All", exact: true }).click();
  await expect(page.locator(".lab-node.lab-dimmed")).toHaveCount(0);
});

test("US-11 @story reloading restores the same static example (not a database reset)", async ({ page }) => {
  await page.goto("/overview");
  await choose(page, "Product", /Bottled water/);
  await choose(page, "Local day", "Fri, Oct 30");
  await page.reload();
  await expect(page.getByRole("combobox", { name: "Product", exact: true })).toHaveText(/Shelf-stable meals/);
  await expect(page.getByRole("combobox", { name: "Local day", exact: true })).toHaveText(/Sat, Oct 24/);
  await expect(siteMarker(page, "Riverbend Pantry")).toHaveAccessibleName(/Shortfall.*20 meals unmet/);
});
