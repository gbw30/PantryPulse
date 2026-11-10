// covers: V1-A04
import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { signInThroughForm } from "./sign-in";
import { envelope } from "./v1-mocks";

// H1 (review of #129): a failed form sign-in must leave the presenter password in no file Playwright writes
// for the failure; error-context.md's accessibility snapshot records input values. Connected runs record no
// trace (CR-w3-web-2, tests/playwright-config.test.mjs), so these run without one and check everything else.
test.use({ trace: "off" });
test.describe.configure({ mode: "serial" });

const CANARY = "Canary-Pw-7Q2x";
const failedOutputs: string[] = [];

async function failSignIn(page: Page, login: "reject" | "hang" | "late") {
  await page.route("**/api/v1/**", (route) => {
    if (!route.request().url().includes("/presenter/login")) return route.fulfill({ status: 401, json: envelope("PRESENTER_REQUIRED") });
    if (login === "reject") return route.fulfill({ status: 429, json: envelope("RATE_LIMITED") });
    // "hang" and "late": never answered, so only a timeout (the form's or the helper's) ends the sign-in.
  });
  await page.goto("/import");
  // "late" (N1): the sign-in starts with less of the test's 20 s left than the helper waits or the form allows.
  if (login === "late") await page.waitForTimeout(12_000);
  const saved = process.env.PP_E2E_PASSWORD;
  process.env.PP_E2E_PASSWORD = CANARY;
  try {
    await signInThroughForm(page);
  } finally {
    if (saved === undefined) delete process.env.PP_E2E_PASSWORD; else process.env.PP_E2E_PASSWORD = saved;
  }
}

for (const [login, how] of [["reject", "rejected (429)"], ["hang", "never answered"], ["late", "late, never answered"]] as const) {
  test(`@V1-A04 canary: a ${how} form sign-in fails (expected)`, async ({ page }, testInfo) => {
    test.fail(); // The sign-in must fail; the last test reads what Playwright wrote for this failure.
    test.setTimeout(20_000);
    failedOutputs.push(testInfo.outputDir);
    await failSignIn(page, login);
  });
}

test("@V1-A04 canary: no file written for those failed sign-ins contains the password", () => {
  expect(failedOutputs).toHaveLength(3);
  for (const dir of failedOutputs) {
    const files = fs.readdirSync(dir, { recursive: true, withFileTypes: true }).filter((e) => e.isFile()).map((e) => path.join(e.parentPath, e.name));
    // Not vacuous: the failure's error-context.md (with its page snapshot) is there to read.
    expect(files.map((f) => path.basename(f)), dir).toContain("error-context.md");
    for (const file of files) expect(fs.readFileSync(file).includes(CANARY), `${file} contains the password`).toBe(false);
  }
});
