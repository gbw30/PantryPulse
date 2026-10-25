import { expect, test } from "@playwright/test";

test("root opens the Network Atlas, links the connected workspace and states simulation boundaries", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/overview$/);
  await expect(page.locator("body")).toHaveCSS("font-family", /IBM Plex Sans/);
  await expect(page.getByRole("heading", { level: 1, name: "Network Atlas" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Workspaces" }).getByRole("link", { name: "Optimization workspace" })).toHaveAttribute("href", "/optimization");
  await expect(page.getByText("this map shows a static fixture, not a saved plan", { exact: false })).toBeVisible();
  await expect(page.getByRole("link", { name: "optimization workspace", exact: true })).toHaveAttribute("href", "/optimization");
  await expect(page.getByRole("link", { name: /Rampazo/ })).toHaveAttribute("href", "https://doi.org/10.1111/itor.70252");
});
