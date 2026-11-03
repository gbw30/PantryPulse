import { expect, test } from "@playwright/test";

test("US-01 @story mobile coordinator can open navigation and search using the header controls", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/overview");
  await page.getByRole("button", { name: "Open navigation" }).click();
  const menu = page.getByRole("dialog");
  await expect(menu.getByRole("link", { name: "Overview", exact: true })).toBeVisible();
  await expect(menu.getByRole("button", { name: "Scenario Lab (not built yet)" })).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(menu).toBeHidden();
  await page.getByRole("button", { name: "Search", exact: true }).click();
  const search = page.getByRole("searchbox", { name: "Search sites or products" });
  await expect(search).toBeVisible();
  await search.fill("willow");
  await search.press("Enter");
  await expect(page.getByRole("dialog", { name: "Willow Creek Pantry" })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Close search", exact: true }).click();
  await expect(search).toBeHidden();
});

test("US-01 @story map zoom is bounded and fit restores positions after pan", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/overview");
  const map = page.locator("[data-atlas-map]");
  const background = map.locator(":scope > div").first();
  await expect(page.locator("[data-marker-role]")).toHaveCount(7);
  for (let i = 0; i < 10; i++) await page.getByRole("button", { name: "Zoom in", exact: true }).click();
  await expect(background).toHaveCSS("transform", "matrix(1.8, 0, 0, 1.8, 0, 0)");
  for (let i = 0; i < 12; i++) await page.getByRole("button", { name: "Zoom out", exact: true }).click();
  await expect(background).toHaveCSS("transform", "matrix(0.7, 0, 0, 0.7, 0, 0)");
  // The legend floats over the map's top left. Find uncovered background so
  // the drag tests panning rather than pressing an unrelated overlay.
  const start = await map.evaluate((element) => {
    const box = element.getBoundingClientRect();
    for (const dx of [24, 100, 200]) for (const dy of [box.height - 150, box.height / 2]) {
      const target = document.elementFromPoint(box.x + dx, box.y + dy);
      if (target?.closest("[data-atlas-map]") === element && !target.closest("button")) return { x: box.x + dx, y: box.y + dy };
    }
    throw new Error("No uncovered map background available for pointer panning");
  });
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move(start.x + 80, start.y + 40, { steps: 4 });
  await page.mouse.up();
  await expect(background).toHaveCSS("transform", "matrix(0.7, 0, 0, 0.7, 80, 40)");
  await page.getByRole("button", { name: "Fit network", exact: true }).click();
  await expect(background).toHaveCSS("transform", "matrix(1, 0, 0, 1, 0, 0)");
  // Fit must bring every marker back inside the current map, including after
  // font loading or browser scrolling changes its viewport coordinates.
  await expect.poll(() => map.evaluate((element) => {
    const bounds = element.getBoundingClientRect();
    return [...element.querySelectorAll("[data-marker-role]")].every((marker) => {
      const rect = marker.getBoundingClientRect();
      return rect.left >= bounds.left && rect.right <= bounds.right && rect.top >= bounds.top && rect.bottom <= bounds.bottom;
    });
  })).toBe(true);
});

test("US-12 @story route motion respects both the explicit switch and reduced-motion preference", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/design-lab");
  const toggle = page.getByRole("checkbox", { name: "Route motion" });
  await expect(toggle).toBeChecked();
  await expect(page.locator(".lab-edge-flow")).not.toHaveCount(0);
  await toggle.uncheck();
  await expect(page.locator(".lab-edge-flow")).toHaveCount(0);
  await toggle.check();
  await expect(page.locator(".lab-edge-flow")).not.toHaveCount(0);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(toggle).toBeChecked();
  await expect(page.locator(".lab-edge-flow")).toHaveCount(0);
});
