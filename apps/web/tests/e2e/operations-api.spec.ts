import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

async function api(page: Page, path: string, body?: unknown, key = randomUUID()) {
  return page.evaluate(async ({ path, body, key }) => {
    const token = document.cookie.split("; ").find((c) => c.startsWith("pp_csrf="))?.split("=")[1] ?? "";
    const response = await fetch(`/api/v1/${path}`, body === undefined ? {} : {
      method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": token, "Idempotency-Key": key },
      body: JSON.stringify(body),
    });
    return { status: response.status, body: await response.json() };
  }, { path, body, key });
}

test("operational history, audited stock and canonical plan review through the browser proxy", async ({ page }) => {
  test.skip(process.env.PP_RUN_CONNECTED !== "1", "Requires isolated seeded database and Linux worker");
  test.setTimeout(180_000);
  await page.goto("/overview");
  await page.getByRole("button", { name: "Presenter sign in" }).click();
  await page.getByLabel("Username", { exact: true }).fill(process.env.PP_E2E_USERNAME ?? "presenter");
  await page.getByLabel("Password", { exact: true }).fill(process.env.PP_E2E_PASSWORD ?? "pantry-local-demo");
  await Promise.all([page.waitForEvent("load"), page.getByRole("button", { name: "Sign in", exact: true }).click()]);
  await expect(page.getByText("Presenter session · simulated demo")).toBeVisible();
  const catalog = await api(page, "operational-catalog");
  expect(catalog.status).toBe(200);
  const site = catalog.body.sites.find((s: { role: string }) => s.role === "HUB");
  const product = catalog.body.products[0];
  const inventoryPath = `inventory/sites/${site.id}/products/${product.id}`;
  const before = await api(page, inventoryPath);
  expect(before.status).toBe(200);
  const created = await api(page, "receipts", {
    source_id: catalog.body.data_sources[0].id, source_record_key: randomUUID(),
    site_id: site.id, donor_id: catalog.body.donors[0].id, received_at: new Date().toISOString(),
    expected_revision: null, is_void: false, lines: [{ line_key: "delivery", product_id: product.id, quantity: "2" }],
  });
  expect(created.status).toBe(201);
  expect((await api(page, inventoryPath)).body.on_hand_quantity).toBe(before.body.on_hand_quantity);
  const receipt = created.body.result;
  const postBody = {
    revision_id: receipt.revision_id, reason: "Fictional browser verification delivery",
    expected_versions: [{ site_id: site.id, product_id: product.id, version: before.body.inventory_version ?? "1" }],
    declarations: [{ line_key: "delivery", eligibility: "ELIGIBLE", expiry: { kind: "NON_EXPIRING", expires_on: null } }],
    supply_matches: [], supply_versions: [],
  };
  const key = randomUUID();
  const posted = await api(page, `receipts/${receipt.receipt_id}/post`, postBody, key);
  expect(posted.status).toBe(200);
  expect((await api(page, `receipts/${receipt.receipt_id}/post`, postBody, key)).body).toEqual(posted.body);
  const current = await api(page, inventoryPath);
  expect(BigInt(current.body.on_hand_quantity)).toBe(BigInt(before.body.on_hand_quantity) + BigInt(2));
  const adjusted = await api(page, `${inventoryPath}/adjustments`, {
    expected_inventory_version: current.body.inventory_version,
    reason: "Fictional physical count correction", source_reference: "browser-verification",
    changes: [{ lot_id: posted.body.result.lots[0].lot_id, delta: "-1" }],
  });
  expect(adjusted.status).toBe(200);
  const stockBeforePlanning = (await api(page, inventoryPath)).body.on_hand_quantity;
  const csv = await page.evaluate(async ({ sourceId, siteId, productId, recordKey }) => {
    const form = new FormData();
    form.set("source_id", sourceId);
    form.set("file", new Blob(["source_record_key,site_id,product_id,day,expected_revision,requested,fulfilled,unmet\n" +
      `${recordKey},${siteId},${productId},2000-01-01,,3,,\n`], { type: "text/csv" }), "fictional-history.csv");
    const token = document.cookie.split("; ").find((c) => c.startsWith("pp_csrf="))?.split("=")[1] ?? "";
    const response = await fetch("/api/v1/imports/demand/csv", { method: "POST", body: form,
      headers: { "X-CSRF-Token": token, "Idempotency-Key": recordKey } });
    return response.status;
  }, { sourceId: catalog.body.data_sources[0].id, siteId: site.id, productId: product.id, recordKey: `vp-e2e-csv-v1-${site.id}-${product.id}` });
  expect(csv).toBe(201);
  await page.getByRole("button", { name: "Generate forecast", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("SUCCEEDED", { timeout: 90_000 });
  await page.getByLabel("Transfer mode (required)").selectOption("HUB_ONLY");
  await page.getByRole("button", { name: "Freeze scenario", exact: true }).click();
  await expect(page.getByRole("button", { name: "Compare frozen scenario", exact: true })).toBeEnabled();
  const scenarioId = await page.getByLabel("Read a saved scenario").inputValue();
  const scenario = await api(page, `scenarios/${scenarioId}`);
  const accepted = await api(page, `scenarios/${scenarioId}/plans`, {
    expected_scenario_hash: scenario.body.payload.operational_hash, method: "CLASSICAL_GP", search_seconds: 1,
  });
  expect(accepted.status).toBe(202);
  await expect.poll(async () => (await api(page, `jobs/${accepted.body.job_id}`)).body.state, { timeout: 90_000 }).toBe("SUCCEEDED");
  const results = await api(page, `allocation-jobs/${accepted.body.job_id}/results`);
  expect(results.status).toBe(200);
  expect(results.body.plans).toHaveLength(1);
  const plan = results.body.plans[0];
  expect(plan.result.verification.passed).toBe(true);
  const review = await api(page, `plans/${plan.id}/review`, {
    action: "REVIEWED", expected_result_hash: plan.result_hash, note: "Simulation reviewed in browser verification",
  });
  expect(review.status).toBe(201);
  expect((await api(page, inventoryPath)).body.on_hand_quantity).toBe(stockBeforePlanning);
  expect((await api(page, "dashboard/summary")).status).toBe(200);
  expect((await api(page, `shortages/${scenario.body.forecast_run_id}`)).status).toBe(200);
});
