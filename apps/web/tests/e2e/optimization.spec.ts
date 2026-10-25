import { expect, test } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

test.describe("persisted simulated OR journey", () => {
  test.skip(!process.env.OR_E2E_PASSWORD, "Requires the isolated OR API/database/supervisor and private test environment; not OR acceptance when skipped.");

  test("five reset-to-finish rehearsals, real disruption, saved visitor reads and responsive views", async ({ page, browser }) => {
    test.setTimeout(180_000);
    const baseURL = `http://127.0.0.1:${process.env.PLAYWRIGHT_PORT ?? "3012"}`;
    const output = path.resolve(process.cwd(), "../../artifacts/or/browser");
    mkdirSync(output, { recursive: true });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto("/optimization");
    await expect(page.getByRole("heading", { name: "Compare allocation plans" })).toBeVisible();
    await expect(page.getByRole("combobox", { name: "Transfer mode" })).toHaveValue("");
    await expect(page.getByRole("button", { name: "Compare methods", exact: true })).toBeDisabled();
    await page.getByLabel("Username", { exact: true }).fill("presenter");
    await page.getByLabel("Password", { exact: true }).fill(process.env.OR_E2E_PASSWORD!);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByText("Session active. Visitors can open saved simulated results.")).toBeVisible();
    const originRejection = await page.request.post(`${baseURL}/api/v1/demo/seed`, {
      headers: { Origin: "https://example.invalid" }, data: { fixture: "six-beneficiary-v1" },
    });
    expect(originRejection.status()).toBe(403);
    const csrfRejection = await page.request.post(`${baseURL}/api/v1/demo/seed`, {
      headers: { Origin: baseURL }, data: { fixture: "six-beneficiary-v1" },
    });
    expect(csrfRejection.status()).toBe(403);
    const evidence: { cycle: number; mode: string; multiplier: string; scenario_hash: string; job_id: string; duration_ms: number }[] = [];
    for (let cycle = 0; cycle < 5; cycle++) {
      const start = Date.now();
      await page.getByRole("button", { name: "Load simulated network", exact: true }).click();
      await expect(page.getByText(/Six fictional pantries, one hub/)).toBeVisible();
      const mode = cycle % 2 ? "HUB_AND_PANTRY" : "HUB_ONLY";
      const multiplier = cycle === 1 ? "1.5" : "1";
      await page.getByRole("combobox", { name: "Transfer mode" }).selectOption(mode);
      await page.getByRole("combobox", { name: "Allocation window" }).selectOption("3");
      await page.getByLabel("Demand multiplier", { exact: true }).fill(multiplier);
      const created = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === "/api/v1/scenarios");
      await page.getByRole("button", { name: "Freeze new scenario" }).click();
      const scenarioResponse = await created;
      expect(scenarioResponse.status()).toBe(201);
      const scenario = await scenarioResponse.json();
      await expect(page.getByText("A new immutable scenario is saved. Existing comparisons keep their original inputs.")).toBeVisible();
      const accepted = page.waitForResponse((response) => response.request().method() === "POST" && response.url().endsWith("/compare-methods"));
      await page.getByRole("button", { name: "Compare methods", exact: true }).click();
      const acceptedResponse = await accepted;
      expect(acceptedResponse.status()).toBe(202);
      const job = await acceptedResponse.json();
      await expect(page.locator(".or-method-card").getByText("OPTIMAL", { exact: true })).toHaveCount(2, { timeout: 40_000 });
      await expect(page.getByRole("heading", { name: "Service within the allocation window", exact: true })).toBeVisible();
      await expect(page.locator(".or-product")).toHaveCount(2);
      for (const table of await page.getByRole("table").all()) await expect(table.locator("tbody tr")).toHaveCount(6);
      const reviewResponse = page.waitForResponse((response) => response.request().method() === "POST" && response.url().endsWith("/review"));
      await page.getByRole("button", { name: "Mark reviewed", exact: true }).first().click();
      expect((await reviewResponse).status()).toBe(201);
      await expect(page.getByText(/Inventory was not changed/)).toBeVisible();
      evidence.push({ cycle: cycle + 1, mode, multiplier, scenario_hash: scenario.operational_hash, job_id: job.job_id, duration_ms: Date.now() - start });
      if (cycle === 0) {
        const visitor = await browser.newContext();
        const saved = await visitor.newPage();
        await saved.goto(`${baseURL}/optimization?job=${job.job_id}`);
        await expect(saved.locator(".or-method-card").getByText("OPTIMAL", { exact: true })).toHaveCount(2);
        await expect(saved.getByRole("button", { name: "Compare methods", exact: true })).toBeDisabled();
        await expect(saved.getByRole("button", { name: "Mark reviewed", exact: true })).toHaveCount(0);
        for (const viewport of [{ width: 1440, height: 900 }, { width: 1280, height: 720 }, { width: 390, height: 844 }]) {
          await saved.setViewportSize(viewport);
          await expect(saved.getByText("Simulated network", { exact: true })).toBeVisible();
          const overflow = await saved.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
          expect(overflow).toBe(false);
          await saved.screenshot({ path: path.join(output, `saved-${viewport.width}x${viewport.height}.png`), fullPage: true });
        }
        await visitor.close();
      }
      if (cycle === 1) expect(scenario.operational_hash).not.toBe(evidence[0].scenario_hash);
      const resetResponse = page.waitForResponse((response) => response.request().method() === "POST" && response.url().endsWith("/demo/reset"));
      await page.getByRole("button", { name: "Reset this simulated dataset", exact: true }).click();
      expect((await resetResponse).status()).toBe(200);
      await expect(page.getByText("The isolated simulated dataset was reset. No physical inventory was changed.")).toBeVisible();
    }
    expect(errors).toEqual([]);
    writeFileSync(path.join(output, "rehearsals.json"), JSON.stringify({ provenance: "REAL_HTTP_POSTGRESQL_OR_TOOLS_SIMULATED_INPUTS", repetitions: evidence, page_errors: errors }, null, 2));
  });
});
