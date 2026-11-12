// covers: V1-A20
import { expect, test, type Locator, type Page, type TestInfo } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";
import { moving, movingTransitions, recordMotion } from "./motion";
import { REQUIRED, csv, failedStatus, mockImport } from "./v1-import-mocks";
import { envelope, example, mockV1, publishedRun } from "./v1-mocks";

// W3-W03: the import, decisions and atlas ranking screens at three viewports. Each one is driven by the
// keyboard only (no click, fill, check or focus() call), scanned by axe with no violation of any impact,
// and run with prefers-reduced-motion: reduce, under which nothing on screen moves. Mocked against
// packages/contracts/examples/v1: proves UI behavior, not the connected app.

const VIEWPORTS = [[1440, 900], [1280, 720], [390, 844]] as const;

/** prefers-reduced-motion is on, and nothing the page started so far moved anything on screen. */
async function expectNoMotion(page: Page) {
  expect(await page.evaluate(() => matchMedia("(prefers-reduced-motion: reduce)").matches)).toBe(true);
  expect(await moving(page)).toEqual([]);
  expect(await movingTransitions(page)).toEqual([]);
}

/** axe (WCAG 2.1 A/AA): no violation of any impact, not only serious and critical ones. */
async function expectAxeClean(page: Page, testInfo: TestInfo, label: string) {
  await expectNoSeriousA11yViolations(page, testInfo, label);
  expect(testInfo.annotations.filter((a) => a.type === "a11y-advisory" && a.description?.startsWith(`${label}:`))).toEqual([]);
}

/** Press Tab (or Shift+Tab) until `target` has focus. */
async function tabTo(page: Page, target: Locator, key: "Tab" | "Shift+Tab" = "Tab") {
  for (let i = 0; i < 200; i++) {
    await page.keyboard.press(key);
    if (await target.evaluate((el) => el === document.activeElement)) return;
  }
  throw new Error(`${key} never reached ${target}`);
}

/** The first Tab reaches the skip link, and Enter moves into the main content. */
async function skipToMain(page: Page) {
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
  await page.keyboard.press("Enter");
}

/** After an action replaces the focused control, focus lands somewhere, not on the page body. */
async function expectFocusKept(page: Page) {
  await expect.poll(() => page.evaluate(() => !!document.activeElement && document.activeElement !== document.body)).toBe(true);
}

const noHorizontalScroll = (page: Page) => expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);

// Decisions: the SavedComparisonV3 example's network and its one action (DecisionActions).
const saved = example("SavedComparisonV3");
const decisionsNetwork = example("NetworkList").networks.find((n) => n.id === saved.network_id)!;
const METHOD = "CLASSICAL_GP";

// Atlas ranking: the DangerRanking example's network, locations and the P-12 projection.
const ranking = example("DangerRanking");
const atlasNetwork = example("NetworkList").networks.find((n) => n.id === ranking.network_id)!;
const P12 = example("LocationList").locations.find((l) => l.location_id === "P-12")!;

test("@V1-A20 the motion check is live: with motion allowed, it records the network switcher opening and finds layout transitions", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await recordMotion(page);
  await mockImport(page, failedStatus);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/import");
  await page.getByRole("combobox", { name: "Network", exact: true }).click();
  await expect(page.getByRole("listbox")).toBeVisible();
  await expect.poll(() => moving(page)).not.toEqual([]);
  // The computed-transition check is live too: with motion allowed, layout transitions are there to find.
  expect(await movingTransitions(page)).not.toEqual([]);
});

for (const [width, height] of VIEWPORTS) {
  test.describe(`${width}x${height}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.setViewportSize({ width, height });
      await recordMotion(page);
    });

    test(`@V1-A20 import: keyboard only, axe clean, no motion at ${width}x${height}`, async ({ page }, testInfo) => {
      await mockImport(page, failedStatus);
      await page.goto("/import");
      await expect(page.getByRole("heading", { level: 1, name: "Import your network" })).toBeVisible();
      await expectAxeClean(page, testInfo, `import ${width}`);

      await skipToMain(page);
      await tabTo(page, page.getByLabel("Network name"));
      await page.keyboard.type("Keyboard Network");
      const pantry = page.getByRole("radio", { name: /^Pantry network/ });
      await tabTo(page, pantry);
      await page.keyboard.press("Space");
      await expect(pantry).toBeChecked();
      // As in import-upload.spec.ts A20: one listener keeps chooser interception on for the whole loop (Playwright
      // otherwise turns it off and back on, without waiting, around each waitForEvent), and each file lands first.
      const keepIntercepting = () => {};
      page.on("filechooser", keepIntercepting);
      for (const file of REQUIRED) {
        await tabTo(page, page.getByLabel(`${file}.csv (required)`));
        const chooser = page.waitForEvent("filechooser");
        await page.keyboard.press("Space");
        await (await chooser).setFiles(csv(file));
        await expect(page.getByText(new RegExp(`^${file}\\.csv · \\d+ bytes$`))).toBeVisible();
      }
      page.off("filechooser", keepIntercepting);
      await tabTo(page, page.getByRole("button", { name: "Check and import" }));
      await page.keyboard.press("Enter");
      const again = page.getByRole("button", { name: "Start a new import" });
      await expect(again).toBeVisible();
      await expectFocusKept(page);
      await expectAxeClean(page, testInfo, `import failed ${width}`);

      await tabTo(page, again);
      await page.keyboard.press("Enter");
      await expect(page.getByLabel("locations.csv (required)")).toHaveValue("");
      await expectFocusKept(page);
      await expectNoMotion(page);
      await noHorizontalScroll(page);
    });

    test(`@V1-A20 shell on these screens: network switcher${width < 768 ? " and navigation drawer" : ""} by keyboard, no motion at ${width}x${height}`, async ({ page }, testInfo) => {
      await mockImport(page, failedStatus);
      await page.goto("/import");
      await expect(page.getByRole("heading", { level: 1, name: "Import your network" })).toBeVisible();
      if (width < 768) {
        await tabTo(page, page.getByRole("button", { name: "Open navigation" }));
        await page.keyboard.press("Enter");
      }
      const switcher = page.getByRole("combobox", { name: "Network", exact: true });
      await tabTo(page, switcher);
      await page.keyboard.press("Enter");
      const listbox = page.getByRole("listbox");
      await expect(listbox).toBeVisible();
      await expectAxeClean(page, testInfo, `network switcher ${width}`);
      await page.keyboard.press("Escape");
      await expect(listbox).toHaveCount(0);
      await expect(switcher).toBeFocused();
      await expectNoMotion(page);
    });

    test(`@V1-A20 decisions: keyboard only, axe clean, no motion at ${width}x${height}`, async ({ page }, testInfo) => {
      const base = `networks/${decisionsNetwork.id}/comparisons/${saved.id}`;
      const actions = example("DecisionActions");
      await mockV1(page, {
        "GET networks": { body: { networks: [decisionsNetwork] } },
        [`GET networks/${decisionsNetwork.id}`]: { body: decisionsNetwork },
        [`GET ${base}`]: { body: saved },
        [`GET ${base}/methods/${METHOD}/actions`]: { body: actions },
        [`POST ${base}/methods/${METHOD}/export`]: { body: "scenario_hash,note\nh,simulated plan; no stock was reserved or moved\n", contentType: "text/csv" },
      });
      await page.emulateMedia({ reducedMotion: "reduce" });
      await page.goto(`/decisions?comparison_id=${saved.id}&method=${METHOD}`);
      const section = page.getByRole("region", { name: `Suggested actions · ${decisionsNetwork.name}` });
      await expect(section.getByRole("article")).toHaveCount(actions.actions.length);
      await expectAxeClean(page, testInfo, `decisions ${width}`);

      await skipToMain(page);
      const include = section.getByRole("checkbox", { name: "Include in export" }).first();
      await tabTo(page, include);
      await page.keyboard.press("Space");
      await expect(include).toBeChecked();
      const exportButton = section.getByRole("button", { name: "Export CSV (1 action)" });
      await tabTo(page, exportButton);
      const [download] = await Promise.all([page.waitForEvent("download"), page.keyboard.press("Enter")]);
      expect(download.suggestedFilename()).toMatch(/\.csv$/);
      await expect(exportButton).toBeFocused();
      await expectAxeClean(page, testInfo, `decisions selected ${width}`);
      await expectNoMotion(page);
      await noHorizontalScroll(page);
    });

    test(`@V1-A20 atlas ranking: keyboard only, axe clean, no motion at ${width}x${height}`, async ({ page }, testInfo) => {
      await mockV1(page, {
        "GET networks": { body: { networks: [atlasNetwork] } },
        ...publishedRun(atlasNetwork, ranking.forecast_run_id),
        [`GET networks/${atlasNetwork.id}/danger`]: { body: ranking },
        [`GET networks/${atlasNetwork.id}/locations`]: { body: example("LocationList") },
        [`GET networks/${atlasNetwork.id}/projection`]: (call) => call.query.get("location_id") === "P-12"
          ? { body: example("LocationProjection") } : { status: 404, body: envelope("NOT_FOUND") },
      });
      await page.emulateMedia({ reducedMotion: "reduce" });
      await page.goto("/overview");
      const section = page.getByRole("region", { name: `Danger ranking · ${atlasNetwork.name}` });
      await expect(section.getByRole("list", { name: "Locations by danger" })).toBeVisible();
      await expectAxeClean(page, testInfo, `atlas ranking ${width}`);

      await skipToMain(page);
      const row = section.getByRole("button", { name: `${P12.name} (P-12)`, exact: true });
      await tabTo(page, row);
      await page.keyboard.press("Enter");
      const inspector = page.getByRole("region", { name: `Site inspector · ${P12.name}` });
      await expect(inspector.getByRole("heading", { name: P12.name })).toBeFocused();
      await expect(inspector.getByRole("table", { name: "WATER-24 in cases" })).toBeVisible();
      await expectAxeClean(page, testInfo, `atlas inspector ${width}`);
      await tabTo(page, inspector.getByRole("button", { name: "Close inspector" }));
      await page.keyboard.press("Enter");
      await expect(inspector).toHaveCount(0);
      await expect(row).toBeFocused();

      const table = section.getByRole("button", { name: "Table" });
      await tabTo(page, table, "Shift+Tab");
      await page.keyboard.press("Enter");
      await expect(table).toHaveAttribute("aria-pressed", "true");
      await expect(section.getByRole("table", { name: /Danger ranking/ })).toBeVisible();
      await expectAxeClean(page, testInfo, `atlas ranking table ${width}`);
      await expectNoMotion(page);
      await noHorizontalScroll(page);
    });
  });
}
