// covers: V1-A10, V1-A11
import { expect, test, type Page } from "@playwright/test";
import { example, mockV1, type Schemas } from "./v1-mocks";

// Mocked against packages/contracts/examples/v1 (EnrichmentStatus, LocationAttributes, RouteList,
// LocalSettings, ForecastAccepted, NetworkList): proves UI behavior, not the connected app.
const network = example("Network");
const NET = `networks/${network.id}`;

/** Enrichment after the user resolved P-07 (values or exclusion): no blockers left. */
function resolved(attributes: Schemas["LocationAttributes"]): Schemas["EnrichmentStatus"] {
  const status = example("EnrichmentStatus");
  status.locations = status.locations.map((l) => (l.location_id === attributes.location_id ? attributes : l));
  status.egp_blockers = [];
  return status;
}

async function open(page: Page) {
  let status = example("EnrichmentStatus");
  const calls = await mockV1(page, {
    "GET networks": { body: { networks: [network] } },
    "GET settings": { body: example("LocalSettings") },
    [`GET ${NET}/enrichment`]: () => ({ body: status }),
    [`GET ${NET}/routes`]: { body: example("RouteList") },
    [`POST ${NET}/enrichment/retry`]: { status: 202, body: example("ForecastAccepted") },
    [`PUT ${NET}/locations/P-07/attributes`]: (call) => {
      const update = JSON.parse(call.body!) as Schemas["LocationAttributesUpdate"];
      const saved: Schemas["LocationAttributes"] = update.excluded
        ? { ...example("LocationAttributes"), location_id: "P-07", state: "excluded", poverty_rate: null, snap_rate: null, source: null }
        : { ...example("LocationAttributes"), location_id: "P-07", poverty_rate: String(update.poverty_rate), snap_rate: String(update.snap_rate) };
      status = resolved(saved);
      return { body: saved };
    },
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/settings");
  await expect(page.getByRole("heading", { level: 1, name: "Settings" })).toBeVisible();
  return calls;
}

test("@V1-A10 unmatched addresses listed with retry", async ({ page }) => {
  const calls = await open(page);
  const unmatched = page.getByRole("region", { name: "Addresses not found" });
  for (const row of example("EnrichmentStatus").unmatched) {
    await expect(unmatched).toContainText(row.location_id);
    await expect(unmatched).toContainText(row.address);
    await expect(unmatched).toContainText(row.hint);
  }
  await unmatched.getByRole("button", { name: "Retry lookups" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Lookups queued" })).toBeVisible();
  expect(calls.filter((c) => c.method === "POST" && c.path === `${NET}/enrichment/retry`)).toHaveLength(1);
});

test("@V1-A10 EGP blocked banner lists locations until values entered or excluded", async ({ page }) => {
  const calls = await open(page);
  const banner = page.getByRole("alert").filter({ hasText: "EGP_PI_INSPIRED is blocked" });
  await expect(banner).toContainText("P-07: poverty rate, SNAP rate");

  const row = page.getByRole("group", { name: "P-07 attributes" });
  await row.getByRole("button", { name: "Enter values" }).click();
  await row.getByLabel("Poverty rate (0 to 1)").fill("0.25");
  await row.getByLabel("SNAP rate (0 to 1)").fill("0.3");
  await row.getByRole("button", { name: "Save" }).click();
  await expect(banner).toHaveCount(0);
  const put = calls.find((c) => c.method === "PUT")!;
  expect(JSON.parse(put.body!)).toEqual({ excluded: false, poverty_rate: "0.25", snap_rate: "0.3" });
  await expect(row).toContainText("Source: entered by you");

  // The other way out, on a fresh page whose mock starts blocked again: exclude the location explicitly.
  const second = await page.context().newPage();
  const secondCalls = await open(second);
  const secondBanner = second.getByRole("alert").filter({ hasText: "EGP_PI_INSPIRED is blocked" });
  await expect(secondBanner).toBeVisible();
  await second.getByRole("group", { name: "P-07 attributes" }).getByRole("button", { name: "Exclude from EGP" }).click();
  await expect(secondBanner).toHaveCount(0);
  expect(JSON.parse(secondCalls.find((c) => c.method === "PUT")!.body!)).toEqual({ excluded: true });
  await expect(second.getByRole("group", { name: "P-07 attributes" })).toContainText("Excluded from EGP");
});

test('@V1-A10 source line "Source: ACS 5-year YYYY, tract NNNN"', async ({ page }) => {
  await open(page);
  await expect(page.getByRole("group", { name: "P-12 attributes" })).toContainText("Source: ACS 5-year 2023, tract 0102");
  await expect(page.getByRole("group", { name: "P-07 attributes" })).toContainText("Source: unknown");
  // Route methods are labeled too (V1-A11).
  const routes = page.getByRole("table", { name: /Routes/ });
  await expect(routes).toContainText("straight-line estimate");
  await expect(routes).toContainText("Google road distance, fetched Nov 5, 2026");
});
