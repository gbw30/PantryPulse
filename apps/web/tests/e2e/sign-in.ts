import { test, type Page } from "@playwright/test";

/**
 * Sign in through the presenter form, the one way every connected spec signs in (W3 lead decision, item 3).
 * A rejected or unanswered login never reloads the page, so this waits at most half the test's timeout
 * (15 s at most) and fails before the test does, and it always empties the password field on the way out.
 * The form also empties it after any failed login. Together they keep the password out of the page
 * snapshot in error-context.md (tests/e2e/sign-in-canary.spec.ts checks every file a failure writes).
 * A trace would still hold it, so connected runs record none (CR-w3-web-2).
 */
export async function signInThroughForm(page: Page) {
  const open = page.getByRole("button", { name: "Presenter sign in" });
  // On a phone viewport the button is in the collapsed navigation.
  if (!(await open.isVisible())) await page.getByRole("button", { name: "Open navigation" }).click();
  await open.click();
  const dialog = page.getByRole("dialog", { name: "Presenter sign in" });
  await dialog.getByLabel("Username", { exact: true }).fill(process.env.PP_E2E_USERNAME ?? "presenter");
  const password = dialog.getByLabel("Password", { exact: true });
  await password.fill(process.env.PP_E2E_PASSWORD ?? "pantry-local-demo");
  const wait = Math.min(15_000, (test.info().timeout || 30_000) / 2);
  try {
    await Promise.all([page.waitForEvent("load", { timeout: wait }), dialog.getByRole("button", { name: "Sign in", exact: true }).click()]);
  } finally {
    // After a sign-in the page has reloaded and the field is gone; otherwise empty it.
    if (await password.isVisible().catch(() => false)) await password.fill("").catch(() => {});
  }
}
