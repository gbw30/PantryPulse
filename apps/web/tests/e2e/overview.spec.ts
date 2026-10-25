import { expect, test, type Locator, type Page, type TestInfo } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";

// Mockup-only content (docs/design/reference/overview.md) must never reach the app.
const MOCKUP_ONLY = ["Alex Chen", "Phoenix", "Canned Protein", "Riverside Community Pantry", "62%", "4,200"];

type Box = { x: number; y: number; width: number; height: number };

function overlaps(a: Box, b: Box, gap = 0) {
  return a.x < b.x + b.width + gap && b.x < a.x + a.width + gap && a.y < b.y + b.height + gap && b.y < a.y + a.height + gap;
}

function inside(inner: Box, outer: Box, tolerance = 1) {
  return inner.x >= outer.x - tolerance && inner.y >= outer.y - tolerance
    && inner.x + inner.width <= outer.x + outer.width + tolerance && inner.y + inner.height <= outer.y + outer.height + tolerance;
}

async function box(locator: Locator) {
  const result = await locator.boundingBox();
  expect(result).not.toBeNull();
  return result!;
}

async function expectMarkersInsideMap(page: Page) {
  await expect.poll(() => page.locator("[data-atlas-map]").evaluate((map) => {
    const bounds = map.getBoundingClientRect();
    const markers = [...map.querySelectorAll("[data-marker-role]")];
    return markers.length === 7 && markers.every((marker) => {
      const rect = marker.getBoundingClientRect();
      return rect.left >= bounds.left && rect.right <= bounds.right && rect.top >= bounds.top && rect.bottom <= bounds.bottom;
    });
  })).toBe(true);
}

// Map controls keep at least 8px of clearance from every marker and its label.
async function expectControlsClearOfMarkers(page: Page) {
  const controls = await box(page.getByRole("group", { name: "Map controls" }));
  for (const marker of await page.locator("[data-marker-role]").all()) {
    expect(overlaps(controls, await box(marker), 8), "map controls crowd a marker").toBe(false);
  }
}

async function chooseProduct(page: Page, name: RegExp) {
  await page.getByRole("combobox", { name: "Product" }).click();
  await page.getByRole("option", { name }).click();
}

const marker = (page: Page, name: string) => page.getByRole("button", { name: new RegExp(`^${name}, `) });

const SITES = ["Riverbend Pantry", "Oak Terrace Pantry", "Cedar Grove Pantry", "Maple Crossing Pantry", "Willow Creek Pantry", "Pine Ridge Pantry", "Gator Distribution Hub"];
const slug = (name: string) => name.replace(/ (Pantry|Distribution Hub)$/, (match) => (match.includes("Hub") ? " hub" : "")).toLowerCase().replace(/ /g, "-");

// No text in the scope is clipped: nothing overflows its box and nothing is truncated with an ellipsis.
async function expectNoClippedText(scope: Locator, label: string) {
  const clipped = await scope.evaluate((root) => [root, ...root.querySelectorAll("*")]
    .filter((element) => {
      if (!(element instanceof HTMLElement)) return false;
      return element.scrollWidth > element.clientWidth + 1 || getComputedStyle(element).textOverflow === "ellipsis";
    })
    .map((element) => `${element.tagName.toLowerCase()} "${(element.textContent ?? "").slice(0, 40)}"`));
  expect(clipped, `${label}: clipped text`).toEqual([]);
}

function insetBox(rect: Box, inset: number): Box {
  return { x: rect.x + inset, y: rect.y + inset, width: rect.width - inset * 2, height: rect.height - inset * 2 };
}

const BENEFICIARY_IDS = ["riverbend", "oak-terrace", "cedar-grove", "maple-crossing", "willow-creek", "pine-ridge"];

// Supply links: exactly one hub -> pantry link per beneficiary; never pantry <-> pantry.
async function expectSupplyLinks(page: Page) {
  const links = page.locator("[data-supply-link]");
  await expect(links).toHaveCount(6);
  const pairs = await links.evaluateAll((paths) => paths.map((path) => [path.getAttribute("data-from"), path.getAttribute("data-supply-link")]));
  for (const [from] of pairs) expect(from).toBe("gator-hub");
  expect(pairs.map(([, to]) => to).sort()).toEqual([...BENEFICIARY_IDS].sort());
}

async function linkEmphasis(page: Page) {
  return page.locator("[data-supply-link]").evaluateAll((paths) => Object.fromEntries(paths.map((path) => [path.getAttribute("data-supply-link"), path.getAttribute("data-emphasis")])));
}

const chipName = (name: string) => (name.includes("Hub") ? "Gator Hub" : name.replace(/ Pantry$/, ""));

async function markerBoxes(page: Page) {
  const boxes = new Map<string, Box>();
  for (const name of SITES) boxes.set(name, await box(marker(page, name)));
  return boxes;
}

// A scroll cue is visible whenever the inspector's content overflows it.
async function expectScrollCueWhenOverflowing(inspector: Locator) {
  const overflows = await inspector.evaluate((element) => element.scrollHeight > element.clientHeight + 1 && element.scrollTop + element.clientHeight < element.scrollHeight - 4);
  if (overflows) await expect(inspector.getByText("More below")).toBeVisible();
}

// Opens the atlas at one viewport with reduced motion; returns the page errors seen so far.
async function openAtlas(page: Page, width: number, height: number) {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.setViewportSize({ width, height });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/overview");
  await expect(page.getByRole("heading", { level: 1, name: "Network Atlas" })).toBeVisible();
  await expect(page.locator("[data-marker-role]")).toHaveCount(7);
  return pageErrors;
}

// Each viewport runs as four focused tests (default view, popovers, inspector, product switch) so no
// single test approaches the 30s timeout in a loaded checkout. Every assertion, scan and capture is kept.
for (const [width, height] of [[1440, 900], [1280, 720], [390, 844]]) {
  const desktop = width >= 1024;
  const shooter = (page: Page, testInfo: TestInfo) => (name: string) => page.screenshot({ path: testInfo.outputPath(`overview-${width}-${name}.png`), fullPage: true });

  test(`network atlas at ${width}x${height}: default view, legend, deficits and shell`, async ({ page }, testInfo) => {
    const pageErrors = await openAtlas(page, width, height);
    const shot = shooter(page, testInfo);
    await expect(page.getByText("SIMULATED — static design fixture, not model output")).toBeVisible();
    await expect(page.getByText("Illustrative layout — not geography")).toBeVisible();
    await expect(page.getByText("Simulated network", { exact: true })).toBeVisible();

    // Legend: the four beneficiary states, each with a visible one-line meaning.
    const legend = page.getByRole("list", { name: "Site status legend" });
    for (const [state, meaning] of [["Shortfall", "unmet on this day"], ["Watch", "deficit later"], ["Covered", "no unmet ahead"], ["Not evaluated", "no projection"]]) {
      const item = legend.getByRole("listitem").filter({ hasText: state });
      await expect(item.getByText(state, { exact: true })).toBeVisible();
      await expect(item.getByText(meaning, { exact: true })).toBeVisible();
    }

    // Six beneficiaries plus one hub, all inside the map canvas, clear of the controls.
    await expect(page.locator('[data-marker-role="beneficiary"]')).toHaveCount(6);
    await expect(page.locator('[data-marker-role="hub"]')).toHaveCount(1);
    await expectMarkersInsideMap(page);
    await expectControlsClearOfMarkers(page);
    await expectSupplyLinks(page);
    const legendCard = page.locator("[data-legend-card]");
    await expect(legendCard.getByText("Supply link", { exact: true })).toBeVisible();
    await expect(legendCard).toContainText("the hub can send to this pantry; not a planned route or shipment");
    if (desktop) {
      // Polish: >= 24px between every pair of marker + label boxes; the legend card clears markers and links.
      const boxes = [...(await markerBoxes(page)).entries()];
      for (let i = 0; i < boxes.length; i += 1) {
        for (let j = i + 1; j < boxes.length; j += 1) expect(overlaps(boxes[i][1], boxes[j][1], 24), `${boxes[i][0]} within 24px of ${boxes[j][0]}`).toBe(false);
      }
      const legendBox = await box(legendCard);
      for (const [name, rect] of boxes) expect(overlaps(legendBox, rect), `legend covers ${name}`).toBe(false);
      for (const link of await page.locator("[data-supply-link]").all()) expect(overlaps(legendBox, await box(link)), "legend covers a supply link").toBe(false);
      // >= 24px between the header block, the site strip and the map.
      const header = await box(page.locator("[data-atlas-header]"));
      const strip = await box(page.locator("[data-site-strip]"));
      const mapSection = await box(page.getByRole("region", { name: "Network map" }));
      expect(strip.y - (header.y + header.height), "header to strip gap").toBeGreaterThanOrEqual(24);
      expect(mapSection.y - (strip.y + strip.height), "strip to map gap").toBeGreaterThanOrEqual(24);
    }
    // Site chips keep >= 8px between neighbours.
    const chipBoxes = await Promise.all((await page.getByRole("list", { name: "All sites" }).getByRole("button").all()).map((chip) => box(chip)));
    for (let index = 1; index < chipBoxes.length; index += 1) {
      if (Math.abs(chipBoxes[index].y - chipBoxes[index - 1].y) < 1) expect(chipBoxes[index].x - (chipBoxes[index - 1].x + chipBoxes[index - 1].width)).toBeGreaterThanOrEqual(8);
    }
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);

    // Mobile first viewport: every legend state and the first two markers are visible together.
    if (!desktop) {
      for (const item of await legend.getByRole("listitem").all()) expect((await box(item)).y + (await box(item)).height).toBeLessThanOrEqual(height);
      for (const name of ["Riverbend Pantry", "Oak Terrace Pantry"]) {
        const rect = await box(marker(page, name));
        expect(rect.y + rect.height, `${name} below the first viewport`).toBeLessThanOrEqual(height);
      }
      await expect(page.getByText("Scroll sideways for all 7 sites")).toBeVisible();
    }

    // Watch sites name their next deficit date without a click.
    await expect(page.getByRole("list", { name: "All sites" }).getByRole("button", { name: /Oak Terrace Watch · Oct 27/ })).toBeVisible();
    await expect(page.getByRole("list", { name: "All sites" }).getByRole("button", { name: /Willow Creek Watch · Oct 29/ })).toBeVisible();
    if (desktop) {
      const deficits = page.getByRole("list", { name: "Projected deficits" });
      await expect(deficits.getByRole("button")).toHaveText([/Riverbend · Sat, Oct 24 · 20 meals unmet/, /Pine Ridge · Sat, Oct 24 · 14 meals unmet/, /Oak Terrace · Tue, Oct 27 · 35 meals unmet/, /Willow Creek · Thu, Oct 29 · 36 meals unmet/]);
      // N3: every status count is visible inside the unselected inspector.
      const inspectorPanel = page.getByTestId("site-inspector");
      const panelBox = await box(inspectorPanel);
      for (const state of ["Shortfall", "Watch", "Covered", "Not evaluated"]) {
        const count = inspectorPanel.getByRole("definition").filter({ hasText: state });
        expect(inside(await box(count), panelBox), `${state} count clipped`).toBe(true);
      }
      await expectScrollCueWhenOverflowing(inspectorPanel);
    }

    // The top bar carries no person, avatar or account identity.
    const topBar = page.getByRole("banner");
    await expect(topBar.locator("img")).toHaveCount(0);
    await expect(topBar.locator('[data-slot="avatar"]')).toHaveCount(0);
    for (const text of MOCKUP_ONLY) await expect(page.getByText(text, { exact: false })).toHaveCount(0);
    await expect(page.getByText("No account · read-only demo")).toHaveCount(width >= 768 ? 1 : 0);

    await shot("map-unselected");
    await expectNoSeriousA11yViolations(page, testInfo, `overview ${width}x${height} default`);
    expect(pageErrors).toEqual([]);
  });

  test(`network atlas at ${width}x${height}: popovers for every site`, async ({ page }, testInfo) => {
    const pageErrors = await openAtlas(page, width, height);
    const shot = shooter(page, testInfo);

    // Popovers open by keyboard, stay inside the map and clear of the inspector, and return focus on Esc.
    for (const [name, slugName, deficit] of [["Riverbend Pantry", "riverbend", "Next deficit Sat, Oct 24 · 20 meals unmet"], ["Oak Terrace Pantry", "oak-terrace", "Next deficit Tue, Oct 27 · 35 meals unmet"]]) {
      const target = marker(page, name);
      await target.focus();
      await page.keyboard.press("Enter");
      const popover = page.getByRole("dialog", { name });
      await expect(popover).toBeVisible();
      await expect(popover).toContainText(deficit);
      await expect(popover.getByRole("button", { name: "Inspect site" })).toBeVisible();
      const popoverBox = await box(popover);
      // Measured after opening: on narrow layouts selecting scrolls the map fully into view.
      const mapBox = await box(page.locator("[data-atlas-map]"));
      expect(inside(popoverBox, mapBox), `${name} popover leaves the map`).toBe(true);
      if (desktop) expect(overlaps(popoverBox, await box(page.getByTestId("site-inspector"))), `${name} popover covers the inspector`).toBe(false);
      expect(overlaps(popoverBox, await box(target)), `${name} popover covers its marker`).toBe(false);
      if (!desktop) {
        // N2: the docked card clears the zoom controls and leaves at least four markers unobscured.
        expect(overlaps(popoverBox, await box(page.getByRole("group", { name: "Map controls" }))), "popover covers the zoom controls").toBe(false);
        const clear = [...(await markerBoxes(page)).values()].filter((rect) => !overlaps(popoverBox, rect));
        expect(clear.length, "fewer than four markers stay visible").toBeGreaterThanOrEqual(4);
      }
      await shot(`popover-${slugName}`);
      await page.keyboard.press("Escape");
      await expect(popover).toBeHidden();
      await expect(target).toBeFocused();
    }

    if (desktop) {
      for (const name of SITES) {
        const target = marker(page, name);
        await target.focus();
        await page.keyboard.press("Enter");
        const popover = page.getByRole("dialog", { name });
        await expect(popover).toBeVisible();
        const popoverBox = await box(popover);
        expect(inside(popoverBox, insetBox(await box(page.locator("[data-atlas-map]")), 16)), `${name} card within 16px of the map edge`).toBe(true);
        const emphasis = await linkEmphasis(page);
        if (name.includes("Hub")) expect(Object.values(emphasis).every((value) => value === "true"), "hub selected: every link emphasized").toBe(true);
        else for (const [id, value] of Object.entries(emphasis)) expect(value, `${name}: link to ${id}`).toBe(id === slug(name) ? "true" : "false");
        expect(overlaps(popoverBox, await box(page.getByTestId("site-inspector"))), `${name} popover covers the inspector`).toBe(false);
        for (const [other, rect] of await markerBoxes(page)) expect(overlaps(popoverBox, rect), `${name} popover covers ${other}`).toBe(false);
        await expectNoClippedText(popover, `${width} ${name} card`);
        if (width === 1280 && ["Gator Distribution Hub", "Maple Crossing Pantry", "Pine Ridge Pantry"].includes(name)) await shot(`popover-${name.includes("Hub") ? "hub" : slug(name)}`);
        await page.keyboard.press("Escape");
        await expect(target).toBeFocused();
      }
    }

    if (!desktop) {
      const chips = page.getByRole("list", { name: "All sites" });
      for (const name of SITES) {
        const chip = chips.getByRole("button", { name: new RegExp(`^${chipName(name)} `) });
        await chip.click();
        const popover = page.getByRole("dialog", { name });
        await expect(popover).toBeVisible();
        const popoverBox = await box(popover);
        expect(inside(popoverBox, insetBox(await box(page.locator("[data-atlas-map]")), 16)), `${name} card within 16px of the map edge`).toBe(true);
        expect(overlaps(popoverBox, await box(marker(page, name))), `${name} card covers its own marker`).toBe(false);
        expect(overlaps(popoverBox, await box(page.getByRole("group", { name: "Map controls" }))), `${name} card covers the zoom controls`).toBe(false);
        const clear = [...(await markerBoxes(page)).values()].filter((rect) => !overlaps(popoverBox, rect));
        expect(clear.length, `${name}: fewer than four markers stay visible`).toBeGreaterThanOrEqual(4);
        await expectNoClippedText(popover, `${width} ${name} card`);
        if (["Willow Creek Pantry", "Cedar Grove Pantry", "Maple Crossing Pantry", "Gator Distribution Hub"].includes(name)) await shot(`popover-${name.includes("Hub") ? "gator-hub" : slug(name)}`);
        await page.keyboard.press("Escape");
        await expect(popover).toBeHidden();
        await expect(chip).toBeFocused();
      }
    }
    expect(pageErrors).toEqual([]);
  });

  test(`network atlas at ${width}x${height}: inspector network and demand table`, async ({ page }, testInfo) => {
    const pageErrors = await openAtlas(page, width, height);
    const shot = shooter(page, testInfo);

    // Inspect site opens the inspector on the Network tab with the selected product's units.
    const riverbend = marker(page, "Riverbend Pantry");
    await expect(riverbend).toHaveAccessibleName(/Shortfall/);
    await riverbend.focus();
    await page.keyboard.press("Enter");
    await page.getByRole("button", { name: "Inspect site" }).click();
    const inspector = page.getByTestId("site-inspector");
    const heading = inspector.getByRole("heading", { name: "Riverbend Pantry" });
    await expect(heading).toBeVisible();
    await expect(inspector).toContainText("Shelf-stable meals");
    await expect(inspector).not.toContainText("bottle");
    await expect(inspector.getByText("Routes hidden — no saved plan")).toBeVisible();
    await expect(inspector.getByRole("button", { name: "Go to Site Details" })).toBeDisabled();
    await expect(page.locator("button.bg-primary:not([disabled]):visible")).toHaveCount(0);
    await expectScrollCueWhenOverflowing(inspector);
    await shot("inspector-network");
    await expectNoSeriousA11yViolations(page, testInfo, `overview ${width}x${height} inspector network`);

    // Demand tab: the data table fits the inspector width; the header stays visible while scrolling.
    await inspector.getByRole("tab", { name: "Demand" }).click();
    await inspector.getByRole("button", { name: "Show data table" }).click();
    const table = inspector.getByRole("table");
    await expect(table).toBeVisible();
    await expect(table.getByRole("row")).toHaveCount(8);
    await expect(table.getByRole("columnheader", { name: "Demand outlook (meals)" })).toBeVisible();
    const labels = table.locator("thead [data-col-label]");
    const labelBoxes = await Promise.all((await labels.all()).map((label) => box(label)));
    expect(labelBoxes.length).toBe(5);
    for (let index = 1; index < labelBoxes.length; index += 1) {
      const gap = labelBoxes[index].x - (labelBoxes[index - 1].x + labelBoxes[index - 1].width);
      expect(gap, `table header gap before column ${index + 1}`).toBeGreaterThanOrEqual(8);
    }
    const tableRegion = inspector.getByRole("region", { name: /daily outlook table/ });
    expect(await tableRegion.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    const lastUnmet = table.getByRole("row", { name: /Fri, Oct 30/ }).getByRole("cell").last();
    await lastUnmet.scrollIntoViewIfNeeded();
    await expect(lastUnmet).toBeInViewport();
    expect(inside(await box(lastUnmet), await box(inspector))).toBe(true);
    expect(inside(await box(heading), await box(inspector)), "inspector header scrolled out of view").toBe(true);
    await expect(heading).toBeInViewport();
    await expectNoSeriousA11yViolations(page, testInfo, `overview ${width}x${height} inspector demand`);
    await expectScrollCueWhenOverflowing(inspector);
    await shot("inspector-demand-table-open");
    await page.keyboard.press("Escape");
    await expect(riverbend).toBeFocused();
    expect(pageErrors).toEqual([]);
  });

  test(`network atlas at ${width}x${height}: product switch changes units`, async ({ page }) => {
    const pageErrors = await openAtlas(page, width, height);
    const riverbend = marker(page, "Riverbend Pantry");
    // Switching product changes the units and statuses shown.
    await chooseProduct(page, /Bottled water/);
    await expect(page.getByRole("button", { name: /^Pine Ridge Pantry, beneficiary pantry, Not evaluated/ })).toBeVisible();
    await riverbend.focus();
    await page.keyboard.press("Enter");
    const popover = page.getByRole("dialog", { name: "Riverbend Pantry" });
    await expect(popover).toContainText("bottles");
    await expect(popover).not.toContainText("meal");
    await page.keyboard.press("Escape");
    await expect(riverbend).toBeFocused();
    expect(pageErrors).toEqual([]);
  });
}

// Escape must not depend on where focus happens to be: with a site open in the inspector and focus
// on the page body (e.g. after the focused control was remounted), Escape still clears the selection
// and returns focus to the site's marker.
test("Escape with focus outside the inspector clears the selection at 1280x720", async ({ page }) => {
  const pageErrors = await openAtlas(page, 1280, 720);
  const riverbend = marker(page, "Riverbend Pantry");
  await riverbend.focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Inspect site" }).click();
  const inspector = page.getByTestId("site-inspector");
  await expect(inspector.getByRole("heading", { name: "Riverbend Pantry" })).toBeVisible();
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  await expect.poll(() => page.evaluate(() => document.activeElement === document.body)).toBe(true);
  await page.keyboard.press("Escape");
  await expect(riverbend).toHaveAttribute("aria-pressed", "false");
  await expect(inspector.getByRole("heading", { name: "Site inspector" })).toBeVisible();
  await expect(riverbend).toBeFocused();
  expect(pageErrors).toEqual([]);
});

// Unknown or inherited preview keys fall back to the static fixture instead of crashing.
for (const key of ["toString", "__proto__", "constructor", "hasOwnProperty"]) {
  test(`?state=${key} shows the normal atlas without errors`, async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await page.goto(`/overview?state=${key}`);
    await expect(page.getByRole("heading", { level: 1, name: "Network Atlas" })).toBeVisible();
    await expect(page.locator("[data-marker-role]")).toHaveCount(7);
    await expect(page.getByRole("note")).toHaveCount(0);
    expect(pageErrors).toEqual([]);
  });
}

test("water product and hub views at 1440x900", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/overview");
  await chooseProduct(page, /Bottled water/);
  const pine = marker(page, "Pine Ridge Pantry");
  await expect(pine).toHaveAccessibleName(/Not evaluated, insufficient data/);
  await pine.focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Inspect site" }).click();
  const inspector = page.getByTestId("site-inspector");
  await expect(inspector).toContainText("Insufficient data");
  await expect(inspector).toContainText("96 bottles");
  await expect(inspector).not.toContainText("A deficit here");
  await expect(inspector).toContainText("No projection, so transfers can't be assessed.");
  await page.screenshot({ path: testInfo.outputPath("overview-1440-water-insufficient.png"), fullPage: true });
  await page.keyboard.press("Escape");
  await chooseProduct(page, /Shelf-stable meals/);
  const cedar = marker(page, "Cedar Grove Pantry");
  await cedar.focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Inspect site" }).click();
  await expect(inspector).not.toContainText("A deficit here");
  await expect(inspector).toContainText("No projected deficit, so no transfer is needed in this view.");
  await page.keyboard.press("Escape");
  const hub = marker(page, "Gator Distribution Hub");
  await hub.focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Inspect site" }).click();
  await expect(inspector).toContainText("Hub · source");
  await expect(inspector).toContainText("the hub has no demand forecast");
  await page.screenshot({ path: testInfo.outputPath("overview-1440-hub.png"), fullPage: true });
});

test("next deficits follow the selected local day (Wed, Oct 28)", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/overview");
  await page.getByRole("combobox", { name: "Local day" }).click();
  await page.getByRole("option", { name: "Wed, Oct 28" }).click();
  await expect(page.getByRole("combobox", { name: "Local day" })).toHaveText(/Wed, Oct 28/);
  const DAY = /(?:Sat|Sun|Mon|Tue|Wed|Thu|Fri), Oct (\d+)|Oct (\d+)/g;
  const datesIn = (text: string) => [...text.matchAll(DAY)].map((match) => Number(match[1] ?? match[2]));
  const deficitDates = (text: string) => [...text.matchAll(/(?:next deficit|Next deficit) (?:Sat|Sun|Mon|Tue|Wed|Thu|Fri), Oct (\d+)/g)].map((match) => Number(match[1]));

  for (const button of await page.getByRole("list", { name: "Projected deficits" }).getByRole("button").all()) {
    for (const day of datesIn((await button.textContent()) ?? "")) expect(day).toBeGreaterThanOrEqual(28);
  }
  for (const chip of await page.getByRole("list", { name: "All sites" }).getByRole("button").all()) {
    for (const day of datesIn((await chip.textContent()) ?? "")) expect(day).toBeGreaterThanOrEqual(28);
  }
  await page.screenshot({ path: testInfo.outputPath("overview-1440-day-oct28-unselected.png"), fullPage: true });

  for (const name of SITES) {
    const target = marker(page, name);
    const accessibleName = (await target.getAttribute("aria-label")) ?? "";
    for (const day of deficitDates(accessibleName)) expect(day, `${name} marker`).toBeGreaterThanOrEqual(28);
    await target.focus();
    await page.keyboard.press("Enter");
    const popover = page.getByRole("dialog", { name });
    await expect(popover).toBeVisible();
    const text = (await popover.textContent()) ?? "";
    for (const day of deficitDates(text)) expect(day, `${name} popover`).toBeGreaterThanOrEqual(28);
    if (accessibleName.includes(", Covered,")) {
      expect(deficitDates(text), `${name} is Covered but shows a deficit date`).toEqual([]);
      await expect(popover).toContainText("No projected deficit");
      await popover.getByRole("button", { name: "Inspect site" }).click();
      const inspector = page.getByTestId("site-inspector");
      expect(deficitDates((await inspector.textContent()) ?? ""), `${name} inspector`).toEqual([]);
      await page.keyboard.press("Escape");
    } else {
      await page.keyboard.press("Escape");
    }
    await expect(target).toBeFocused();
  }
});

test("site search filters the list and selects a match", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/overview");
  const search = page.getByRole("searchbox", { name: "Search sites or products" });
  await expect(search).toHaveAttribute("placeholder", "Search sites or products…");
  await search.fill("oak");
  const list = page.getByRole("list", { name: "All sites" });
  await expect(list.getByRole("button")).toHaveCount(1);
  await expect(page.getByRole("list", { name: "Matching products" })).toHaveCount(0);
  await search.press("Enter");
  await expect(page.getByRole("dialog", { name: "Oak Terrace Pantry" })).toBeVisible();
});

// The fixture has no region data, so search covers sites and products only.
test("product search offers a product and switches units", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/overview");
  const search = page.getByRole("searchbox", { name: "Search sites or products" });
  const product = page.getByRole("combobox", { name: "Product" });
  await expect(product).toHaveText(/Shelf-stable meals \(meals\)/);

  await search.fill("water");
  const results = page.getByRole("list", { name: "Matching products" });
  const water = results.getByRole("button", { name: /Bottled water \(bottles\)/ });
  await expect(water).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("overview-1440-search-water.png"), fullPage: true });
  await water.click();
  await expect(product).toHaveText(/Bottled water \(bottles\)/);
  await expect(page.getByText(/Site status · Bottled water \(bottles\)/)).toBeVisible();
  await expect(page.getByRole("button", { name: /^Pine Ridge Pantry, beneficiary pantry, Not evaluated/ })).toBeVisible();

  // Keyboard: Enter selects the first match; with no matching site that is the product.
  await search.fill("meal");
  await expect(page.getByRole("list", { name: "Matching products" }).getByRole("button", { name: /Shelf-stable meals/ })).toBeVisible();
  await search.press("Enter");
  await expect(product).toHaveText(/Shelf-stable meals \(meals\)/);
  await search.fill("bottle");
  await search.press("Enter");
  await expect(product).toHaveText(/Bottled water \(bottles\)/);
});

test("first load animates supply links and markers, then settles", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/overview");
  await page.locator("[data-supply-link]").first().waitFor({ state: "attached" });
  const sample = () => page.evaluate(() => ({
    links: [...document.querySelectorAll("[data-supply-link]")].map((path) => `${path.getAttribute("stroke-dasharray")}|${path.getAttribute("stroke-dashoffset")}`),
    markers: [...document.querySelectorAll("[data-marker-role]")].map((marker) => `${getComputedStyle(marker).opacity}|${getComputedStyle(marker).transform}`),
    running: document.getAnimations().filter((animation) => animation.playState === "running").length,
  }));
  const first = await sample();
  await page.waitForTimeout(120);
  const second = await sample();
  expect(first.links.some((value, index) => value !== second.links[index]), "supply links draw in").toBe(true);
  expect(first.markers.some((value, index) => value !== second.markers[index]) || first.running > 0, "markers animate in").toBe(true);
  // Everything settles: final opacity 1, links fully drawn, and nothing changes between frames.
  await page.waitForTimeout(1500);
  const settled = await sample();
  await page.waitForTimeout(250);
  const later = await sample();
  expect(later).toEqual(settled);
  for (const value of settled.markers) expect(value.split("|")[0]).toBe("1");
  for (const value of settled.links) expect(Number.parseFloat(value.split("|")[0].split(/[ ,]/)[0])).toBeGreaterThanOrEqual(0.999);
  expect(settled.running).toBe(0);
});

test("loading keeps the legend and a stable skeleton", async ({ page }) => {
  await page.goto("/overview?state=loading");
  await expect(page.getByRole("list", { name: "Site status legend" })).toBeVisible();
  await expect(page.getByText("Loading network snapshot")).toBeVisible();
  await expect(page.locator("[data-marker-role]")).toHaveCount(0);
});

test("empty snapshot shows every site as not evaluated", async ({ page }) => {
  await page.goto("/overview?state=empty");
  await expect(page.getByText("No projection is available for this snapshot.", { exact: false })).toBeVisible();
  const markers = page.locator('[data-marker-role="beneficiary"]');
  await expect(markers).toHaveCount(6);
  for (const item of await markers.all()) await expect(item).toHaveAccessibleName(/Not evaluated/);
});

test("adapter failure shows an alert and no fabricated data", async ({ page }) => {
  await page.goto("/overview?state=unavailable");
  // Next.js renders its own empty route-announcer alert; target ours by its text.
  await expect(page.getByRole("alert").filter({ hasText: "Network snapshot unavailable" })).toBeVisible();
  await expect(page.locator("[data-marker-role]")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});
