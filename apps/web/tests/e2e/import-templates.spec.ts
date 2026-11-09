// covers: V1-A06
import { expect, test, type Page } from "@playwright/test";
import { envelope, example, mockV1, type Schemas } from "./v1-mocks";

// Mocked against packages/contracts/examples/v1 (TemplateCatalog, NetworkList): proves UI behavior,
// not the connected app. As the API does (CR-w3-samples-3): Pantry serves examples, Retail answers
// 404 TEMPLATE_EXAMPLE_UNAVAILABLE until the samples lane adds its examples, and no mode offers none.
const catalog = example("TemplateCatalog");
const UNAVAILABLE = envelope("TEMPLATE_EXAMPLE_UNAVAILABLE");
const header = (t: Schemas["Template"]) => `${t.columns.map((c) => c.name).join(",")}\r\n`;

function catalogFor(mode: string | null): Schemas["TemplateCatalog"] {
  const known = mode === "PANTRY" || mode === "RETAIL" ? mode : null;
  return { ...catalog, mode: known, templates: catalog.templates.map((t) => ({ ...t, example_available: known === "PANTRY" })) };
}

const section = (page: Page, name: string) => page.getByRole("region", { name: new RegExp(`^${name}\\.csv`) });

test("@V1-A06 each template offers blank and example downloads", async ({ page }) => {
  const routes: Parameters<typeof mockV1>[1] = { "GET networks": { body: example("NetworkList") },
    "GET templates": (call) => ({ body: catalogFor(call.query.get("mode")) }) };
  for (const template of catalog.templates) {
    routes[`GET templates/${template.name}.csv`] = (call) => call.query.get("kind") !== "example"
      ? { contentType: "text/csv", body: header(template) }
      : call.query.get("mode") === "PANTRY" ? { contentType: "text/csv", body: `${header(template)}example\r\n` }
      : { status: 404, body: UNAVAILABLE };
  }
  const calls = await mockV1(page, routes);
  await page.goto("/import");
  await expect(page.getByRole("heading", { level: 1, name: "Import your network" })).toBeVisible();

  // Before a network type is chosen: blanks only, and no example is requested.
  for (const template of catalog.templates) {
    const blank = section(page, template.name).getByRole("link", { name: `Download blank ${template.name}.csv` });
    await expect(blank).toHaveAttribute("href", `/api/v1/templates/${template.name}.csv?kind=blank`);
    const download = page.waitForEvent("download");
    await blank.click();
    expect((await download).suggestedFilename()).toBe(`${template.name}.csv`);
    await expect(section(page, template.name).getByRole("button", { name: `Download example ${template.name}.csv` })).toBeDisabled();
    await expect(section(page, template.name).getByText("Choose Pantry or Retail under 2. Network settings to get an example.")).toBeVisible();
  }

  await page.getByRole("radio", { name: /^Pantry network/ }).click();
  for (const template of catalog.templates) {
    const exampleLink = section(page, template.name).getByRole("link", { name: `Download example ${template.name}.csv` });
    await expect(exampleLink).toHaveAttribute("href", `/api/v1/templates/${template.name}.csv?kind=example&mode=PANTRY`);
    const download = page.waitForEvent("download");
    await exampleLink.click();
    expect((await download).suggestedFilename()).toBe(`${template.name}-example.csv`);
  }

  await page.getByRole("radio", { name: /^Retail network/ }).click();
  for (const template of catalog.templates) {
    await expect(section(page, template.name).getByRole("button", { name: `Download example ${template.name}.csv` })).toBeDisabled();
    await expect(section(page, template.name).getByText("Example not available yet: template example unavailable")).toBeVisible();
  }
  // The page's own example requests (asking why one is unavailable) named the network's mode, and none
  // fell back to the API's Pantry default. A download's request isn't routed here, so links are checked by href.
  const examples = calls.filter((c) => c.path.startsWith("templates/") && c.query.get("kind") === "example");
  expect(examples.map((c) => `${c.path}?mode=${c.query.get("mode")}`).sort())
    .toEqual(catalog.templates.map((t) => `templates/${t.name}.csv?mode=RETAIL`).sort());
});
