import { expect, test } from "@playwright/test";

test("home links the connected workspace and states simulation boundaries", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("body")).toHaveCSS("font-family", "Arial, Helvetica, sans-serif");
  await expect(page.getByRole("heading", { name: "Research-inspired resource allocation" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open optimization workspace" })).toHaveAttribute("href", "/optimization");
  await expect(page.getByText("Results are simulations; no operational dispatch is performed.", { exact: false })).toBeVisible();
  await expect(page.getByRole("link", { name: /Rampazo/ })).toHaveAttribute("href", "https://doi.org/10.1111/itor.70252");
});

