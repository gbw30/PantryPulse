// covers: V1-A12, V1-A14, V1-A16, V1-A20
import { expect, test, type Page } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";
import { CONNECTED, NEEDS_BACKEND, chooseNetwork, runForecast, signIn } from "./connected";
import { compare, freeze } from "./connected-plan";

// W5-SC02: the w5-screens evidence, connected only, on the fictional Pantry sample a first start seeds.
// Full-page screenshots go to each test's output folder; the lane copies them to
// docs/pantrypulse/visual-evidence/w5-screens/. Reduced motion, so every capture is a settled frame.
const PANTRY = "Sample Pantry Network (North Central Florida)";
const VIEWPORTS = [[1440, 900], [1280, 720], [390, 844]] as const;

test.beforeEach(() => test.skip(!CONNECTED, NEEDS_BACKEND));
test.describe.configure({ mode: "serial", timeout: 900_000 });

async function shoot(page: Page, name: string) {
  for (const [width, height] of VIEWPORTS) {
    await page.setViewportSize({ width, height });
    await page.evaluate(() => window.scrollTo(0, 0));
    // The first view is what a reader sees; the full page paints the fixed sidebar and sticky top bar mid-page.
    await page.screenshot({ path: test.info().outputPath(`${name}-${width}x${height}-view.png`), animations: "disabled" });
    await page.screenshot({ path: test.info().outputPath(`${name}-${width}x${height}-full.png`), fullPage: true, animations: "disabled" });
  }
  await page.setViewportSize({ width: 1440, height: 900 });
}

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page, "/overview");
  await chooseNetwork(page, PANTRY);
});

test("@V1-A12 @V1-A20 evidence: /data shows only the Pantry sample", async ({ page }, testInfo) => {
  await runForecast(page, PANTRY);
  await page.goto("/data");
  const trust = page.getByRole("region", { name: `Forecast trust · ${PANTRY}` });
  await expect(trust.getByRole("table", { name: "Accuracy by location and unit" })).toBeVisible({ timeout: 60_000 });
  const text = await page.locator("body").innerText();
  for (const word of ["Riverbend", "Gator", "bottles"]) expect(text, `legacy content "${word}"`).not.toContain(word);
  await shoot(page, "data");
  await expectNoSeriousA11yViolations(page, testInfo, "w5-screens /data");
});

test("@V1-A14 @V1-A20 evidence: the Scenario Lab comparison, rows collapsed and open", async ({ page }, testInfo) => {
  await page.goto("/scenarios");
  const section = page.getByRole("region", { name: `Method comparison · ${PANTRY}` });
  const transfer = "Hub → pantries only";
  const results = await compare(section, await freeze(section, transfer, "3 days"), transfer);
  await shoot(page, "comparison");
  await results.getByRole("region", { name: "Classical GP", exact: true }).getByText("Show rows").click();
  await shoot(page, "comparison-rows-open");
  await expectNoSeriousA11yViolations(page, testInfo, "w5-screens comparison");
});
