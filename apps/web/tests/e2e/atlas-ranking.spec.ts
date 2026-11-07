// covers: V1-A13, V1-A20
import { expect, test, type Page } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";
import { example, mockV1 } from "./v1-mocks";

// Mocked against packages/contracts/examples/v1 (DangerRanking, NetworkList): proves UI behavior, not
// the connected app. The forecast run comes from the URL until a run can be discovered (CR-w1-web-2).
const ranking = example("DangerRanking");
const network = example("NetworkList").networks.find((n) => n.id === ranking.network_id)!;

async function open(page: Page) {
  const calls = await mockV1(page, {
    "GET networks": { body: { networks: [network] } },
    [`GET networks/${network.id}/danger`]: (call) => call.query.get("forecast_run_id") === ranking.forecast_run_id
      ? { body: ranking } : { status: 404, body: { error: { code: "NOT_FOUND", message: "not found", details: {} } } },
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`/overview?forecast_run_id=${ranking.forecast_run_id}`);
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
  expect(listed).toEqual(ranking.rows.map((r) => r.location_id));
});

for (const [width, height] of [[1440, 900], [1280, 720], [390, 844]] as const) {
  test(`@V1-A20 axe clean at ${width}x${height}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height });
    await open(page);
    const section = page.getByRole("region", { name: `Danger ranking · ${network.name}` });
    await expect(section.getByRole("list", { name: "Locations by danger" })).toBeVisible();
    await expectNoSeriousA11yViolations(page, testInfo, `atlas ranking list ${width}`);
    await section.getByRole("button", { name: "Table" }).click();
    await expectNoSeriousA11yViolations(page, testInfo, `atlas ranking table ${width}`);
    // Keyboard: the view toggle is reachable and operable.
    await section.getByRole("button", { name: "List" }).focus();
    await page.keyboard.press("Enter");
    await expect(section.getByRole("button", { name: "List" })).toHaveAttribute("aria-pressed", "true");
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
