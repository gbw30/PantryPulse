// covers: V1-A05, V1-A14, V1-A15
import { expect, test, type Page } from "@playwright/test";
import { example, mockV1 } from "./v1-mocks";

// Mocked against packages/contracts/examples/v1 (NetworkList): proves UI behavior, not the connected app.
const list = example("NetworkList");
const pantry = list.networks.find((n) => n.mode === "PANTRY" && !n.is_sample)!;
const sample = list.networks.find((n) => n.is_sample)!;

async function chooseNetwork(page: Page, name: string) {
  await page.getByRole("region", { name: "Current network" }).getByRole("combobox").click();
  await page.getByRole("option", { name: new RegExp(name) }).click();
}

test.beforeEach(async ({ page }) => {
  await mockV1(page, { "GET networks": { body: list } });
  await page.emulateMedia({ reducedMotion: "reduce" });
});

test(`@V1-A05 sample network shows "Sample data — fictional"`, async ({ page }) => {
  await page.goto("/overview");
  const switcher = page.getByRole("region", { name: "Current network" });
  await chooseNetwork(page, pantry.name);
  await expect(switcher.getByText("Sample data — fictional")).toHaveCount(0);
  await chooseNetwork(page, sample.name);
  await expect(switcher.getByText("Sample data — fictional")).toBeVisible();
  // The switcher is in the header's context bar, so its badge is the header's one sample label (W5A-02).
  await expect(page.getByRole("banner").getByText("Sample data — fictional")).toHaveCount(1);
});

test("@V1-A14 receipts, posting, adjustments and lot declarations are not in v1 navigation", async ({ page }) => {
  await page.goto("/data");
  const explorerTabs = page.getByRole("navigation", { name: "Data Explorer views" });
  await expect(explorerTabs.getByRole("link", { name: "Dashboard" })).toBeVisible();
  for (const nav of [explorerTabs, page.getByRole("navigation", { name: "Primary" })]) {
    for (const href of ["/data/operations", "/data/inventory", "/data/inputs"]) {
      await expect(nav.locator(`a[href^="${href}"]`)).toHaveCount(0);
    }
    await expect(nav.getByText(/receipt|posting|adjustment|lot declaration|Operations Board|Inventory & Lots|Data input/i)).toHaveCount(0);
  }
});

test("switching network updates vocabulary", async ({ page }) => {
  await page.goto("/overview");
  const switcher = page.getByRole("region", { name: "Current network" });
  await chooseNetwork(page, pantry.name);
  await expect(switcher).toContainText("Pantry mode · hubs and pantries");
  await chooseNetwork(page, sample.name);
  await expect(switcher).toContainText("Retail mode · distribution centers and stores");
  await expect(switcher).not.toContainText("Pantry mode");
  // The choice survives a reload (per-browser convenience only).
  await page.reload();
  await expect(page.getByRole("region", { name: "Current network" }).getByRole("combobox")).toContainText(sample.name);
});

// W5-UI05 (W4-03 ux-critic notes): a long network name widened the selector over page titles. Since W5A-02 the
// selector sits in the header's context bar, so it must stay a bounded width there.
for (const [width, height] of [[1440, 900], [1280, 720]] as const) {
  test(`@V1-A20 the network selector stays a bounded width in the context bar at ${width}x${height}`, async ({ page }) => {
    const long = { ...sample, name: "Heronfield Market and Partner Stores of the Greater North Central Region — sample retail network" };
    await page.unrouteAll();
    await mockV1(page, { "GET networks": { body: { networks: [long] } } });
    await page.setViewportSize({ width, height });
    await page.goto("/settings");
    // Truncated on screen, so the full name lives in the accessible name (label + chosen network).
    const trigger = page.getByRole("banner").getByRole("region", { name: "Current network" }).getByRole("combobox");
    await expect(trigger).toHaveAccessibleName(`Network ${long.name} (sample)`);
    const box = (await trigger.boundingBox())!;
    expect(box.width, "the trigger truncates a long name").toBeLessThanOrEqual(320);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth), "the long name never widens the page").toBeLessThanOrEqual(width);
    const title = (await page.getByRole("heading", { level: 1 }).boundingBox())!;
    expect(box.x + box.width <= title.x || box.y + box.height <= title.y || title.y + title.height <= box.y, "the trigger never covers the page title").toBe(true);
  });
}

// W5-UI05 (orchestrator, from w5-screens' connected captures): at 390 the top bar's right-hand group (sample
// label, snapshot date, theme toggle) refused to shrink, so every v1 screen was 481 px wide and scrolled sideways.
for (const path of ["/overview", "/data", "/scenarios", "/decisions", "/import", "/settings"]) {
  test(`@V1-A20 ${path} at 390x844 with a sample network chosen never scrolls sideways`, async ({ page }) => {
    const chosen = { ...sample, name: "Heronfield Market — sample retail network", as_of_date: "2026-11-12" };
    await page.unrouteAll();
    await mockV1(page, { "GET networks": { body: { networks: [chosen] } } });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(path);
    const banner = page.getByRole("banner");
    await expect(banner).toContainText("Sample data — fictional");
    await expect(banner).toContainText("Snapshot Nov 12, 2026");
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  });
}

// W5A-02: the menu is the header's first row at 768 px and up; below that it stays the "Open navigation" drawer.
const PRIMARY = ["Overview", "Data Explorer", "Recommendations", "Scenario Lab", "Import data"];

test("@V1-A20 at 1280x720 the menu is in the header and no sidebar is rendered", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/settings");
  await expect(page.locator("header nav[aria-label='Primary']")).toBeVisible();
  await expect(page.locator("header nav[aria-label='Reference']")).toBeVisible();
  await expect(page.locator("header [data-slot='page-actions']")).toHaveCount(1);
  await expect(page.locator("[data-slot='sidebar'], [data-sidebar='sidebar']")).toHaveCount(0);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Open navigation" })).toBeHidden();
});

test("@V1-A20 at 1280x720 the content starts at the left edge: no column is reserved for a sidebar", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/settings");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect((await page.locator("#main-content").boundingBox())!.x).toBeLessThanOrEqual(40);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(1280);
});

test("@V1-A20 the menu links are reached by Tab in order, and the current one is marked", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/import");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const header = page.getByRole("banner");
  const primary = header.getByRole("navigation", { name: "Primary" });
  const links = [...PRIMARY.map((name) => primary.getByRole("link", { name, exact: true })),
    header.getByRole("navigation", { name: "Reference" }).getByRole("link", { name: "Methodology & audit" })];
  // Skip link and brand come first; from the first menu link on, each Tab is the next link.
  for (let i = 0; i < 4 && !(await links[0].evaluate((el) => el === document.activeElement)); i++) await page.keyboard.press("Tab");
  for (const link of links) {
    await expect(link).toBeFocused();
    await page.keyboard.press("Tab");
  }
  await expect(header.locator("[aria-current='page']")).toHaveText("Import data");
  // The current item carries a 3 px underline in --pp-action (and aria-current, so color is not the only cue).
  const underline = await links[4].evaluate((el) => {
    const probe = document.body.appendChild(document.createElement("i"));
    probe.style.color = "var(--pp-action)";
    const action = getComputedStyle(probe).color;
    probe.remove();
    const style = getComputedStyle(el);
    return { width: style.borderBottomWidth, isAction: style.borderBottomColor === action };
  });
  expect(underline).toEqual({ width: "3px", isAction: true });
});

test("@V1-A20 at 390x844 Open navigation opens the drawer with the same links, and the page never scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/settings");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const drawer = page.getByRole("dialog");
  // Retry the tap until the page is hydrated.
  await expect(async () => {
    if (!(await drawer.isVisible())) await page.getByRole("button", { name: "Open navigation" }).click();
    await expect(drawer).toBeVisible({ timeout: 1000 });
  }).toPass();
  await expect(page.locator("header nav")).toHaveCount(0);
  for (const name of PRIMARY) await expect(drawer.getByRole("navigation", { name: "Primary" }).getByRole("link", { name, exact: true })).toBeVisible();
  await expect(drawer.getByRole("navigation", { name: "Reference" }).getByRole("link", { name: "Methodology & audit" })).toBeVisible();
  await expect(drawer.getByRole("link", { name: "Settings" })).toHaveAttribute("aria-current", "page");
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

// W5A-03c (connected review): at 1280x720 the context bar wrapped to a second row, mostly for a search field no page
// uses. One horizontal line through every visible item means the items sit on one row.
const oneRow = (el: Element) => {
  // An icon counts as one item: the shapes inside an SVG sit at different heights.
  const boxes = [...el.querySelectorAll("*")].filter((n) => !n.parentElement?.closest("svg") && (n.children.length === 0 || n.tagName === "svg"))
    .map((n) => n.getBoundingClientRect()).filter((r) => r.width > 1 && r.height > 1);
  return Math.max(...boxes.map((r) => r.top)) < Math.min(...boxes.map((r) => r.bottom));
};
const menuRow = (page: Page) => page.locator("header nav[aria-label='Primary'] >> xpath=..");

for (const path of ["/overview", "/scenarios", "/decisions", "/data"]) {
  test(`@V1-A20 ${path} at 1280x720: the context bar and the menu row each fit one line, with no search control`, async ({ page }) => {
    const chosen = { ...sample, as_of_date: "2026-11-12" };
    await page.unrouteAll();
    await mockV1(page, { "GET networks": { body: { networks: [chosen] } } });
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto(path);
    const bar = page.locator("[data-slot='context-bar']");
    await expect(bar.getByRole("combobox")).toContainText(chosen.name);
    await expect(bar).toContainText("Snapshot Nov 12, 2026");
    await expect.soft(bar.locator("input[type='search']"), "no page passes a search").toHaveCount(0);
    await expect.soft(bar.getByRole("button", { name: /search/i })).toHaveCount(0);
    expect.soft(await bar.evaluate(oneRow), "the context bar is one row").toBe(true);
    expect.soft(await menuRow(page).evaluate(oneRow), "the menu row is one row").toBe(true);
    // toBeVisible counts a 1 px sr-only box as visible, so the label's width is measured.
    expect.soft((await page.getByRole("banner").getByText("Presenter session", { exact: true }).boundingBox())?.width, "Presenter session is shown").toBeGreaterThan(1);
  });
}

// The visitor's label and wider sign-in button need 1400 px; below that the label stays in the accessible name only.
test("@V1-A20 a visitor's menu row fits one line at 1280x720, and shows the read-only label from 1400", async ({ page }) => {
  await page.unrouteAll();
  await mockV1(page, {}, { presenter: false });
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/overview");
  const label = page.getByRole("banner").getByText("No account · read-only demo", { exact: true });
  await expect(label).toBeAttached();
  expect(await menuRow(page).evaluate(oneRow), "the menu row is one row at 1280").toBe(true);
  await page.setViewportSize({ width: 1400, height: 900 });
  await expect.poll(async () => (await label.boundingBox())?.width ?? 0, "the read-only label is shown at 1400").toBeGreaterThan(1);
  expect(await menuRow(page).evaluate(oneRow), "the menu row is one row at 1400").toBe(true);
});

// W5A-03c, spec §4.10: green never means OK by itself, and a dot reads as "live". The sample label is a neutral badge.
test("@V1-A20 at 390x844 the sample label is a tint badge with ink text, no dot and no action colour", async ({ page }) => {
  await page.unrouteAll();
  await mockV1(page, { "GET networks": { body: { networks: [sample] } } });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/overview");
  const label = page.getByRole("banner").getByText("Sample data — fictional", { exact: true });
  await expect(label).toBeVisible();
  const look = await label.evaluate((el) => {
    const token = (name: string) => {
      const probe = document.body.appendChild(document.createElement("i"));
      probe.style.color = `var(${name})`;
      const value = getComputedStyle(probe).color;
      probe.remove();
      return value;
    };
    const style = getComputedStyle(el);
    return { children: el.children.length, tint: style.backgroundColor === token("--pp-tint"), ink: style.color === token("--pp-ink"), actionClass: /pp-action/.test(el.className) };
  });
  expect(look).toEqual({ children: 0, tint: true, ink: true, actionClass: false });
});
