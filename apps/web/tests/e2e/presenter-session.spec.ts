import { expect, test, type Page } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";

// Shared presenter sign-in in the sidebar footer (PP-56 foundation). The API is mocked; FastAPI owns
// authentication, so the shell only probes one presenter-only read when a pp_csrf cookie exists.

const BASE = `http://127.0.0.1:${process.env.PLAYWRIGHT_PORT ?? "3000"}`;
const envelope = (code: string) => ({ error: { code, message: code.toLowerCase(), details: {} }, request_id: "00000000-0000-4000-8000-000000000000" });

async function mockVisitorApi(page: Page) {
  const probes: string[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/allocation-methodology") probes.push(path);
    await route.fulfill({ status: 401, json: envelope("PRESENTER_REQUIRED") });
  });
  return probes;
}

// On mobile the footer lives in the off-canvas navigation drawer.
async function openFooter(page: Page) {
  const footer = page.getByRole("button", { name: /^(Presenter sign in|Sign out)$/ });
  if (!(await footer.isVisible())) await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(footer).toBeVisible();
}

for (const [width, height] of [[1440, 900], [390, 844]]) {
  test(`visitor signs in from the sidebar at ${width}x${height}`, async ({ page }, testInfo) => {
    const probes = await mockVisitorApi(page);
    let logins = 0;
    await page.route("**/api/v1/presenter/login", async (route) => {
      logins += 1;
      const body = route.request().postDataJSON() as { username: string; password: string };
      if (body.password !== "right") return route.fulfill({ status: 401, json: envelope("INVALID_CREDENTIALS") });
      await page.context().addCookies([{ name: "pp_csrf", value: "token", url: BASE }]);
      await route.fulfill({ status: 200, json: { actor_id: "11111111-1111-4111-8111-111111111111", csrf_token: "token", expires_in_seconds: 3600, organization_id: "22222222-2222-4222-8222-222222222222" } });
    });
    await page.setViewportSize({ width, height });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/overview");
    await openFooter(page);

    // No cookie: visitor without any probe; no invented identity.
    await expect(page.getByText("No account · read-only demo")).toBeVisible();
    expect(probes).toEqual([]);
    const trigger = page.getByRole("button", { name: "Presenter sign in" });
    await trigger.click();
    const dialog = page.getByRole("dialog", { name: "Presenter sign in" });
    await expect(dialog).toBeVisible();
    await expectNoSeriousA11yViolations(page, testInfo, `sign-in dialog ${width}x${height}`);

    await dialog.getByLabel("Username").fill("presenter");
    await dialog.getByLabel("Password").fill("wrong");
    await dialog.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(dialog.getByRole("alert")).toHaveText("Username or password not recognized.");
    expect(logins).toBe(1);

    // Escape closes and returns focus to the trigger.
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    if (width >= 768) await expect(trigger).toBeFocused();

    // Success reloads the page; the probe now answers 200 and the footer shows the session.
    await page.unroute("**/api/v1/**");
    // Later routes win in Playwright, so hand login back to its earlier handler.
    await page.route("**/api/v1/**", (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/api/v1/presenter/login") return route.fallback();
      return path === "/api/v1/allocation-methodology"
        ? route.fulfill({ status: 200, json: { methods: [], transfer_modes: [], default_transfer_mode: null } })
        : route.fulfill({ status: 401, json: envelope("PRESENTER_REQUIRED") });
    });
    await openFooter(page);
    await page.getByRole("button", { name: "Presenter sign in" }).click();
    const again = page.getByRole("dialog", { name: "Presenter sign in" });
    await again.getByLabel("Username").fill("presenter");
    await again.getByLabel("Password").fill("right");
    await Promise.all([page.waitForEvent("load"), again.getByRole("button", { name: "Sign in", exact: true }).click()]);
    await openFooter(page);
    await expect(page.getByText("Presenter session · simulated demo")).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
    await expect(page.getByText("No account · read-only demo")).toHaveCount(0);
    // Identity never appears in the top bar.
    await expect(page.getByRole("banner").getByText("Presenter session", { exact: false })).toHaveCount(0);
  });
}

test("a stale pp_csrf cookie without a session falls back to visitor", async ({ page }) => {
  await page.context().addCookies([{ name: "pp_csrf", value: "stale", url: BASE }]);
  const probes = await mockVisitorApi(page);
  await page.goto("/overview");
  await expect(page.getByRole("button", { name: "Presenter sign in" })).toBeEnabled();
  expect(probes.length).toBeGreaterThan(0);
});
