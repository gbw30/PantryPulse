import { expect, test } from "@playwright/test";

test("root redirects to the Network Atlas, which states research implementation is pending", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/overview$/);
  await expect(page.locator("body")).toHaveCSS("font-family", /IBM Plex Sans/);
  await expect(page.getByRole("heading", { level: 1, name: "Network Atlas" })).toBeVisible();
  await expect(page.getByText("Allocation engines are not implemented yet.", { exact: false })).toBeVisible();
  await expect(page.getByRole("link", { name: /Rampazo/ })).toHaveAttribute("href", "https://doi.org/10.1111/itor.70252");
});
