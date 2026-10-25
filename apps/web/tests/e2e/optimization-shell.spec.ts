import { expect, test } from "@playwright/test";

// /optimization was replaced by the Scenario Lab (PP-55 decision 1); the old URL redirects and
// carries durable-job and comparison parameters over so saved links keep working.
test("/optimization redirects to /scenarios and keeps query parameters", async ({ page }) => {
  await page.route("**/api/v1/**", (route) => route.fulfill({ status: 401, json: { error: { code: "PRESENTER_REQUIRED", message: "presenter required", details: {} }, request_id: "00000000-0000-4000-8000-000000000000" } }));
  await page.goto("/optimization?job=11111111-1111-4111-8111-111111111111&kind=comparisons");
  await expect(page).toHaveURL(/\/scenarios\?job=11111111-1111-4111-8111-111111111111&kind=comparisons$/);
  await expect(page.getByRole("heading", { level: 1, name: "Scenario Lab" })).toBeVisible();
});
