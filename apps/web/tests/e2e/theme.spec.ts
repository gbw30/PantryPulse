import { expect, test, type Page } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";

// PP-52 decision 5: a dark/light toggle in the shared top bar, persisted per browser through
// lib/theme.ts, applied before the first paint by the root layout's boot script.

const DARK = /(^|\s)dark(\s|$)/;

async function asVisitor(page: Page) {
  await page.route("**/api/v1/**", (route) => route.fulfill({
    status: 401,
    json: { error: { code: "PRESENTER_REQUIRED", message: "presenter required", details: {} }, request_id: "00000000-0000-4000-8000-000000000000" },
  }));
}

// Runs before every document's own scripts, on every navigation of this page.
async function storeDark(page: Page) {
  await page.addInitScript(() => {
    try {
      window.localStorage.setItem("pp-theme", "dark");
    } catch {
      // Storage blocked: the test then fails on the class assertion, which is the point.
    }
  });
}

async function openOverview(page: Page, width: number, height: number) {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await asVisitor(page);
  await page.setViewportSize({ width, height });
  await page.emulateMedia({ reducedMotion: "reduce", colorScheme: "light" });
  await page.goto("/overview");
  await expect(page.getByRole("heading", { level: 1, name: "Network Atlas" })).toBeVisible();
  await expect(page.locator("[data-marker-role]")).toHaveCount(7, { timeout: 15_000 });
  return pageErrors;
}

test("the top-bar toggle switches .dark on <html>, persists across reload and flips its name", async ({ page }) => {
  const pageErrors = await openOverview(page, 1440, 900);
  const html = page.locator("html");
  const banner = page.getByRole("banner");
  await expect(html).not.toHaveClass(DARK);

  await banner.getByRole("button", { name: "Switch to dark theme" }).click();
  await expect(html).toHaveClass(DARK);
  await expect(banner.getByRole("button", { name: "Switch to light theme" })).toBeVisible();
  expect(await page.evaluate(() => window.localStorage.getItem("pp-theme"))).toBe("dark");
  // Tokens switch with the class: the canvas is the dark palette's.
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(7, 23, 33)");

  await page.reload();
  await expect(page.locator("[data-marker-role]")).toHaveCount(7, { timeout: 15_000 });
  await expect(html).toHaveClass(DARK);
  const toLight = banner.getByRole("button", { name: "Switch to light theme" });
  await expect(toLight).toBeVisible();

  await toLight.click();
  await expect(html).not.toHaveClass(DARK);
  await expect(banner.getByRole("button", { name: "Switch to dark theme" })).toBeVisible();
  await page.reload();
  await expect(html).not.toHaveClass(DARK);
  await expect(banner.getByRole("button", { name: "Switch to dark theme" })).toBeVisible();
  expect(pageErrors).toEqual([]);
});

test("no flash: with dark stored, <html> is dark before the first paint and stays dark after hydration", async ({ page }) => {
  await storeDark(page);
  await page.addInitScript(() => {
    const probe = window as unknown as { __ppBodyDark?: boolean; __ppFirstFrameDark?: boolean };
    const isDark = () => document.documentElement?.classList.contains("dark") ?? false;
    // The moment <body> is inserted (nothing of the page can have painted yet).
    new MutationObserver((_, observer) => {
      if (!document.body) return;
      probe.__ppBodyDark = isDark();
      observer.disconnect();
    }).observe(document, { childList: true, subtree: true });
    // The first rendering frame that has a body.
    const frame = () => {
      if (!document.body) {
        requestAnimationFrame(frame);
        return;
      }
      probe.__ppFirstFrameDark = isDark();
    };
    requestAnimationFrame(frame);
  });
  await openOverview(page, 1440, 900);
  for (let round = 0; round < 2; round += 1) {
    const probe = await page.evaluate(() => {
      const value = window as unknown as { __ppBodyDark?: boolean; __ppFirstFrameDark?: boolean };
      return { body: value.__ppBodyDark, frame: value.__ppFirstFrameDark };
    });
    expect(probe, `load ${round + 1}`).toEqual({ body: true, frame: true });
    await expect(page.locator("html")).toHaveClass(DARK);
    await expect(page.getByRole("banner").getByRole("button", { name: "Switch to light theme" })).toBeVisible();
    await page.reload();
    await expect(page.locator("[data-marker-role]")).toHaveCount(7, { timeout: 15_000 });
  }
});

for (const [width, height] of [[1440, 900], [390, 844]]) {
  test(`overview in dark at ${width}x${height}: no serious a11y violations on the map, card and inspector`, async ({ page }, testInfo) => {
    await storeDark(page);
    const pageErrors = await openOverview(page, width, height);
    await expect(page.locator("html")).toHaveClass(DARK);
    await page.screenshot({ path: testInfo.outputPath(`overview-dark-${width}.png`), fullPage: true });
    await expectNoSeriousA11yViolations(page, testInfo, `overview dark ${width}x${height} default`);

    const riverbend = page.getByRole("button", { name: /^Riverbend Pantry, / });
    await riverbend.focus();
    await page.keyboard.press("Enter");
    const card = page.getByRole("dialog", { name: "Riverbend Pantry" });
    await expect(card).toBeVisible();
    await expectNoSeriousA11yViolations(page, testInfo, `overview dark ${width}x${height} card`);
    await card.getByRole("button", { name: "Inspect site" }).click();
    const inspector = page.getByTestId("site-inspector");
    await expect(inspector.getByRole("heading", { name: "Riverbend Pantry" })).toBeVisible();
    await inspector.getByRole("tab", { name: "Demand" }).click();
    await inspector.getByRole("button", { name: "Show data table" }).click();
    await expect(inspector.getByRole("table")).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`overview-dark-${width}-inspector-demand.png`), fullPage: true });
    await expectNoSeriousA11yViolations(page, testInfo, `overview dark ${width}x${height} inspector demand`);
    expect(pageErrors).toEqual([]);
  });
}

test("the toggle works on /optimization, and the workspace has no serious a11y violations in dark at 1440", async ({ page }, testInfo) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.emulateMedia({ reducedMotion: "reduce", colorScheme: "light" });
  await page.goto("/optimization");
  await expect(page.getByRole("heading", { level: 1, name: "Optimization workspace" })).toBeVisible();
  const html = page.locator("html");
  await expect(html).not.toHaveClass(DARK);
  await page.getByRole("banner").getByRole("button", { name: "Switch to dark theme" }).click();
  await expect(html).toHaveClass(DARK);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "Optimization workspace" })).toBeVisible();
  await expect(html).toHaveClass(DARK);
  await expect(page.getByRole("heading", { name: "Presenter sign in" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("optimization-dark-1440.png"), fullPage: true });
  await expectNoSeriousA11yViolations(page, testInfo, "optimization dark 1440x900");
  expect(pageErrors).toEqual([]);
});
