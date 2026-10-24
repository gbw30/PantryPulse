import { expect, test } from "@playwright/test";

test("scaffold clearly states research implementation is pending", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Research-inspired resource allocation" })).toBeVisible();
  await expect(page.getByText("Allocation engines are not implemented yet.", { exact: false })).toBeVisible();
  await expect(page.getByRole("link", { name: /Rampazo/ })).toHaveAttribute("href", "https://doi.org/10.1111/itor.70252");
});

