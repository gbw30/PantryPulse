// covers: V1-A16, V1-A20
import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";
import { example, mockV1, type Schemas } from "./v1-mocks";

// Mocked against packages/contracts/examples/v1 (DecisionActions, SavedComparisonV3, NetworkList):
// proves UI behavior, not the connected app. The example has one action; a second, inferred action is
// cloned from it. The export CSV is the server's (W1-S07 columns); here it is assembled from the same
// examples so the test can check that the page saves exactly what the server returned.

const saved = example("SavedComparisonV3");
const network = example("NetworkList").networks.find((n) => n.id === saved.network_id)!;
const METHOD = "CLASSICAL_GP";
const NOTE = "simulated plan; no stock was reserved or moved";

function decisions(): Schemas["DecisionActions"] {
  const d = example("DecisionActions");
  const [first] = d.actions;
  d.actions.push({ ...first, id: "T-2", explanation_kind: "inferred",
    action_text: "Move 10 cases of Bottled water from Hub North to Pantry 7, ship on Nov 6, arrives Nov 7.",
    why_text: "Pantry 7 is likely short on Nov 9.", effect: { ...first.effect, receiver_unmet_delta: -10 } });
  return d;
}

function csv(ids: string[]) {
  const cell = (v: string) => `"${v.replaceAll('"', '""')}"`;
  const header = ["scenario_id", "scenario_hash", "method", "network_mode", "action_id", "action", "why", "note"].join(",");
  const rows = decisions().actions.filter((a) => ids.includes(a.id)).map((a) =>
    [saved.scenario_id, saved.result.scenario_hash, METHOD, saved.result.mode, a.id, a.action_text, a.why_text, NOTE].map(cell).join(","));
  return [header, ...rows].join("\n") + "\n";
}

async function open(page: Page, net: Schemas["Network"] = network) {
  const base = `networks/${network.id}/comparisons/${saved.id}`;
  const calls = await mockV1(page, {
    "GET networks": { body: { networks: [net] } },
    [`GET networks/${network.id}`]: { body: net },
    [`GET ${base}`]: { body: saved },
    [`GET ${base}/methods/${METHOD}/actions`]: { body: decisions() },
    [`POST ${base}/methods/${METHOD}/export`]: (call) => ({ body: csv(JSON.parse(call.body!).action_ids), contentType: "text/csv" }),
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`/decisions?comparison_id=${saved.id}&method=${METHOD}`);
  const section = page.getByRole("region", { name: `Suggested actions · ${network.name}` });
  await expect(section.getByRole("article")).toHaveCount(2);
  return { calls, section };
}

test('@V1-A16 select actions, export CSV download contains scenario hash and "simulated plan; no stock was reserved or moved"', async ({ page }) => {
  const { calls, section } = await open(page);
  await expect(section).toContainText("effect of this action given the rest of the plan; effects don't add up across actions");
  const exportButton = section.getByRole("button", { name: /Export CSV/ });
  await expect(exportButton).toBeDisabled();
  await section.getByRole("article", { name: decisions().actions[0].action_text }).getByRole("checkbox", { name: "Include in export" }).check();
  await expect(exportButton).toHaveText("Export CSV (1 action)");
  const [download] = await Promise.all([page.waitForEvent("download"), exportButton.click()]);
  expect(download.suggestedFilename()).toBe(`pantrypulse-plan-${saved.id.slice(0, 8)}-${METHOD}.csv`);
  const text = readFileSync((await download.path())!, "utf8");
  expect(text).toBe(csv(["T-1"]));
  expect(text).toContain(saved.result.scenario_hash);
  expect(text).toContain(NOTE);
  expect(calls.filter((c) => c.method === "POST").map((c) => JSON.parse(c.body!))).toEqual([{ action_ids: ["T-1"] }]);
});

test("@V1-A16 print page shows the same rows", async ({ page }) => {
  // The same network marked as a sample: the printed plan must carry the sample label too.
  const { section } = await open(page, { ...network, is_sample: true });
  await section.getByRole("button", { name: "Select all" }).click();
  await section.getByRole("link", { name: "Print page (2 actions)" }).click();
  await expect(page).toHaveURL(/\/decisions\/print\?/);
  const table = page.getByRole("table", { name: "Selected actions" });
  const rows = table.locator("tbody tr");
  await expect(rows).toHaveCount(2);
  for (const [i, a] of decisions().actions.entries()) {
    await expect(rows.nth(i)).toContainText(a.action_text);
    await expect(rows.nth(i)).toContainText(a.why_text);
  }
  await expect(page.getByText(`Scenario ${saved.scenario_id} · hash ${saved.result.scenario_hash}`)).toBeVisible();
  await expect(page.getByText(NOTE)).toBeVisible();
  await expect(page.getByText("effect of this action given the rest of the plan; effects don't add up across actions")).toBeVisible();
  await expect(page.getByText("Sample data — fictional")).toBeVisible();
});

test("@V1-A16 a method without a verified plan shows no actions and no export", async ({ page }) => {
  const base = `networks/${network.id}/comparisons/${saved.id}`;
  const egp = saved.result.methods.find((m) => m.method === "EGP_PI_INSPIRED")!;
  expect(egp.verified).toBe(false);
  await mockV1(page, {
    "GET networks": { body: { networks: [network] } },
    [`GET ${base}`]: { body: saved },
    [`GET ${base}/methods/EGP_PI_INSPIRED/actions`]: { body: { ...decisions(), method: "EGP_PI_INSPIRED" } },
  });
  await page.goto(`/decisions?comparison_id=${saved.id}&method=EGP_PI_INSPIRED`);
  const section = page.getByRole("region", { name: `Suggested actions · ${network.name}` });
  await expect(section).toContainText("EGP-PI-inspired has no verified plan in this comparison, so there are no suggested actions.");
  await expect(section).toContainText(egp.failure_reason!);
  await expect(section.getByRole("article")).toHaveCount(0);
  await expect(section.getByRole("button", { name: /Export CSV/ })).toHaveCount(0);
});

test("@V1-A16 ids that are not UUIDs are never sent to the API", async ({ page }) => {
  const calls = await mockV1(page, { "GET networks": { body: { networks: [network] } } });
  await page.goto(`/decisions?comparison_id=..%2F..%2Fsettings&method=${METHOD}`);
  await expect(page.getByText("Open suggested actions from a verified method result in Scenario Lab.")).toBeVisible();
  await page.goto(`/decisions/print?network_id=..&comparison_id=${saved.id}&method=${METHOD}&actions=T-1`);
  await expect(page.getByText("Open the print page from Decisions after selecting actions.")).toBeVisible();
  expect(calls.filter((c) => c.path.includes("comparisons"))).toEqual([]);
});

for (const [width, height] of [[1440, 900], [1280, 720], [390, 844]] as const) {
  test(`@V1-A20 decisions keyboard + axe + reduced motion at ${width}x${height}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height });
    const { section } = await open(page);
    expect(await page.evaluate(() => matchMedia("(prefers-reduced-motion: reduce)").matches)).toBe(true);
    await expectNoSeriousA11yViolations(page, testInfo, `decisions ${width}`);
    // Keyboard: Space toggles an action's checkbox, and the export button becomes reachable and enabled.
    const box = section.getByRole("checkbox", { name: "Include in export" }).first();
    await box.focus();
    await page.keyboard.press("Space");
    await expect(box).toBeChecked();
    await expect(section.getByRole("button", { name: "Export CSV (1 action)" })).toBeEnabled();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
