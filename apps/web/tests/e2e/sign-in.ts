import type { Page } from "@playwright/test";

/**
 * Sign in through the presenter form, the one way every connected spec signs in (W3 lead decision, item 3).
 * A rejected login (429 from the login limit, a wrong password) never reloads the page, so this fails fast
 * instead of at the test timeout, and it empties the password field first: the password never reaches
 * error-context.md or the uploaded test-results.
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
  try {
    await Promise.all([page.waitForEvent("load", { timeout: 30_000 }), dialog.getByRole("button", { name: "Sign in", exact: true }).click()]);
  } catch (error) {
    await password.fill("").catch(() => {});
    throw error;
  }
}
