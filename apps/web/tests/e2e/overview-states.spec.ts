// covers: V1-A20
import { expect, test } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";
import { envelope, mockV1 } from "./v1-mocks";

// Mocked: proves the Overview's two states without a network, not the connected app.
for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
  const at = `${viewport.width}x${viewport.height}`;
  test.describe(at, () => {
    test.use({ viewport });
    test.beforeEach(({ page }) => page.emulateMedia({ reducedMotion: "reduce" }));

    test(`@V1-A20 signed out, the Overview asks for a sign-in and renders no map, ranking or fixture (${at})`, async ({ page }, testInfo) => {
      await mockV1(page, {}, { presenter: false });
      await page.goto("/overview");
      const main = page.getByRole("main");
      await expect(main.getByRole("heading", { level: 1, name: "Sign in to see your networks" })).toBeVisible();
      await expect(main.getByText("Networks, forecasts and plans are open to the presenter session only.")).toBeVisible();
      await expect(main.getByRole("heading")).toHaveCount(1);
      for (const role of ["img", "application", "list", "table"] as const) await expect(main.getByRole(role)).toHaveCount(0);
      await expect(main.locator("svg")).toHaveCount(0);
      await expect(page.getByText(/static fixture|simulated/i)).toHaveCount(0);
      await expectNoSeriousA11yViolations(page, testInfo, `overview signed out ${at}`);
      await main.getByRole("button", { name: "Presenter sign in" }).click();
      const dialog = page.getByRole("dialog", { name: "Presenter sign in" });
      await expect(dialog.getByLabel("Username", { exact: true })).toBeVisible();
      await expect(dialog.getByLabel("Password", { exact: true })).toBeVisible();
    });

    test(`@V1-A20 signed in with no network, the Overview offers the network picker and Import data (${at})`, async ({ page }, testInfo) => {
      await mockV1(page, { "GET networks": { body: { networks: [] } } });
      await page.goto("/overview");
      const main = page.getByRole("main");
      await expect(main.getByRole("heading", { level: 1, name: "Choose or import a network" })).toBeVisible();
      // W5A-03c: one picker per page. At 768 px and up it is the context bar's; below that the page shows its own.
      const pickers = page.getByRole("region", { name: "Current network" });
      await expect(pickers).toHaveCount(1);
      await expect(page.locator("#network-switcher-label")).toHaveCount(1);
      if (viewport.width >= 768) {
        await expect(page.getByRole("banner").getByRole("region", { name: "Current network" })).toBeVisible();
        await expect(main).toContainText("the bar above");
      } else {
        await expect(main.getByRole("region", { name: "Current network" })).toBeVisible();
      }
      await expect(main.getByRole("link", { name: "Import data", exact: true })).toHaveAttribute("href", "/import");
      await expect(main.getByRole("button", { name: "Presenter sign in" })).toHaveCount(0);
      await expect(page.getByText(/static fixture/i)).toHaveCount(0);
      await expectNoSeriousA11yViolations(page, testInfo, `overview no network ${at}`);
    });

    test(`@V1-A20 a network list that fails gets its own state with one alert, and Try again lists again (${at})`, async ({ page }, testInfo) => {
      let fail = true;
      const calls = await mockV1(page, { "GET networks": () => fail ? { status: 500, body: envelope("INTERNAL_ERROR") } : { body: { networks: [] } } });
      const listed = () => calls.filter((c) => c.method === "GET" && c.path === "networks").length;
      await page.goto("/overview");
      const main = page.getByRole("main");
      await expect(main.getByRole("heading", { level: 1, name: "Networks could not be loaded" })).toBeVisible();
      // Next's route announcer is an alert too, so alerts are counted by their text.
      const alerts = page.getByRole("alert").filter({ hasText: /network/i });
      await expect(alerts).toHaveCount(1);
      await expect(alerts).toContainText("internal error");
      await expectNoSeriousA11yViolations(page, testInfo, `overview network error ${at}`);
      const before = listed();
      fail = false;
      await main.getByRole("button", { name: "Try again" }).click();
      await expect.poll(listed).toBeGreaterThan(before);
      await expect(main.getByRole("heading", { level: 1, name: "Choose or import a network" })).toBeVisible();
    });
  });
}
