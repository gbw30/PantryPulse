import { expect, test } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";

// Methodology & audit (blueprint §7): static research attribution for everyone, live solver settings
// from GET /allocation-methodology for presenters. API mocked.

const BASE = `http://127.0.0.1:${process.env.PLAYWRIGHT_PORT ?? "3000"}`;
const envelope = (code: string) => ({ error: { code, message: code.toLowerCase(), details: {} }, request_id: "00000000-0000-4000-8000-000000000000" });
const METHODOLOGY = {
  methods: ["CLASSICAL_GP", "EGP_PI_INSPIRED"], transfer_modes: ["HUB_ONLY", "HUB_AND_PANTRY"], default_transfer_mode: null,
  decision_ids: ["BD-01"], expiry: "usable through stated local expiry date", search_seconds: { default: 120, maximum: 300 },
  donor_protection_days: 7, planning_window_days: [1, 2, 3], stock_effect: "NONE_SIMULATION_ONLY",
  limitations: ["Fixed route loading order restricts the feasible region"],
};

for (const [width, height] of [[1440, 900], [1280, 720], [390, 844]]) {
  test(`methodology for a visitor at ${width}x${height}`, async ({ page }, testInfo) => {
    await page.route("**/api/v1/**", (route) => route.fulfill({ status: 401, json: envelope("PRESENTER_REQUIRED") }));
    await page.setViewportSize({ width, height });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/methodology");
    await expect(page.getByRole("heading", { level: 1, name: "Methodology" })).toBeVisible();
    await expect(page.getByRole("link", { name: /DOI 10\.1111\/itor\.70252/ })).toHaveAttribute("href", "https://doi.org/10.1111/itor.70252");
    await expect(page.getByText("First published online 11 September 2026", { exact: false })).toBeVisible();
    await expect(page.getByText("not a reproduction", { exact: false })).toBeVisible();
    await expect(page.getByText("after presenter sign-in", { exact: false })).toBeVisible();
    for (const banned of ["exact reproduction", "reduces poverty", "fairer distribution", "probability of stockout"]) {
      await expect(page.getByText(banned, { exact: false })).toHaveCount(0);
    }
    await page.screenshot({ path: testInfo.outputPath(`methodology-${width}.png`), fullPage: true });
    await expectNoSeriousA11yViolations(page, testInfo, `methodology ${width}x${height}`);
  });
}

test("methodology shows live solver settings for a presenter", async ({ page }) => {
  await page.context().addCookies([{ name: "pp_csrf", value: "token", url: BASE }]);
  await page.route("**/api/v1/**", (route) => new URL(route.request().url()).pathname === "/api/v1/allocation-methodology"
    ? route.fulfill({ status: 200, json: METHODOLOGY })
    : route.fulfill({ status: 401, json: envelope("PRESENTER_REQUIRED") }));
  await page.goto("/methodology");
  await expect(page.getByText("no default; the presenter must choose")).toBeVisible();
  await expect(page.getByText("120 s default, 300 s maximum")).toBeVisible();
  await expect(page.getByText("None — simulation only", { exact: false })).toBeVisible();
  await expect(page.getByText("Fixed route loading order restricts the feasible region")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Reference" }).getByRole("link", { name: "Methodology & audit" })).toHaveAttribute("aria-current", "page");
});
