import { expect, test, type Locator, type Page } from "@playwright/test";

// PP-52: draggable map nodes and panels, keyboard move mode, flowing supply links.
// Every test starts in a fresh browser context, so localStorage (and the saved layout) starts empty;
// each test asserts that before it relies on the default layout.

const LAYOUT_KEY = "pp-atlas-layout";

type Box = { x: number; y: number; width: number; height: number };
type Point = { x: number; y: number };

function overlaps(a: Box, b: Box, gap = 0) {
  return a.x < b.x + b.width + gap && b.x < a.x + a.width + gap && a.y < b.y + b.height + gap && b.y < a.y + a.height + gap;
}

function inside(inner: Box, outer: Box, tolerance = 1) {
  return inner.x >= outer.x - tolerance && inner.y >= outer.y - tolerance
    && inner.x + inner.width <= outer.x + outer.width + tolerance && inner.y + inner.height <= outer.y + outer.height + tolerance;
}

function insetBox(rect: Box, inset: number): Box {
  return { x: rect.x + inset, y: rect.y + inset, width: rect.width - inset * 2, height: rect.height - inset * 2 };
}

async function box(locator: Locator) {
  const result = await locator.boundingBox();
  expect(result).not.toBeNull();
  return result!;
}

const centre = (rect: Box): Point => ({ x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 });

function expectNear(actual: Point, expected: Point, label: string, tolerance = 2) {
  expect(Math.abs(actual.x - expected.x), `${label}: x ${actual.x} vs ${expected.x}`).toBeLessThanOrEqual(tolerance);
  expect(Math.abs(actual.y - expected.y), `${label}: y ${actual.y} vs ${expected.y}`).toBeLessThanOrEqual(tolerance);
}

const marker = (page: Page, name: string) => page.getByRole("button", { name: new RegExp(`^${name}, `) });
const glyph = (page: Page, siteId: string) => page.locator(`[data-site-id="${siteId}"] [data-glyph]`);

async function glyphCentre(page: Page, siteId: string) {
  return centre(await box(glyph(page, siteId)));
}

// A supply link's start or end point in page coordinates (paths are drawn in map pixels).
async function linkPoint(page: Page, siteId: string, end: "start" | "end") {
  const d = (await page.locator(`[data-supply-link="${siteId}"]`).getAttribute("d")) ?? "";
  const numbers = d.match(/-?\d+(?:\.\d+)?/g)?.map(Number) ?? [];
  const map = await page.locator("[data-atlas-map]").evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return { x: rect.left + element.clientLeft, y: rect.top + element.clientTop };
  });
  const [x, y] = end === "start" ? numbers.slice(0, 2) : numbers.slice(-2);
  return { x: map.x + x, y: map.y + y };
}

async function savedLayout(page: Page) {
  return page.evaluate((key) => {
    const raw = window.localStorage.getItem(key);
    return raw === null ? null : JSON.parse(raw);
  }, LAYOUT_KEY);
}

async function asVisitor(page: Page) {
  await page.route("**/api/v1/**", (route) => route.fulfill({
    status: 401,
    json: { error: { code: "PRESENTER_REQUIRED", message: "presenter required", details: {} }, request_id: "00000000-0000-4000-8000-000000000000" },
  }));
}

async function openAtlas(page: Page, width: number, height: number, reducedMotion: "reduce" | "no-preference" = "reduce") {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await asVisitor(page);
  await page.setViewportSize({ width, height });
  await page.emulateMedia({ reducedMotion });
  await page.goto("/overview");
  await expect(page.locator("[data-marker-role]")).toHaveCount(7, { timeout: 15_000 });
  expect(await savedLayout(page), "layout storage starts empty").toBeNull();
  return pageErrors;
}

async function reloadAtlas(page: Page) {
  await page.reload();
  await expect(page.locator("[data-marker-role]")).toHaveCount(7, { timeout: 15_000 });
}

// Pointer drag from a point to a point in several moves (pointer events, as a mouse or pen produces).
async function dragFromTo(page: Page, from: Point, to: Point, steps = 10) {
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  for (let step = 1; step <= steps; step += 1) {
    await page.mouse.move(from.x + ((to.x - from.x) * step) / steps, from.y + ((to.y - from.y) * step) / steps);
  }
  await page.mouse.up();
}

async function dragBy(page: Page, handle: Locator, dx: number, dy: number) {
  const from = centre(await box(handle));
  await dragFromTo(page, from, { x: from.x + dx, y: from.y + dy });
}

test("drag a pantry and the hub: markers and supply links follow, persist across reload, and Reset layout restores them", async ({ page }, testInfo) => {
  const pageErrors = await openAtlas(page, 1440, 900);
  const riverbend = marker(page, "Riverbend Pantry");
  const oak = marker(page, "Oak Terrace Pantry");
  const reset = page.getByRole("button", { name: "Reset layout" });
  await expect(reset).toBeVisible();

  const start = await glyphCentre(page, "riverbend");
  expectNear(await linkPoint(page, "riverbend", "end"), start, "default link end at the marker");
  const oakStart = await box(oak);

  await dragFromTo(page, start, { x: start.x + 90, y: start.y + 70 });
  const moved = await glyphCentre(page, "riverbend");
  expectNear(moved, { x: start.x + 90, y: start.y + 70 }, "dragged marker");
  expectNear(await linkPoint(page, "riverbend", "end"), moved, "link end follows the marker");

  // Dragging a node neither selects it nor pans the map.
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(riverbend).toHaveAttribute("aria-pressed", "false");
  expectNear(centre(await box(oak)), centre(oakStart), "other markers stay put");

  // Saved per browser, schema-versioned, keyed by site id.
  const saved = await savedLayout(page);
  expect(saved.v).toBe(1);
  expect(Object.keys(saved.nodes)).toEqual(["riverbend"]);

  // The hub drags too, and every link starts at its new position.
  const hubStart = await glyphCentre(page, "gator-hub");
  await dragFromTo(page, hubStart, { x: hubStart.x - 50, y: hubStart.y + 30 });
  const hubMoved = await glyphCentre(page, "gator-hub");
  expectNear(hubMoved, { x: hubStart.x - 50, y: hubStart.y + 30 }, "dragged hub");
  for (const siteId of ["riverbend", "oak-terrace", "cedar-grove", "maple-crossing", "willow-creek", "pine-ridge"]) {
    expectNear(await linkPoint(page, siteId, "start"), hubMoved, `link to ${siteId} starts at the hub`);
  }
  await page.screenshot({ path: testInfo.outputPath("overview-1440-node-dragged.png"), fullPage: true });

  await reloadAtlas(page);
  expectNear(await glyphCentre(page, "riverbend"), moved, "position after reload");
  expectNear(await linkPoint(page, "riverbend", "end"), moved, "link after reload");
  expectNear(await glyphCentre(page, "gator-hub"), hubMoved, "hub after reload");

  await reset.click();
  expectNear(await glyphCentre(page, "riverbend"), start, "Reset layout restores the default");
  expectNear(await glyphCentre(page, "gator-hub"), hubStart, "Reset layout restores the hub");
  expect(Object.keys((await savedLayout(page))?.nodes ?? {})).toEqual([]);
  await reloadAtlas(page);
  expectNear(await glyphCentre(page, "riverbend"), start, "default after reset and reload");

  // A click, or a press that moves less than the drag threshold, still selects.
  const here = await glyphCentre(page, "riverbend");
  await dragFromTo(page, here, { x: here.x + 2, y: here.y + 1 }, 2);
  await expect(page.getByRole("dialog", { name: "Riverbend Pantry" })).toBeVisible();
  await page.keyboard.press("Escape");
  await oak.click();
  await expect(page.getByRole("dialog", { name: "Oak Terrace Pantry" })).toBeVisible();
  expect(pageErrors).toEqual([]);
});

test("dragging empty map pans every marker without saving a layout", async ({ page }) => {
  await openAtlas(page, 1440, 900);
  const riverbend = await glyphCentre(page, "riverbend");
  const hub = await glyphCentre(page, "gator-hub");
  // Midway between two markers: links do not take pointer events, so this is empty map.
  const empty = { x: (riverbend.x + hub.x) / 2 - 40, y: (riverbend.y + hub.y) / 2 + 30 };
  await dragFromTo(page, empty, { x: empty.x + 40, y: empty.y + 30 });
  expectNear(await glyphCentre(page, "riverbend"), { x: riverbend.x + 40, y: riverbend.y + 30 }, "pan moves riverbend");
  expectNear(await glyphCentre(page, "gator-hub"), { x: hub.x + 40, y: hub.y + 30 }, "pan moves the hub");
  expect(Object.keys((await savedLayout(page))?.nodes ?? {})).toEqual([]);
});

test("keyboard move mode: M, then arrows in 8px steps; Escape or Enter places the node and announces it", async ({ page }) => {
  const pageErrors = await openAtlas(page, 1440, 900);
  const riverbend = marker(page, "Riverbend Pantry");
  await expect(riverbend).toHaveAccessibleDescription(/Press M to move/);
  const announcer = page.locator("[data-atlas-announcer]");
  const start = await glyphCentre(page, "riverbend");

  // Arrows outside move mode do not move the node.
  await riverbend.focus();
  await page.keyboard.press("ArrowRight");
  expectNear(await glyphCentre(page, "riverbend"), start, "arrow without move mode");

  await page.keyboard.press("m");
  await expect(announcer).toContainText("Moving Riverbend Pantry");
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowDown");
  expectNear(await glyphCentre(page, "riverbend"), { x: start.x + 16, y: start.y + 8 }, "two right, one down");
  await page.keyboard.press("Escape");
  await expect(announcer).toContainText("Riverbend Pantry placed");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(riverbend).toBeFocused();
  await expect(riverbend).toHaveAttribute("aria-pressed", "false");

  // Enter also finishes, without selecting the site.
  await page.keyboard.press("M");
  await expect(announcer).toContainText("Moving Riverbend Pantry");
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("Enter");
  await expect(announcer).toContainText("Riverbend Pantry placed");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const placed = await glyphCentre(page, "riverbend");
  expectNear(placed, { x: start.x + 16, y: start.y }, "after one step up");

  await reloadAtlas(page);
  expectNear(await glyphCentre(page, "riverbend"), placed, "keyboard move persists");
  // Enter on a focused marker outside move mode still selects it.
  await marker(page, "Riverbend Pantry").focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog", { name: "Riverbend Pantry" })).toBeVisible();
  expect(pageErrors).toEqual([]);
});

test("drops are clamped: a node dropped on the card band, the legend or the inspector snaps clear", async ({ page }) => {
  await openAtlas(page, 1440, 900);
  const map = page.locator("[data-atlas-map]");
  const mapBox = await box(map);
  const willow = marker(page, "Willow Creek Pantry");

  // Onto the docked-card band along the bottom of the map.
  const willowGlyph = await glyphCentre(page, "willow-creek");
  await dragFromTo(page, willowGlyph, { x: willowGlyph.x + 30, y: mapBox.y + mapBox.height - 30 });
  const willowBox = await box(willow);
  expect(inside(willowBox, insetBox(mapBox, 8)), "dropped node stays inside the map").toBe(true);
  expect(overlaps(willowBox, await box(page.getByRole("group", { name: "Map controls" })), 8), "covers the zoom controls").toBe(false);
  expect(overlaps(willowBox, await box(page.getByText("Illustrative layout — not geography"))), "covers the caption").toBe(false);
  expect(overlaps(willowBox, await box(page.getByRole("button", { name: "Reset layout" }))), "covers Reset layout").toBe(false);
  // The docked card, opened for any site, does not cover the dropped node.
  for (const name of ["Riverbend Pantry", "Gator Distribution Hub", "Pine Ridge Pantry", "Willow Creek Pantry"]) {
    await marker(page, name).focus();
    await page.keyboard.press("Enter");
    const card = page.getByRole("dialog", { name });
    await expect(card).toBeVisible();
    expect(overlaps(await box(card), await box(willow)), `${name} card covers the dropped node`).toBe(false);
    await page.keyboard.press("Escape");
    await expect(card).toBeHidden();
  }

  // Onto the legend card.
  const legendBox = await box(page.locator("[data-legend-card]"));
  await dragFromTo(page, await glyphCentre(page, "oak-terrace"), centre(legendBox));
  const oakBox = await box(marker(page, "Oak Terrace Pantry"));
  expect(overlaps(oakBox, legendBox), "dropped node under the legend").toBe(false);
  expect(inside(oakBox, insetBox(mapBox, 8))).toBe(true);

  // Onto the inspector, at the right edge of the viewport.
  const cedarGlyph = await glyphCentre(page, "cedar-grove");
  await dragFromTo(page, cedarGlyph, { x: 1430, y: cedarGlyph.y });
  const cedarBox = await box(marker(page, "Cedar Grove Pantry"));
  expect(overlaps(cedarBox, await box(page.getByTestId("site-inspector"))), "dropped node under the inspector").toBe(false);
  expect(inside(cedarBox, insetBox(mapBox, 8))).toBe(true);
});

test("panels move by their grip handles at 1440, stay inside the map, persist and reset", async ({ page }, testInfo) => {
  const pageErrors = await openAtlas(page, 1440, 900);
  const mapBox = await box(page.locator("[data-atlas-map]"));
  const legend = page.locator("[data-legend-card]");
  const inspector = page.getByTestId("site-inspector");
  const legendHandle = page.getByRole("button", { name: "Move legend" });
  const inspectorHandle = page.getByRole("button", { name: "Move inspector" });
  await expect(legendHandle).toBeVisible();
  await expect(inspectorHandle).toBeVisible();
  const legendStart = await box(legend);
  const inspectorStart = await box(inspector);

  await dragBy(page, legendHandle, 160, 120);
  expectNear(await box(legend), { x: legendStart.x + 160, y: legendStart.y + 120 }, "legend dragged");
  await dragBy(page, inspectorHandle, -180, 0);
  expectNear(await box(inspector), { x: inspectorStart.x - 180, y: inspectorStart.y }, "inspector dragged");

  // Keyboard: arrow keys on the focused handle move the panel in 8px steps.
  await legendHandle.focus();
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("ArrowUp");
  expectNear(await box(legend), { x: legendStart.x + 144, y: legendStart.y + 112 }, "legend after arrow keys");
  await page.screenshot({ path: testInfo.outputPath("overview-1440-panels-moved.png"), fullPage: true });

  // Clamped within the map: the inspector dragged to the viewport edge, the legend to the map's far corner.
  const inspectorGrip = centre(await box(inspectorHandle));
  await dragFromTo(page, inspectorGrip, { x: 1439, y: inspectorGrip.y });
  expect(inside(await box(inspector), mapBox), "inspector leaves the map").toBe(true);
  await dragBy(page, inspectorHandle, -180, 0);
  const inspectorMoved = await box(inspector);
  await dragFromTo(page, centre(await box(legendHandle)), { x: mapBox.x + mapBox.width - 4, y: mapBox.y + mapBox.height - 4 });
  const legendMoved = await box(legend);
  expect(inside(legendMoved, mapBox), "legend leaves the map").toBe(true);

  // The docked selection card moves by its own handle and stays open.
  const riverbend = marker(page, "Riverbend Pantry");
  await riverbend.focus();
  await page.keyboard.press("Enter");
  const card = page.getByRole("dialog", { name: "Riverbend Pantry" });
  await expect(card).toBeVisible();
  const cardStart = await box(card);
  await dragBy(page, card.getByRole("button", { name: "Move selection card" }), 120, -60);
  await expect(card).toBeVisible();
  const cardMoved = await box(card);
  expectNear(cardMoved, { x: cardStart.x + 120, y: cardStart.y - 60 }, "card dragged");
  expect(inside(cardMoved, mapBox), "card leaves the map").toBe(true);
  await page.keyboard.press("Escape");
  await expect(card).toBeHidden();
  await expect(riverbend).toBeFocused();

  const saved = await savedLayout(page);
  expect(saved.v).toBe(1);
  expect(Object.keys(saved.panels).sort()).toEqual(["card", "inspector", "legend"]);

  await reloadAtlas(page);
  expectNear(await box(legend), legendMoved, "legend after reload");
  expectNear(await box(inspector), inspectorMoved, "inspector after reload");
  await marker(page, "Riverbend Pantry").focus();
  await page.keyboard.press("Enter");
  await expect(card).toBeVisible();
  expectNear(await box(card), cardMoved, "card after reload");
  await page.keyboard.press("Escape");
  await expect(card).toBeHidden();

  await page.getByRole("button", { name: "Reset layout" }).click();
  expectNear(await box(legend), legendStart, "legend reset");
  expectNear(await box(inspector), inspectorStart, "inspector reset");
  await marker(page, "Riverbend Pantry").focus();
  await page.keyboard.press("Enter");
  await expect(card).toBeVisible();
  expectNear(await box(card), cardStart, "card reset");
  expect(Object.keys((await savedLayout(page))?.panels ?? {})).toEqual([]);
  expect(pageErrors).toEqual([]);
});

test("at 390 panels have no drag handles; nodes still drag", async ({ page }) => {
  await openAtlas(page, 390, 844);
  await expect(page.getByRole("button", { name: /^Move (legend|inspector|selection card)$/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Reset layout" })).toBeVisible();
  await marker(page, "Riverbend Pantry").scrollIntoViewIfNeeded();
  const start = await glyphCentre(page, "riverbend");
  await dragFromTo(page, start, { x: start.x + 24, y: start.y + 40 });
  expectNear(await glyphCentre(page, "riverbend"), { x: start.x + 24, y: start.y + 40 }, "node dragged at 390");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test.describe("touch", () => {
  test.use({ hasTouch: true });

  // The tap comes first: after a CDP-synthesised touch drag Chromium emits no click for the next tap,
  // even after a plain empty-map pan (checked while writing this test), so that order tests the harness.
  test("a tap selects a node and a touch drag moves one at 390 without selecting it", async ({ page }) => {
    await openAtlas(page, 390, 844);
    await marker(page, "Riverbend Pantry").scrollIntoViewIfNeeded();
    const oak = await glyphCentre(page, "oak-terrace");
    await page.touchscreen.tap(oak.x, oak.y);
    await expect(page.getByRole("dialog", { name: "Oak Terrace Pantry" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    const start = await glyphCentre(page, "riverbend");
    const cdp = await page.context().newCDPSession(page);
    const touch = (type: "touchStart" | "touchMove" | "touchEnd", point?: Point) =>
      cdp.send("Input.dispatchTouchEvent", { type, touchPoints: point ? [{ x: point.x, y: point.y }] : [] });
    await touch("touchStart", start);
    for (let step = 1; step <= 8; step += 1) await touch("touchMove", { x: start.x + 3 * step, y: start.y + 5 * step });
    await touch("touchEnd");
    expectNear(await glyphCentre(page, "riverbend"), { x: start.x + 24, y: start.y + 40 }, "touch-dragged node");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    expect(Object.keys((await savedLayout(page))?.nodes ?? {})).toEqual(["riverbend"]);
  });
});

// Decision 4 (user override of ART-DIRECTION's perpetual-motion ban): every supply link flows from the
// hub to its pantry while motion is allowed; OS reduced motion stops it and leaves a static line.
test("supply links flow continuously hub to pantry; the selected link flows faster; reduced motion stops it", async ({ page }) => {
  await openAtlas(page, 1440, 900, "no-preference");
  const flows = page.locator("[data-supply-flow]");
  await expect(flows).toHaveCount(6);
  const flowAnimations = () => page.evaluate(() => document.getAnimations()
    .filter((animation) => animation.playState === "running")
    .flatMap((animation) => {
      const effect = animation.effect as KeyframeEffect | null;
      const target = effect?.target;
      if (!effect || !(target instanceof Element) || !target.matches("[data-supply-flow]")) return [];
      const timing = effect.getComputedTiming();
      return [{ id: target.getAttribute("data-supply-flow"), duration: Number(timing.duration), infinite: timing.iterations === Infinity, opacity: Number(getComputedStyle(target).opacity) }];
    }));
  await expect.poll(async () => (await flowAnimations()).length).toBe(6);
  for (const flow of await flowAnimations()) expect(flow.infinite, `${flow.id} loops`).toBe(true);
  // Each flow follows its own link's path, which starts at the hub.
  for (const flow of await flows.all()) {
    const id = await flow.getAttribute("data-supply-flow");
    expect(await flow.getAttribute("d")).toBe(await page.locator(`[data-supply-link="${id}"]`).getAttribute("d"));
  }
  const legend = page.locator("[data-legend-card]");
  await expect(legend).toContainText("Supply link: the hub can send to this pantry; not a planned route or shipment");

  await marker(page, "Riverbend Pantry").focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog", { name: "Riverbend Pantry" })).toBeVisible();
  await expect.poll(async () => {
    const running = await flowAnimations();
    const selected = running.find((flow) => flow.id === "riverbend");
    const others = running.filter((flow) => flow.id !== "riverbend");
    return Boolean(selected) && others.length === 5 && others.every((flow) => flow.duration > selected!.duration && flow.opacity < selected!.opacity);
  }, { message: "the selected link flows faster and brighter" }).toBe(true);

  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect.poll(async () => (await flowAnimations()).length).toBe(0);
  expect(await page.evaluate(() => document.getAnimations().filter((animation) => animation.playState === "running" && animation.effect?.getComputedTiming().iterations === Infinity).length)).toBe(0);
  await expect(page.locator("[data-supply-link]")).toHaveCount(6);
});

test("with reduced motion from the start, no supply link animates", async ({ page }) => {
  await openAtlas(page, 1440, 900, "reduce");
  await expect(page.locator("[data-supply-link]")).toHaveCount(6);
  await page.waitForTimeout(300);
  expect(await page.evaluate(() => document.getAnimations().filter((animation) => animation.playState === "running").length)).toBe(0);
});
