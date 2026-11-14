// covers: V1-A05
import { expect, test, type Page } from "@playwright/test";
import { envelope, example, mockV1 } from "./v1-mocks";

// Mocked: proves which screens label the legacy fixture data, not the connected app. Any screen that renders
// the legacy fictional demo says "Simulated network", whatever network is chosen; /import and /settings show
// no network data and never do (lead decisions 2026-11-09, and L1 of the #129 review).
/** Render the legacy demo whatever network is chosen: they never read the network. */
const ALWAYS_LEGACY = ["/data/pulse", "/data/inputs", "/data/inventory", "/data/operations", "/recommendations"];
/** Render the legacy demo only while no v1 network is chosen; a chosen network replaces it. */
const LEGACY_WITHOUT_NETWORK = ["/overview", "/scenarios"];
const NO_NETWORK_DATA = ["/import", "/settings"];
/** Render the legacy demo beside the chosen network's forecast trust (W4-03 #1): the legacy block labels itself. */
const LEGACY_BESIDE_NETWORK = ["/data"];

const banner = (page: Page) => page.getByRole("banner");
const pill = (page: Page, text: string) => banner(page).getByText(text, { exact: true });
const imported = example("Network"); // a real import: is_sample false

test("@V1-A05 with no v1 network, every screen that renders the legacy demo says simulated; /import and /settings don't", async ({ page }) => {
  await mockV1(page, { "GET networks": { body: { networks: [] } } });
  for (const path of [...ALWAYS_LEGACY, ...LEGACY_BESIDE_NETWORK, ...LEGACY_WITHOUT_NETWORK]) {
    await page.goto(path);
    await expect(pill(page, "Simulated network"), path).toBeVisible();
  }
  for (const path of NO_NETWORK_DATA) {
    await page.goto(path);
    // The empty list has settled (the switcher says so) before the pill's absence counts.
    await expect(page.getByText("No network yet.").first(), path).toBeVisible();
    await expect(banner(page), path).not.toContainText("Simulated network");
  }
});

test("@V1-A05 with a real network chosen, the screens that still render the legacy demo say simulated; the others don't", async ({ page }) => {
  await mockV1(page, { "GET networks": { body: { networks: [imported] } } });
  for (const path of ALWAYS_LEGACY) {
    await page.goto(path);
    await expect(pill(page, "Simulated network"), path).toBeVisible();
  }
  for (const path of [...LEGACY_WITHOUT_NETWORK, ...NO_NETWORK_DATA]) {
    await page.goto(path);
    // The network is chosen (the switcher shows it) before the pill's absence counts.
    await expect(page.getByRole("combobox", { name: "Network", exact: true }).first(), path).toContainText(imported.name);
    await expect(banner(page), path).not.toContainText(/Simulated network|Sample data/);
  }
});

test("@V1-A05 a network list that fails to load says so on every screen, and the legacy screens still say simulated", async ({ page }) => {
  await mockV1(page, { "GET networks": { status: 500, body: envelope("INTERNAL_ERROR") } });
  for (const path of [...ALWAYS_LEGACY, ...LEGACY_BESIDE_NETWORK, ...LEGACY_WITHOUT_NETWORK]) {
    await page.goto(path);
    await expect(pill(page, "Network list unavailable"), path).toBeVisible();
    await expect(pill(page, "Simulated network"), path).toBeVisible();
  }
  for (const path of NO_NETWORK_DATA) {
    await page.goto(path);
    await expect(pill(page, "Network list unavailable"), path).toBeVisible();
    await expect(banner(page), path).not.toContainText("Simulated network");
  }
});

// W5-UI02.1: with a v1 network chosen, /data shows only that network's forecast trust and no legacy block, so the
// top bar labels the chosen network (sample data, or nothing for a real import).
const LEGACY_FIXTURE = { "GET dashboard/summary": { status: 403, body: envelope("FORBIDDEN") }, "GET forecast-catalog": { status: 403, body: envelope("FORBIDDEN") } };
for (const [kind, network, label] of [["real import", imported, null], ["sample network", { ...imported, is_sample: true }, "Sample data — fictional"]] as const) {
  test(`@V1-A05 /data with a ${kind} chosen labels that network in the top bar and shows no legacy block`, async ({ page }) => {
    await mockV1(page, { "GET networks": { body: { networks: [network] } }, ...LEGACY_FIXTURE });
    await page.goto("/data");
    await expect(page.getByRole("combobox", { name: "Network", exact: true }).first()).toContainText(network.name);
    await expect(page.locator("[data-explorer-source]")).toHaveCount(0);
    if (label) await expect(pill(page, label)).toBeVisible();
    await expect(banner(page)).not.toContainText(label ? "Simulated network" : /Simulated network|Sample data/);
  });
}
