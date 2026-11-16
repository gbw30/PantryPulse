import { expect, test, type Page } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";
import { envelope, example, mockV1, publishedRun } from "./v1-mocks";

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
  await expect(page.getByRole("heading", { level: 1, name: "Sign in to see your networks" })).toBeVisible();
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
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(16, 23, 31)");

  await page.reload();
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
  }
});

const ranking = example("DangerRanking");
const network = example("NetworkList").networks.find((n) => n.id === ranking.network_id)!;
const P12 = example("LocationList").locations.find((l) => l.location_id === "P-12")!;

for (const [width, height] of [[1440, 900], [390, 844]]) {
  test(`overview in dark at ${width}x${height}: no serious a11y violations on the ranking and inspector`, async ({ page }, testInfo) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await storeDark(page);
    await mockV1(page, {
      "GET networks": { body: { networks: [network] } },
      ...publishedRun(network, ranking.forecast_run_id),
      [`GET networks/${network.id}/danger`]: { body: ranking },
      [`GET networks/${network.id}/locations`]: { body: example("LocationList") },
      [`GET networks/${network.id}/projection`]: (call) => call.query.get("location_id") === "P-12"
        ? { body: example("LocationProjection") } : { status: 404, body: envelope("NOT_FOUND") },
    });
    await page.setViewportSize({ width, height });
    await page.emulateMedia({ reducedMotion: "reduce", colorScheme: "light" });
    await page.goto("/overview");
    await expect(page.locator("html")).toHaveClass(DARK);
    const section = page.getByRole("region", { name: `Danger ranking · ${network.name}` });
    const row = section.getByRole("button", { name: `${P12.name} (P-12)`, exact: true });
    await expect(row).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`overview-dark-${width}.png`), fullPage: true });
    await expectNoSeriousA11yViolations(page, testInfo, `overview dark ${width}x${height} ranking`);

    await row.focus();
    await page.keyboard.press("Enter");
    const inspector = page.getByRole("region", { name: `Site inspector · ${P12.name}` });
    await expect(inspector.getByRole("table", { name: "WATER-24 in cases" })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`overview-dark-${width}-inspector.png`), fullPage: true });
    await expectNoSeriousA11yViolations(page, testInfo, `overview dark ${width}x${height} inspector`);
    expect(pageErrors).toEqual([]);
  });
}

// /optimization now redirects to the Scenario Lab (PP-55 decision 1), so the toggle is exercised there.
test("the toggle works on /scenarios (via the /optimization redirect), with no serious a11y violations in dark at 1440", async ({ page }, testInfo) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.emulateMedia({ reducedMotion: "reduce", colorScheme: "light" });
  await page.goto("/optimization");
  await expect(page).toHaveURL(/\/scenarios$/);
  await expect(page.getByRole("heading", { level: 1, name: "Scenario Lab" })).toBeVisible();
  const html = page.locator("html");
  await expect(html).not.toHaveClass(DARK);
  await page.getByRole("banner").getByRole("button", { name: "Switch to dark theme" }).click();
  await expect(html).toHaveClass(DARK);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "Scenario Lab" })).toBeVisible();
  await expect(html).toHaveClass(DARK);
  await page.screenshot({ path: testInfo.outputPath("scenario-lab-dark-1440.png"), fullPage: true });
  await expectNoSeriousA11yViolations(page, testInfo, "scenario lab dark 1440x900");
  expect(pageErrors).toEqual([]);
});
