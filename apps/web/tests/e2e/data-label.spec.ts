// covers: V1-A05
import { expect, test, type Page } from "@playwright/test";
import { envelope, mockV1 } from "./v1-mocks";

// Mocked: proves which screens label the legacy fixture data, not the connected app. With no v1 network
// chosen, these routes show the legacy fictional demo, so the top bar must call it simulated; /import and
// /settings show no network data and carry no such label (lead decision 2026-11-09).
const LEGACY_DATA = ["/overview", "/data", "/data/pulse", "/data/inputs", "/data/inventory", "/data/operations", "/recommendations", "/scenarios"];
const NO_NETWORK_DATA = ["/import", "/settings"];

const pill = (page: Page, text: string) => page.getByRole("banner").getByText(text, { exact: true });

test("@V1-A05 every screen that shows the legacy fixture data labels it simulated; /import and /settings don't", async ({ page }) => {
  await mockV1(page, { "GET networks": { body: { networks: [] } } });
  for (const path of LEGACY_DATA) {
    await page.goto(path);
    await expect(pill(page, "Simulated network"), path).toBeVisible();
  }
  for (const path of NO_NETWORK_DATA) {
    await page.goto(path);
    // The empty list has settled (the switcher says so) before the pill's absence counts.
    await expect(page.getByText("No network yet.", { exact: false }).first(), path).toBeVisible();
    await expect(page.getByRole("banner"), path).not.toContainText("Simulated network");
  }
});

test("@V1-A05 a network list that fails to load says so, and the legacy screens still say simulated", async ({ page }) => {
  await mockV1(page, { "GET networks": { status: 500, body: envelope("INTERNAL_ERROR") } });
  await page.goto("/overview");
  await expect(pill(page, "Network list unavailable")).toBeVisible();
  await expect(pill(page, "Simulated network")).toBeVisible();
  for (const path of NO_NETWORK_DATA) {
    await page.goto(path);
    await expect(pill(page, "Network list unavailable"), path).toBeVisible();
    await expect(page.getByRole("banner"), path).not.toContainText("Simulated network");
  }
});
