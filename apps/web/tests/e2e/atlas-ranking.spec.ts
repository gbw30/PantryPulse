// covers: V1-A13, V1-A20
import { expect, test, type Page } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";
import { envelope, example, mockV1, publishedRun } from "./v1-mocks";

// Mocked against packages/contracts/examples/v1 (DangerRanking, NetworkList, LocationList, LocationProjection):
// proves UI behavior, not the connected app. The forecast run is the network's newest published run (W4-02).
// The projection route is a 501 stub until W3-F05; only P-12 has an example projection.
const ranking = example("DangerRanking");
const network = example("NetworkList").networks.find((n) => n.id === ranking.network_id)!;
const names = Object.fromEntries(example("LocationList").locations.map((l) => [l.location_id, `${l.name} (${l.location_id})`]));

async function open(page: Page, served = ranking) {
  const calls = await mockV1(page, {
    "GET networks": { body: { networks: [network] } },
    ...publishedRun(network, ranking.forecast_run_id),
    [`GET networks/${network.id}/danger`]: (call) => call.query.get("forecast_run_id") === ranking.forecast_run_id
      ? { body: served } : { status: 404, body: { error: { code: "NOT_FOUND", message: "not found", details: {} } } },
    [`GET networks/${network.id}/locations`]: { body: example("LocationList") },
    [`GET networks/${network.id}/projection`]: (call) =>
      call.query.get("forecast_run_id") === ranking.forecast_run_id && call.query.get("location_id") === "P-12"
        ? { body: example("LocationProjection") } : { status: 404, body: envelope("NOT_FOUND") },
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/overview");
  return calls;
}

test("@V1-A13 table alternative lists the same ranking", async ({ page }) => {
  await open(page);
  const section = page.getByRole("region", { name: `Danger ranking · ${network.name}` });
  const list = section.getByRole("list", { name: "Locations by danger" }).getByRole("listitem");
  await expect(list).toHaveCount(ranking.rows.length);
  const listed = await list.evaluateAll((items) => items.map((li) => li.getAttribute("aria-label")!.split(",")[0]));
  await section.getByRole("button", { name: "Table" }).click();
  await expect(section.getByRole("button", { name: "Table" })).toHaveAttribute("aria-pressed", "true");
  const rows = section.getByRole("table", { name: /Danger ranking/ }).locator("tbody tr");
  await expect(rows).toHaveCount(ranking.rows.length);
  expect(await rows.evaluateAll((trs) => trs.map((tr) => tr.querySelector("td")!.textContent))).toEqual(listed);
  expect(listed).toEqual(ranking.rows.map((r) => names[r.location_id]));
});

test("@V1-A13 selecting a row opens the site inspector", async ({ page }) => {
  const calls = await open(page);
  const section = page.getByRole("region", { name: `Danger ranking · ${network.name}` });
  await section.getByRole("button", { name: names["P-12"], exact: true }).click();
  const inspector = page.getByRole("region", { name: "Site inspector · Archer Road Pantry" });
  await expect(inspector.getByRole("heading", { name: "Archer Road Pantry" })).toBeFocused();
  await expect(inspector.getByRole("table", { name: "WATER-24 in cases" })).toBeVisible();
  await expect(inspector.getByRole("table", { name: "RICE-5 in bags" })).toBeVisible();
  await expect(inspector.getByRole("table", { name: "WATER-24 in cases" }).getByRole("row", { name: /Nov 10/ })).toContainText("unknown");
  await expect(inspector).not.toContainText(/total/i);
  // The dev server's StrictMode mounts effects twice, so count only what was asked for, not how often.
  const asked = calls.filter((c) => c.path.endsWith("/projection")).map((c) => Object.fromEntries(c.query));
  expect(asked.length).toBeGreaterThan(0);
  for (const query of asked) expect(query).toEqual({ forecast_run_id: ranking.forecast_run_id, location_id: "P-12" });
  await inspector.getByRole("button", { name: "Close inspector" }).click();
  await expect(inspector).toHaveCount(0);
  await expect(section.getByRole("button", { name: names["P-12"], exact: true })).toBeFocused();
});

test("@V1-A13 locations are placed by their coordinates, and one without coordinates is listed, not guessed", async ({ page }) => {
  await open(page);
  const section = page.getByRole("region", { name: `Danger ranking · ${network.name}` });
  const map = section.getByRole("group", { name: `Map of ${network.name}` });
  await expect(map.getByRole("button")).toHaveCount(2);
  const hub = (await map.getByRole("button", { name: `${names["H-1"]}, not ranked` }).boundingBox())!;
  const east = (await map.getByRole("button", { name: `${names["P-07"]}, Low danger` }).boundingBox())!;
  expect(hub.x).toBeLessThan(east.x);
  expect(hub.y).toBeGreaterThan(east.y);
  await expect(section.getByRole("list", { name: "Not on the map (no coordinates)" })).toHaveText(names["P-12"]);
  await map.getByRole("button", { name: `${names["P-07"]}, Low danger` }).click();
  const inspector = page.getByRole("region", { name: "Site inspector · Eastside Pantry" });
  await expect(inspector.getByRole("alert")).toHaveText(/Projection unavailable \(not found\)\./);
});

for (const [width, height] of [[1440, 900], [1280, 720], [390, 844]] as const) {
  test(`@V1-A20 axe clean at ${width}x${height}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height });
    await open(page);
    const section = page.getByRole("region", { name: `Danger ranking · ${network.name}` });
    await expect(section.getByRole("list", { name: "Locations by danger" })).toBeVisible();
    await expectNoSeriousA11yViolations(page, testInfo, `atlas ranking list ${width}`);
    await section.getByRole("button", { name: names["P-12"], exact: true }).click();
    await expect(page.getByRole("table", { name: "WATER-24 in cases" })).toBeVisible();
    await expectNoSeriousA11yViolations(page, testInfo, `atlas inspector ${width}`);
    await section.getByRole("button", { name: "Table" }).click();
    await expectNoSeriousA11yViolations(page, testInfo, `atlas ranking table ${width}`);
    // Keyboard: the view toggle is reachable and operable.
    await section.getByRole("button", { name: "List" }).focus();
    await page.keyboard.press("Enter");
    await expect(section.getByRole("button", { name: "List" })).toHaveAttribute("aria-pressed", "true");
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

// W5-UI02.5 (W4-03 ux-critic #5): the Overview's first view. Five ranked rows, so #3 is a real third row.
function fiveRows(mode: "PANTRY" | "RETAIL" = "PANTRY") {
  const served = example("DangerRanking");
  served.mode = mode;
  const low = served.rows[1];
  served.rows.push(...[3, 4, 5].map((rank) => ({ ...low, location_id: `P-9${rank}`, rank })));
  // Retail from sales history is the longest line: the reason and the sales basis (W5-UI04) on every row.
  if (mode === "RETAIL") served.rows = served.rows.map((row) => ({ ...row, basis: "sales" as const }));
  return served;
}

for (const [width, height, mode] of [[1440, 900, "PANTRY"], [1280, 720, "PANTRY"], [1440, 900, "RETAIL"], [1280, 720, "RETAIL"]] as const) {
  test(`@V1-A20 ranks #1–#3 show without scrolling at ${width}x${height} (${mode})`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await open(page, fiveRows(mode));
    const items = page.getByRole("list", { name: "Locations by danger" }).getByRole("listitem");
    await expect(items).toHaveCount(5);
    expect(await page.evaluate(() => scrollY)).toBe(0);
    for (const i of [0, 1, 2]) {
      const box = (await items.nth(i).boundingBox())!;
      expect(box.y + box.height, `rank #${i + 1} ends inside the first view`).toBeLessThanOrEqual(height);
    }
  });
}

test("@V1-A20 Run forecast sits outside the ranking, labeled for presenters", async ({ page }) => {
  await open(page);
  const section = page.getByRole("region", { name: `Danger ranking · ${network.name}` });
  await expect(section.getByRole("list", { name: "Locations by danger" })).toBeVisible();
  await expect(section.getByRole("button", { name: "Run forecast" })).toHaveCount(0);
  const controls = page.getByRole("group", { name: "Presenter controls" });
  await expect(controls).toContainText("Presenter");
  await expect(controls.getByRole("button", { name: "Run forecast" })).toBeVisible();
});

test("@V1-A20 a focused map marker shows its site name", async ({ page }) => {
  await open(page);
  const map = page.getByRole("group", { name: `Map of ${network.name}` });
  const marker = map.getByRole("button", { name: `${names["P-07"]}, Low danger` });
  const name = map.getByText(names["P-07"], { exact: true });
  await expect(name).toBeHidden();
  await marker.focus();
  await expect(name).toBeVisible();
});

test("@V1-A20 Escape closes the live inspector and returns focus to its opener", async ({ page }) => {
  await open(page);
  const section = page.getByRole("region", { name: `Danger ranking · ${network.name}` });
  const opener = section.getByRole("button", { name: names["P-12"], exact: true });
  await opener.click();
  const inspector = page.getByRole("region", { name: "Site inspector · Archer Road Pantry" });
  await expect(inspector.getByRole("table", { name: "WATER-24 in cases" })).toBeVisible();
  await inspector.getByRole("table", { name: "WATER-24 in cases" }).click(); // focus elsewhere in the inspector
  await page.keyboard.press("Escape");
  await expect(inspector).toHaveCount(0);
  await expect(opener).toBeFocused();

  const marker = page.getByRole("group", { name: `Map of ${network.name}` }).getByRole("button", { name: `${names["P-07"]}, Low danger` });
  await marker.click();
  await expect(page.getByRole("region", { name: "Site inspector · Eastside Pantry" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("region", { name: "Site inspector · Eastside Pantry" })).toHaveCount(0);
  await expect(marker).toBeFocused();
});
