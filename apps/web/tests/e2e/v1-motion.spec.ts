// covers: V1-A20
import { expect, test, type Page } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";
import { MOTION, inlineQuiet, moving, movingTransitions, recordMotion, started } from "./motion";
import { failedStatus, mockImport } from "./v1-import-mocks";
import { envelope, example, mockV1, publishedRun } from "./v1-mocks";

// W5-UI03 (ART-DIRECTION motion contract): motion explains a change and then stops. With motion allowed, every
// animation and transition the v1 screens start ends within 1 s and none repeats forever (except the supply-link flow,
// see FLOW below, which the map's pause control stops); under
// prefers-reduced-motion nothing moves (opacity and colour may still change). Mocked against
// packages/contracts/examples/v1: proves UI behavior, not the connected app.

const LIMIT_MS = 1_000;
// The supply-link flow is the one loop allowed: an explicit user override (docs/pantrypulse/tasks/PP-52.md decision 4),
// kept by Gabriel on 2026-11-12 with a pause control. Exempt by name only; everything else stays finite and ≤ 1 s.
const FLOW = "pp-supply-flow";
const flowRunning = (page: Page) => page.evaluate((flow) => document.getAnimations()
  .filter((a) => (a as CSSAnimation).animationName === flow && a.playState === "running").length, FLOW);
const ranking = example("DangerRanking");
const atlasNetwork = example("NetworkList").networks.find((n) => n.id === ranking.network_id)!;
const P12 = example("LocationList").locations.find((l) => l.location_id === "P-12")!;
const saved = example("SavedComparisonV3");
const decisionsNetwork = example("NetworkList").networks.find((n) => n.id === saved.network_id)!;

/** Each screen with the interactions that start its motion. */
const SCREENS: Record<string, (page: Page) => Promise<void>> = {
  "atlas ranking and site inspector": async (page) => {
    await mockV1(page, {
      "GET networks": { body: { networks: [atlasNetwork] } },
      ...publishedRun(atlasNetwork, ranking.forecast_run_id),
      [`GET networks/${atlasNetwork.id}/danger`]: { body: ranking },
      [`GET networks/${atlasNetwork.id}/locations`]: { body: example("LocationList") },
      [`GET networks/${atlasNetwork.id}/projection`]: (call) => call.query.get("location_id") === "P-12"
        ? { body: example("LocationProjection") } : { status: 404, body: envelope("NOT_FOUND") },
    });
    await page.goto("/overview");
    const section = page.getByRole("region", { name: `Danger ranking · ${atlasNetwork.name}` });
    await section.getByRole("button", { name: `${P12.name} (P-12)`, exact: true }).click();
    await expect(page.getByRole("table", { name: "WATER-24 in cases" })).toBeVisible();
    await section.getByRole("button", { name: "Table" }).click();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("region", { name: `Site inspector · ${P12.name}` })).toHaveCount(0);
  },
  "import and its column guides": async (page) => {
    await mockImport(page, failedStatus);
    await page.goto("/import");
    await page.getByText(/^Column guide \(/).first().click();
    await page.getByRole("combobox", { name: "Network", exact: true }).click();
    await expect(page.getByRole("listbox")).toBeVisible();
    await page.keyboard.press("Escape");
  },
  "demo atlas and its site card": async (page) => {
    await mockV1(page, { "GET networks": { body: { networks: [] } } });
    await page.goto("/overview");
    await expect(page.locator("[data-marker-role]")).toHaveCount(7, { timeout: 15_000 });
    await page.locator("[data-marker-role]").first().click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
  },
  decisions: async (page) => {
    const base = `networks/${decisionsNetwork.id}/comparisons/${saved.id}`;
    await mockV1(page, {
      "GET networks": { body: { networks: [decisionsNetwork] } },
      [`GET networks/${decisionsNetwork.id}`]: { body: decisionsNetwork },
      [`GET ${base}`]: { body: saved },
      [`GET ${base}/methods/CLASSICAL_GP/actions`]: { body: example("DecisionActions") },
    });
    await page.goto(`/decisions?comparison_id=${saved.id}&method=CLASSICAL_GP`);
    const section = page.getByRole("region", { name: `Suggested actions · ${decisionsNetwork.name}` });
    await section.getByRole("checkbox", { name: "Include in export" }).first().check();
  },
};

/** Lets every finite animation the interactions started run out (capped), so none is read mid-flight. */
const settle = async (page: Page) => {
  await page.evaluate((limit) => Promise.race([
    Promise.all(document.getAnimations().map((a) => a.finished.catch(() => undefined))),
    new Promise((done) => setTimeout(done, limit)),
  ]), LIMIT_MS * 2);
  await inlineQuiet(page, LIMIT_MS * 2);
};

for (const [screen, drive] of Object.entries(SCREENS)) {
  test(`@V1-A20 every animation is finite, ≤ 1s, and absent under prefers-reduced-motion: ${screen}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await recordMotion(page);
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await drive(page);
    await settle(page);
    const all = (await started(page)).filter((a) => !(a.kind === "css-animation" && a.name === FLOW));
    const tooLong = all.filter((a) => a.infinite || !(a.endMs <= LIMIT_MS)).map((a) => `${a.kind} ${a.name} on ${a.target}: ${a.endMs} ms`);
    expect(tooLong, "every animation ends within 1 s").toEqual([]);
    expect(await page.evaluate((flow) => document.getAnimations().filter((a) => a.effect?.getComputedTiming().iterations === Infinity
      && (a as CSSAnimation).animationName !== flow).length, FLOW)).toBe(0);

    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.reload(); // the recorder starts empty on each document
    await drive(page);
    await settle(page);
    expect(await moving(page), "nothing moves under reduced motion").toEqual([]);
    expect(await movingTransitions(page)).toEqual([]);
    expect(await flowRunning(page), "the supply-link flow is gone under reduced motion").toBe(0);
  });
}

// Pause, Stop, Hide (WCAG 2.2.2) for the one loop the atlas keeps (PP-52 #4; Gabriel 2026-11-12).
async function demoAtlas(page: Page) {
  await mockV1(page, { "GET networks": { body: { networks: [] } } });
  await page.goto("/overview");
  await expect(page.locator("[data-marker-role]")).toHaveCount(7, { timeout: 15_000 });
}

test("@V1-A20 the map's pause control stops the supply-link flow, and it stays stopped after a reload", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await demoAtlas(page);
  const pause = page.getByRole("group", { name: "Map controls" }).getByRole("button", { name: "Pause link animation" });
  await expect(pause).toHaveAttribute("aria-pressed", "false");
  await expect.poll(() => flowRunning(page)).toBeGreaterThan(0);
  await pause.focus();
  await page.keyboard.press("Enter");
  await expect(pause).toHaveAttribute("aria-pressed", "true");
  await expect.poll(() => flowRunning(page)).toBe(0);
  await expectNoSeriousA11yViolations(page, testInfo, "demo atlas with the link animation paused");

  await page.reload();
  await expect(page.locator("[data-marker-role]")).toHaveCount(7, { timeout: 15_000 });
  await expect(pause).toHaveAttribute("aria-pressed", "true");
  await expect.poll(() => flowRunning(page)).toBe(0);

  await pause.click();
  await expect(pause).toHaveAttribute("aria-pressed", "false");
  await expect.poll(() => flowRunning(page)).toBeGreaterThan(0);
});

test("@V1-A20 with storage unavailable the flow plays, and pausing still works for the page view", async ({ page }) => {
  await page.addInitScript(() => {
    Storage.prototype.getItem = () => { throw new Error("storage blocked"); };
    Storage.prototype.setItem = () => { throw new Error("storage blocked"); };
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await demoAtlas(page);
  const pause = page.getByRole("button", { name: "Pause link animation" });
  await expect(pause).toHaveAttribute("aria-pressed", "false");
  await expect.poll(() => flowRunning(page)).toBeGreaterThan(0);
  await pause.click();
  await expect(pause).toHaveAttribute("aria-pressed", "true");
  await expect.poll(() => flowRunning(page)).toBe(0);
});

// The check is live: the inspector's entrance (W5-UI03) is recorded with motion allowed, and kept to opacity under reduce.
test("@V1-A20 the site inspector enters with a short fade and lift, and only fades under reduced motion", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await recordMotion(page);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await SCREENS["atlas ranking and site inspector"](page);
  const entrance = (await started(page)).filter((a) => a.target.includes("Site inspector"));
  expect(entrance.length, "the inspector's entrance was recorded").toBeGreaterThan(0);
  expect(entrance.every((a) => a.endMs > 0 && a.endMs <= 250)).toBe(true);
  expect(entrance.some((a) => a.props.some((p) => MOTION.test(p))), "it lifts with motion allowed").toBe(true);

  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.reload();
  await SCREENS["atlas ranking and site inspector"](page);
  const faded = (await started(page)).filter((a) => a.target.includes("Site inspector"));
  expect(faded.length, "it still fades in under reduced motion").toBeGreaterThan(0);
  expect(faded.flatMap((a) => a.props).filter((p) => MOTION.test(p))).toEqual([]);
});
