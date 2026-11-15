// covers: V1-A20
import { mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { CONNECTED, NEEDS_BACKEND, chooseNetwork, runForecast, seedSamples, signIn } from "../connected";
import { compare, freeze } from "../connected-plan";

// W5-UI01 (v1-before) and W5-UI03 (v1-after): the connected app's v1 screens at the three review
// viewports, light and dark, into docs/pantrypulse/visual-evidence/$PP_EVIDENCE_DIR. Real API, database
// and worker: every forecast and comparison runs through the real queue. Reduced motion is emulated so
// no screenshot lands mid-animation. Run: RUN=<dir> PP_E2E_PRODUCTION=1 PP_EVIDENCE_DIR=v1-before
// run-e2e.sh --config tests/e2e/connected/evidence.config.ts (after `npm run build`; the dev server
// draws its own indicator over the page).

const DIR = process.env.PP_EVIDENCE_DIR ?? "";
const OUT = path.resolve(__dirname, "../../../../../docs/pantrypulse/visual-evidence", DIR);
const VIEWPORTS = [[1440, 900], [1280, 720], [390, 844]] as const;
const THEMES = ["light", "dark"] as const;

test.describe.configure({ timeout: 1_800_000 });

/** Each theme through the real top-bar toggle (or the same class switch where a page has none), then each viewport. */
async function capture(page: Page, name: string, ready: Locator) {
  for (const theme of THEMES) {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });
    const toggle = page.getByRole("banner").getByRole("button", { name: `Switch to ${theme} theme` });
    if (await toggle.isVisible()) await toggle.click();
    else await page.evaluate((t) => document.documentElement.classList.toggle("dark", t === "dark"), theme);
    await expect(page.locator("html")).toHaveClass(theme === "dark" ? /(^|\s)dark(\s|$)/ : /^(?!.*\bdark\b)/);
    for (const [width, height] of VIEWPORTS) {
      await page.setViewportSize({ width, height });
      await expect(ready).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(500); // layout measured by ResizeObserver settles after the resize
      await page.screenshot({ path: path.join(OUT, `${name}-${width}x${height}-${theme}.png`), fullPage: true });
    }
  }
  // Back to desktop: at 390 the sidebar (and its network switcher) is a closed drawer, and a click on it waits forever.
  await page.setViewportSize({ width: 1440, height: 900 });
}

test("@V1-A20 capture the v1 screens at three viewports, light and dark", async ({ page }) => {
  test.skip(!CONNECTED || !DIR, `${NEEDS_BACKEND}, and PP_EVIDENCE_DIR`);
  mkdirSync(OUT, { recursive: true });
  const samples = seedSamples();
  const pantry = samples.PANTRY.name, retail = samples.RETAIL.name;
  await page.emulateMedia({ reducedMotion: "reduce" });
  await signIn(page, "/overview");

  await page.goto("/import");
  await capture(page, "import", page.getByRole("button", { name: "Check and import" }));
  await page.goto("/settings");
  await capture(page, "settings", page.getByRole("heading", { level: 1 }));

  await chooseNetwork(page, retail);
  await runForecast(page, retail);
  const retailRanking = page.getByRole("region", { name: `Danger ranking · ${retail}` });
  await capture(page, "atlas-ranking-retail", retailRanking.getByRole("list", { name: "Locations by danger" }));

  await chooseNetwork(page, pantry);
  await runForecast(page, pantry);
  const ranking = page.getByRole("region", { name: `Danger ranking · ${pantry}` });
  await capture(page, "atlas-ranking-pantry", ranking.getByRole("list", { name: "Locations by danger" }));
  await ranking.getByRole("list", { name: "Locations by danger" }).getByRole("listitem").first().getByRole("button").first().click();
  await capture(page, "site-inspector-pantry", page.getByRole("region", { name: /^Site inspector · / }));

  await page.goto("/data");
  await capture(page, "forecast-trust-pantry", page.getByRole("region", { name: `Forecast trust · ${pantry}` }));

  await page.goto("/scenarios");
  const section = page.getByRole("region", { name: `Method comparison · ${pantry}` });
  const scenario = await freeze(section, "Hub → pantries only", "2 days");
  const results = await compare(section, scenario, "Hub → pantries only");
  await capture(page, "comparison-pantry", results);

  await results.getByRole("link", { name: "Open suggested actions for Classical GP" }).click();
  const decisions = page.getByRole("region", { name: `Suggested actions · ${pantry}` });
  await expect(decisions.getByRole("article").first()).toBeVisible({ timeout: 30_000 });
  await decisions.getByRole("button", { name: "Select all" }).click();
  await capture(page, "decisions-pantry", decisions);

  await decisions.getByRole("link", { name: /^Print page \(/ }).click();
  // The print page has no app shell (and no theme toggle): wait for it, not for the page being left.
  await expect(page).toHaveURL(/\/decisions\/print\?/);
  await expect(page.getByRole("table", { name: "Selected actions" })).toBeVisible({ timeout: 30_000 });
  await capture(page, "print-pantry", page.getByRole("table", { name: "Selected actions" }));
});
