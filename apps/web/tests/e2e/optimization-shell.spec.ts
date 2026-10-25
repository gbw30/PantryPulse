import { expect, test } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";

// No backend is needed: the workspace shows its sign-in / connection error state inside the shared shell.
// The only expected failures are the API proxy's 5xx responses for the planning catalogs.
for (const [width, height] of [[1440, 900], [390, 844]]) {
  test(`optimization workspace renders in the shared shell at ${width}x${height}`, async ({ page }, testInfo) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    const unexpected: string[] = [];
    page.on("response", (response) => {
      if (response.status() >= 400 && !new URL(response.url()).pathname.startsWith("/api/v1/")) unexpected.push(`${response.status()} ${response.url()}`);
    });
    await page.setViewportSize({ width, height });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/optimization");

    await expect(page.getByRole("heading", { level: 1, name: "Optimization workspace" })).toBeVisible();
    await expect(page.getByRole("banner")).toBeVisible();
    await expect(page.getByRole("banner").getByText("Simulated network", { exact: true })).toBeVisible();
    await expect(page.getByRole("main")).toHaveCount(1);
    await expect(page.getByRole("heading", { name: "Presenter sign in" })).toBeVisible();

    // The sidebar marks the workspace link as the current page (desktop sidebar or the mobile drawer).
    if (width < 768) await page.getByRole("button", { name: "Open navigation" }).click();
    const workspaceLink = page.getByRole("navigation", { name: "Workspaces" }).getByRole("link", { name: "Optimization workspace" });
    await expect(workspaceLink).toBeVisible();
    await expect(workspaceLink).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Overview" })).not.toHaveAttribute("aria-current", "page");
    if (width < 768) await page.keyboard.press("Escape");

    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expectNoSeriousA11yViolations(page, testInfo, `optimization shell ${width}x${height}`);
    await page.screenshot({ path: testInfo.outputPath(`optimization-after-${width}.png`), fullPage: true });
    expect(pageErrors).toEqual([]);
    expect(unexpected).toEqual([]);
  });
}
