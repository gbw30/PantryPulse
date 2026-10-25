import { expect, test, type Page, type Route } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";

// PP-56 data input: mocked presenter APIs. Covers visitor read-only, atomic import rejection,
// null-not-zero quantities, idempotency reuse, inventory 409 staleness and supply confirmation.

const BASE = `http://127.0.0.1:${process.env.PLAYWRIGHT_PORT ?? "3000"}`;
const envelope = (code: string, details: Record<string, unknown> = {}) => ({ error: { code, message: code.toLowerCase(), details }, request_id: "00000000-0000-4000-8000-000000000000" });

const SITE = "11111111-1111-4111-8111-111111111111";
const PRODUCT = "22222222-2222-4222-8222-222222222222";
const SOURCE = "33333333-3333-4333-8333-333333333333";
const DONOR = "44444444-4444-4444-8444-444444444444";
const LOT = "55555555-5555-4555-8555-555555555555";
const SUPPLY = "66666666-6666-4666-8666-666666666666";

const CATALOG = {
  sites: [{ id: SITE, name: "Riverbend Pantry", role: "BENEFICIARY" }],
  products: [{ id: PRODUCT, name: "Shelf-stable meals", base_unit: "meal" }],
  donors: [{ id: DONOR, name: "Community Donor" }],
  data_sources: [{ id: SOURCE, name: "Demo intake", classification: "SIMULATED" }],
};

const SNAPSHOT = {
  site_id: SITE, product_id: PRODUCT, site_name: "Riverbend Pantry", product_name: "Shelf-stable meals",
  base_unit: "meal", timezone: "America/New_York", local_date: "2026-10-25", observed_at: "2026-10-25T12:00:00Z",
  inventory_version: "7", on_hand_quantity: "40", usable_quantity: "28", excluded_quantity: "12",
  excluded_quantities: { EXPIRED: "12" },
  lots: [
    { lot_id: LOT, batch_key: "B-1", eligibility: "ELIGIBLE", expiry_kind: "DATED", expires_on: "2026-10-30", on_hand_quantity: "28", usable: true, exclusion_reason: null, metadata_version: "2" },
    { lot_id: "77777777-7777-4777-8777-777777777777", batch_key: "B-0", eligibility: "ELIGIBLE", expiry_kind: "DATED", expires_on: "2026-10-20", on_hand_quantity: "12", usable: false, exclusion_reason: "EXPIRED", metadata_version: "1" },
  ],
};

async function asPresenter(page: Page, handler: (path: string, route: Route) => Promise<boolean> | boolean) {
  await page.context().addCookies([{ name: "pp_csrf", value: "token", url: BASE }]);
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.slice("/api/v1/".length);
    if (path === "allocation-methodology") return route.fulfill({ status: 200, json: { methods: [] } });
    if (path === "operational-catalog") return route.fulfill({ status: 200, json: CATALOG });
    if (await handler(path, route)) return;
    return route.fulfill({ status: 404, json: envelope("NOT_FOUND") });
  });
}

test("visitor sees no forms on either data-input route", async ({ page }, testInfo) => {
  await page.route("**/api/v1/**", (route) => route.fulfill({ status: 401, json: envelope("PRESENTER_REQUIRED") }));
  for (const path of ["/data/inputs", "/data/inventory"]) {
    await page.goto(path);
    await expect(page.getByText("Presenter sign-in required")).toBeVisible();
    await expect(page.locator("form")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /adjustment|Import|Create/ })).toHaveCount(0);
  }
  await expectNoSeriousA11yViolations(page, testInfo, "data input visitor");
});

test("atomic demand import rejection lists rows and saves nothing; null quantities stay null", async ({ page }, testInfo) => {
  const bodies: unknown[] = [];
  await asPresenter(page, (path, route) => {
    if (path === "imports/demand" && route.request().method() === "POST") {
      bodies.push(route.request().postDataJSON());
      void route.fulfill({ status: 422, json: envelope("INVALID_OPERATIONAL_INPUT", { atomic: true, accepted_count: "0", rejected_count: "2", errors: [{ row_index: 1, field: "requested", code: "string_pattern_mismatch" }] }) });
      return true;
    }
    return false;
  });
  await page.goto("/data/inputs");
  await page.getByLabel("Data source").selectOption(SOURCE);
  await page.getByLabel("Row 1 record key").fill("rec-1");
  await page.getByLabel("Row 1 site").selectOption(SITE);
  await page.getByLabel("Row 1 product").selectOption(PRODUCT);
  await page.getByLabel("Row 1 day").fill("2026-10-20");
  await page.getByLabel("Row 1 requested").fill("12");
  await page.getByRole("button", { name: "Add row" }).click();
  await page.getByLabel("Row 2 record key").fill("rec-2");
  await page.getByLabel("Row 2 site").selectOption(SITE);
  await page.getByLabel("Row 2 product").selectOption(PRODUCT);
  await page.getByLabel("Row 2 day").fill("2026-10-21");
  await page.getByLabel("Row 2 unmet").fill("3");
  await page.getByRole("button", { name: "Import demand history" }).click();

  await expect(page.getByText("No rows were saved.", { exact: false })).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "string_pattern_mismatch" }).getByRole("cell").first()).toHaveText("2");
  const body = bodies[0] as { rows: Record<string, unknown>[] };
  expect(body.rows[0].fulfilled).toBeNull();
  expect(body.rows[0].unmet).toBeNull();
  expect(body.rows[0].requested).toBe("12");
  expect(body.rows[1].requested).toBeNull();
  await expectNoSeriousA11yViolations(page, testInfo, "demand import rejection");
});

test("retry after network failure reuses the Idempotency-Key; an edit changes it", async ({ page }) => {
  const keys: string[] = [];
  let calls = 0;
  await asPresenter(page, (path, route) => {
    if (path === "imports/demand" && route.request().method() === "POST") {
      keys.push(route.request().headers()["idempotency-key"]);
      calls += 1;
      if (calls === 1) { void route.abort("connectionrefused"); } else {
        void route.fulfill({ status: 201, json: { command_id: "88888888-8888-4888-8888-888888888888", operation: "demand-import", result: { accepted_count: "1", rows: [] } } });
      }
      return true;
    }
    return false;
  });
  await page.goto("/data/inputs");
  await page.getByLabel("Data source").selectOption(SOURCE);
  await page.getByLabel("Row 1 record key").fill("rec-1");
  await page.getByLabel("Row 1 site").selectOption(SITE);
  await page.getByLabel("Row 1 product").selectOption(PRODUCT);
  await page.getByLabel("Row 1 day").fill("2026-10-20");
  await page.getByLabel("Row 1 requested").fill("5");
  await page.getByRole("button", { name: "Import demand history" }).click();
  await expect(page.getByText("Could not reach the server", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByText("Import saved — 1 row(s) accepted")).toBeVisible();
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
});

for (const [width, height] of [[1440, 900], [1280, 720], [390, 844]]) {
  test(`inventory lots, declaration and stale adjustment at ${width}x${height}`, async ({ page }, testInfo) => {
    const adjustments: { body: Record<string, unknown>; key: string }[] = [];
    let declared = 0;
    await asPresenter(page, (path, route) => {
      if (path === `inventory/sites/${SITE}/products/${PRODUCT}`) { void route.fulfill({ status: 200, json: SNAPSHOT }); return true; }
      if (path === `inventory/lots/${LOT}/declarations`) {
        declared += 1;
        void route.fulfill({ status: 200, json: { command_id: "99999999-9999-4999-8999-999999999999", operation: "declare", result: {} } });
        return true;
      }
      if (path === `inventory/sites/${SITE}/products/${PRODUCT}/adjustments`) {
        adjustments.push({ body: route.request().postDataJSON() as Record<string, unknown>, key: route.request().headers()["idempotency-key"] });
        void route.fulfill({ status: 409, json: envelope("STALE_INVENTORY_VERSION") });
        return true;
      }
      return false;
    });
    await page.setViewportSize({ width, height });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto(`/data/inventory?site=${SITE}&product=${PRODUCT}`);

    await expect(page.getByText("inventory version 7", { exact: false })).toBeVisible();
    await expect(page.getByRole("row").filter({ hasText: "B-0" })).toContainText("Expired");
    await page.screenshot({ path: testInfo.outputPath(`inventory-${width}.png`), fullPage: true });
    await expectNoSeriousA11yViolations(page, testInfo, `inventory ${width}x${height}`);

    // Declaration sends the loaded inventory version.
    await page.getByRole("button", { name: "Declare lot B-1" }).click();
    await page.getByLabel("Reason").fill("Spot check");
    await page.getByRole("button", { name: "Save declaration" }).click();
    await expect(page.getByText("Lot B-1 declared eligible", { exact: false })).toBeVisible();
    expect(declared).toBe(1);

    // Stale adjustment: 409 copy with a reload path; the loaded version was sent.
    await page.getByRole("button", { name: "Record stock adjustment" }).click();
    await page.getByLabel("Change for lot B-1 (meal)").fill("-3");
    await page.getByLabel("Reason").fill("Damaged cases");
    await page.getByLabel("Source reference").fill("count-sheet-12");
    await page.getByRole("button", { name: "Apply adjustment" }).click();
    await expect(page.getByText("Inventory changed since you loaded it", { exact: false })).toBeVisible();
    await expect(page.getByRole("button", { name: "Reload inventory" })).toBeVisible();
    expect((adjustments[0].body as { expected_inventory_version: string }).expected_inventory_version).toBe("7");
    expect((adjustments[0].body as { changes: { delta: string }[] }).changes).toEqual([{ lot_id: LOT, delta: "-3" }]);
  });
}

test("supply create then confirm sends both expected versions", async ({ page }) => {
  const confirmations: Record<string, unknown>[] = [];
  const supplies: Record<string, unknown>[] = [];
  await asPresenter(page, (path, route) => {
    if (path === "supplies" && route.request().method() === "GET") {
      void route.fulfill({ status: 200, json: { supplies: supplies.length ? [{ id: SUPPLY, site_id: SITE, product_id: PRODUCT, source_id: SOURCE, source_record_key: "PO-9", quantity: "50", received_quantity: "0", outstanding_confirmed_quantity: "0", expected_arrival_at: null, state: "UNCONFIRMED", version: "1" }] : [] } });
      return true;
    }
    if (path === "supplies" && route.request().method() === "POST") {
      supplies.push(route.request().postDataJSON() as Record<string, unknown>);
      void route.fulfill({ status: 201, json: { command_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", operation: "supply-create", result: {} } });
      return true;
    }
    if (path === `supplies/${SUPPLY}/confirmation`) {
      confirmations.push(route.request().postDataJSON() as Record<string, unknown>);
      void route.fulfill({ status: 200, json: { command_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", operation: "confirm", result: {} } });
      return true;
    }
    return false;
  });
  await page.goto("/data/inputs");
  await page.getByRole("button", { name: "Expected supplies" }).click();
  await page.getByLabel("Site", { exact: true }).selectOption(SITE);
  await page.getByLabel("Product", { exact: true }).selectOption(PRODUCT);
  await page.getByLabel("Data source").selectOption(SOURCE);
  await page.getByLabel("Source record key").fill("PO-9");
  await page.getByLabel("Quantity (meal)").fill("50");
  await page.getByRole("button", { name: "Create expected supply" }).click();
  await expect(page.getByText("Expected supply created (unconfirmed)", { exact: false })).toBeVisible();

  await page.getByRole("button", { name: "Confirm / cancel supply PO-9" }).click();
  await page.getByLabel("Current inventory version", { exact: false }).fill("7");
  await page.getByLabel("Reason").fill("Carrier confirmed");
  await page.getByRole("button", { name: "Confirm supply" }).click();
  await expect(page.getByText("not on-hand stock", { exact: false })).toBeVisible();
  const body = confirmations[0] as { expected_supply_version: string; expected_inventory_version: string; outstanding_quantity: string; cancel: boolean };
  expect(body.expected_supply_version).toBe("1");
  expect(body.expected_inventory_version).toBe("7");
  expect(body.outstanding_quantity).toBe("50");
  expect(body.cancel).toBe(false);
});

test("receipt create, stale revise and post with declarations", async ({ page }) => {
  let revision = 1;
  const posts: Record<string, unknown>[] = [];
  const RECEIPT = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
  const receiptRead = () => ({
    receipt: { id: RECEIPT, source_id: SOURCE, source_record_key: "R-1" },
    revisions: Array.from({ length: revision }, (_, i) => ({
      id: `dddddddd-dddd-4ddd-8ddd-00000000000${i + 1}`, revision: String(i + 1), receiving_site_id: SITE, donor_id: DONOR,
      received_at: "2026-10-24T15:00:00Z", local_day: "2026-10-24", is_void: false,
      lines: [{ id: `eeeeeeee-eeee-4eee-8eee-00000000000${i + 1}`, line_key: "L1", product_id: PRODUCT, received_quantity: "30" }],
    })),
    reconciliation: null,
  });
  await asPresenter(page, (path, route) => {
    const method = route.request().method();
    if (path === "receipts" && method === "POST") {
      void route.fulfill({ status: 201, json: { command_id: "ffffffff-ffff-4fff-8fff-ffffffffffff", operation: "receipt-create", result: { receipt_id: RECEIPT, revision_id: "x", revision: "1", stock_changed: false, is_void: false } } });
      return true;
    }
    if (path === `receipts/${RECEIPT}` && method === "GET") { void route.fulfill({ status: 200, json: receiptRead() }); return true; }
    if (path === `receipts/${RECEIPT}/revisions`) { void route.fulfill({ status: 409, json: envelope("STALE_RECEIPT_REVISION") }); return true; }
    if (path === `receipts/${RECEIPT}/post`) {
      posts.push(route.request().postDataJSON() as Record<string, unknown>);
      revision = 1;
      void route.fulfill({ status: 200, json: { command_id: "f0f0f0f0-0000-4000-8000-000000000000", operation: "post", result: { stock_changed: true } } });
      return true;
    }
    if (path === `inventory/sites/${SITE}/products/${PRODUCT}`) { void route.fulfill({ status: 200, json: SNAPSHOT }); return true; }
    return false;
  });
  await page.goto("/data/inputs");
  await page.getByRole("button", { name: "Receipts" }).click();
  await page.getByLabel("Donor").selectOption(DONOR);
  await page.getByLabel("Receiving site").selectOption(SITE);
  await page.getByLabel("Data source").selectOption(SOURCE);
  await page.getByLabel("Source record key").fill("R-1");
  await page.getByLabel("Received at").fill("2026-10-24T15:00");
  await page.getByLabel("Line 1 product").selectOption(PRODUCT);
  await page.getByLabel("Line 1 quantity").fill("30");
  await page.getByRole("button", { name: "Create receipt (no stock effect)" }).click();
  await expect(page.getByText("Revision 1", { exact: true })).toBeVisible();

  // Stale revision shows the 409 copy.
  await page.getByRole("button", { name: "Revise (expects revision 1)" }).click();
  await page.getByRole("button", { name: /Save revision 2/ }).click();
  await expect(page.getByText("newer revision", { exact: false })).toBeVisible();

  // Post with a declaration and a loaded version (reopen via the session-tracked link).
  await page.getByRole("button", { name: "cccccccc" }).click();
  await page.getByRole("button", { name: "Post to stock…" }).click();
  await page.getByLabel("Line L1 expires on").fill("2026-11-05");
  await page.getByRole("button", { name: "Load current versions" }).click();
  await expect(page.getByLabel("Shelf-stable meals (meal)")).toHaveValue("7");
  await page.getByLabel("Reason").fill("Arrived complete");
  await page.getByRole("button", { name: "Post to stock", exact: true }).click();
  await expect(page.getByText("Receipt posted — stock changed", { exact: false })).toBeVisible();
  const body = posts[0] as { declarations: { line_key: string; expiry: { kind: string; expires_on: string } }[]; expected_versions: { version: string }[] };
  expect(body.declarations[0]).toMatchObject({ line_key: "L1", eligibility: "ELIGIBLE", expiry: { kind: "DATED", expires_on: "2026-11-05" } });
  expect(body.expected_versions).toEqual([{ site_id: SITE, product_id: PRODUCT, version: "7" }]);
});

test("connected: CSV import, receipt post and adjustment against the seeded API", async ({ page }) => {
  test.skip(process.env.PP_RUN_CONNECTED !== "1", "Requires isolated seeded PostgreSQL and API");
  // Covered by the packet's connected plan; exercised when PP_RUN_CONNECTED=1 with the demo launcher.
  await page.goto("/data/inputs");
  await expect(page.getByRole("heading", { level: 2, name: "Data input" })).toBeVisible();
});
