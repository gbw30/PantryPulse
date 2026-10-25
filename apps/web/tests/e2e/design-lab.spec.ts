import { expect, test, type Page } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";

async function expectNetworkFits(page: Page) {
  await expect.poll(() => page.locator(".lab-map").evaluate((map) => {
    const bounds = map.getBoundingClientRect();
    return [...map.querySelectorAll(".lab-node")].every((node) => {
      const rect = node.getBoundingClientRect();
      return rect.left >= bounds.left && rect.right <= bounds.right
        && rect.top >= bounds.top && rect.bottom <= bounds.bottom;
    });
  })).toBe(true);
}

for (const [width, height] of [[1440, 900], [1280, 720], [390, 844]]) {
  test(`network fits and stays labeled at ${width}x${height}`, async ({ page }, testInfo) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await page.setViewportSize({ width, height });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/design-lab");
    await expect(page.getByText("Simulated network", { exact: true })).toBeVisible();
    await expect(page.getByText("Planning example \u00b7 amounts are illustrative")).toBeVisible();
    await expect(page.getByText("proposed to move", { exact: true })).toBeVisible();
    await expect(page.getByText("confirmed to move", { exact: true })).toHaveCount(0);
    await expect(page.locator(".lab-node")).toHaveCount(7);
    await expect(page.getByRole("heading", { name: "Seven-day outlook for Riverbend", exact: true })).toBeVisible();
    await expect(page.locator(".lab-outlook-summary")).toHaveText("Without the proposed route, Riverbend runs out of meals on Tuesday and ends the week 120 meals short. With 80 meals from Gator Hub on Tuesday, it ends 40 short.");
    await expect(page.locator(".lab-inspector-answer")).toContainText("on Tuesday toward this week’s 120-meal shortfall");
    await expectNetworkFits(page);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    // Every filter and view control must remain within the visible header.
    for (const control of await page.locator(".lab-stage-header button").all()) {
      const bounds = await control.boundingBox();
      expect(bounds).not.toBeNull();
      expect(bounds!.x).toBeGreaterThanOrEqual(0);
      expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
    }
    // Reset must restore the fit after deliberate zoom and pointer panning.
    await page.getByRole("button", { name: "Zoom in", exact: true }).click();
    const map = await page.locator(".lab-map").boundingBox();
    await page.mouse.move(map!.x + 25, map!.y + 25);
    await page.mouse.down();
    await page.mouse.move(map!.x + 125, map!.y + 65);
    await page.mouse.up();
    await page.getByRole("button", { name: "Fit network", exact: true }).click();
    await expectNetworkFits(page);
    // The default shortage state, routed series and table must be accessible too.
    const tableToggle = page.getByText("View data table", { exact: true });
    await tableToggle.focus();
    await page.keyboard.press("Enter");
    const table = page.getByRole("table");
    await expect(table).toBeVisible();
    await expect(table.getByRole("row", { name: "Mon 19 n/a 14 14 8 to 20", exact: true })).toBeVisible();
    await expect(table.getByRole("row", { name: "Tue 20 n/a −8 72 −16 to 0", exact: true })).toBeVisible();
    await expect(table.getByRole("row", { name: "Sun 25 n/a −120 −40 −141 to −99", exact: true })).toBeVisible();
    await expectNoSeriousA11yViolations(page, testInfo, `design-lab ${width}x${height} Riverbend dark`);
    await page.screenshot({ path: testInfo.outputPath(`design-lab-${width}-dark.png`), fullPage: true });
    await page.getByRole("button", { name: "Switch to light mode" }).click();
    await expectNoSeriousA11yViolations(page, testInfo, `design-lab ${width}x${height} Riverbend light`);
    await page.screenshot({ path: testInfo.outputPath(`design-lab-${width}-light.png`), fullPage: true });
    await tableToggle.focus();
    await page.keyboard.press("Enter");
    await expect(table).toBeHidden();
    await page.getByRole("button", { name: "Switch to dark mode" }).click();
    // The readable selector remains usable when the overview is scaled down.
    await page.getByRole("combobox", { name: "Location", exact: true }).selectOption("pine");
    await expect(page.getByRole("heading", { name: "Pine Ridge", exact: true })).toBeVisible();
    await expectNoSeriousA11yViolations(page, testInfo, `design-lab ${width}x${height} dark`);
    await page.getByRole("button", { name: "Switch to light mode" }).click();
    await expect(page.locator(".lab-light")).toBeVisible();
    await expect(page.locator(".lab-edge-flow")).toHaveCount(0);
    expect(pageErrors).toEqual([]);
    await expectNoSeriousA11yViolations(page, testInfo, `design-lab ${width}x${height} light`);
    await page.getByRole("combobox", { name: "Location", exact: true }).selectOption("hub");
    await expect(page.getByText("The hub holds supply for the network and has no demand forecast.", { exact: false })).toBeVisible();
    await expect(page.locator(".lab-chart")).toHaveCount(0);
    await page.screenshot({ path: testInfo.outputPath(`design-lab-${width}.png`), fullPage: true });
  });
}

test("fit adapts when resizing and when returning from optional 3D", async ({ page }) => {
  await page.goto("/design-lab");
  await page.setViewportSize({ width: 390, height: 844 });
  await expectNetworkFits(page);
  await page.getByRole("button", { name: "3D", exact: true }).click();
  await expect(page.locator(".lab-3d-canvas")).toBeVisible();
  await page.getByRole("combobox", { name: "Location", exact: true }).selectOption("oak");
  await expect(page.getByRole("heading", { name: "Oak Terrace", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "2D", exact: true }).click();
  await expectNetworkFits(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await expectNetworkFits(page);
});

test("unavailable WebGL offers the usable 2D alternative", async ({ page }) => {
  await page.addInitScript(() => {
    const getContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (this: HTMLCanvasElement, ...args) {
      if (String(args[0]).startsWith("webgl")) return null;
      return Reflect.apply(getContext, this, args);
    } as typeof getContext;
  });
  await page.goto("/design-lab");
  await page.getByRole("button", { name: "3D", exact: true }).click();
  await expect(page.getByText("3D view is unavailable in this browser.")).toBeVisible();
  await page.getByRole("button", { name: "Return to 2D", exact: true }).click();
  await expectNetworkFits(page);
  await expect(page.getByRole("combobox", { name: "Location", exact: true })).toBeVisible();
});
