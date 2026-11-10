import { test, type Page } from "@playwright/test";

/**
 * Sign in through the presenter form, the one way every connected spec signs in (W3 lead decision, item 3).
 * A rejected or unanswered login never reloads the page, so this waits at most WAIT_MS and then fails, and
 * it always empties the password field on the way out. However late in the test it runs, it adds that
 * time to the test's timeout just before typing the password, so the test cannot time out (and write its
 * page snapshot) while the password is typed. Playwright exposes no elapsed time to measure "time left".
 * The form also empties the field after any failed login, including one the server never answers (10 s).
 * Together they keep the password out of the page snapshot in error-context.md
 * (tests/e2e/sign-in-canary.spec.ts checks every file a failure writes). A trace would still hold it, so
 * connected runs record none (CR-w3-web-2).
 */
const WAIT_MS = 15_000; // longer than the form's own 10 s login timeout
const CLEANUP_MS = 5_000; // to empty the field after a failed wait

export async function signInThroughForm(page: Page) {
  const open = page.getByRole("button", { name: "Presenter sign in" });
  // On a phone viewport the button is in the collapsed navigation.
  if (!(await open.isVisible())) await page.getByRole("button", { name: "Open navigation" }).click();
  await open.click();
  const dialog = page.getByRole("dialog", { name: "Presenter sign in" });
  await dialog.getByLabel("Username", { exact: true }).fill(process.env.PP_E2E_USERNAME ?? "presenter");
  const info = test.info();
  if (info.timeout) info.setTimeout(info.timeout + WAIT_MS + CLEANUP_MS);
  const password = dialog.getByLabel("Password", { exact: true });
  await password.fill(process.env.PP_E2E_PASSWORD ?? "pantry-local-demo");
  try {
    await Promise.all([page.waitForEvent("load", { timeout: WAIT_MS }), dialog.getByRole("button", { name: "Sign in", exact: true }).click()]);
  } finally {
    // After a sign-in the page has reloaded and the field is gone; otherwise empty it.
    if (await password.isVisible().catch(() => false)) await password.fill("").catch(() => {});
  }
}
