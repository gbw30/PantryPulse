import { expect, test } from "@playwright/test";
import { example, mockV1, publishedRun } from "./v1-mocks";

const ranking = example("DangerRanking");
const network = example("NetworkList").networks.find((n) => n.id === ranking.network_id)!;

test("root opens the Network Atlas for the chosen network and links methodology", async ({ page }) => {
  await mockV1(page, {
    "GET networks": { body: { networks: [network] } },
    ...publishedRun(network, ranking.forecast_run_id),
    [`GET networks/${network.id}/danger`]: { body: ranking },
    [`GET networks/${network.id}/locations`]: { body: example("LocationList") },
  });
  await page.goto("/");
  await expect(page).toHaveURL(/\/overview$/);
  await expect(page.locator("body")).toHaveCSS("font-family", /IBM Plex Sans/);
  const title = page.getByRole("heading", { level: 1, name: "Network Atlas" });
  await expect(title).toBeVisible();
  // W5A-01: page titles are set in the serif; everything else stays in the sans.
  await expect(title).toHaveCSS("font-family", /IBM Plex Serif/);
  await expect(title).toHaveCSS("font-weight", "500");
  await expect(page.getByRole("region", { name: `Danger ranking · ${network.name}` })).toBeVisible();
  // The Workspaces nav was retired when the Scenario Lab replaced /optimization (PP-55 decision 1).
  await expect(page.getByRole("navigation", { name: "Reference" }).getByRole("link", { name: "Methodology & audit" })).toHaveAttribute("href", "/methodology");
});
