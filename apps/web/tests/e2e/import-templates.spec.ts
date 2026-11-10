// covers: V1-A06
import { expect, test, type Page } from "@playwright/test";
import { example, mockV1, type Schemas } from "./v1-mocks";

// Mocked against packages/contracts/examples/v1 (TemplateCatalog, NetworkList): proves UI behavior,
// not the connected app. As today's API does (CR-w3-samples-3): only the Pantry catalog marks examples
// available, Retail's arrive with samples PR #128, and a catalog with no mode offers none. The connected
// check that a Retail import downloads the Retail file is a W4 carry-in, after #128.
const catalog = example("TemplateCatalog");
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
      : { contentType: "text/csv", body: `${header(template)}${call.query.get("mode")} example\r\n` };
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

  // Pantry: each link names the mode, and the browser downloads from exactly that URL.
  await page.getByRole("radio", { name: /^Pantry network/ }).click();
  for (const template of catalog.templates) {
    const url = `/api/v1/templates/${template.name}.csv?kind=example&mode=PANTRY`;
    const exampleLink = section(page, template.name).getByRole("link", { name: `Download example ${template.name}.csv` });
    await expect(exampleLink).toHaveAttribute("href", url);
    const download = page.waitForEvent("download");
    await exampleLink.click();
    expect((await download).suggestedFilename()).toBe(`${template.name}-example.csv`);
    expect(new URL((await download).url()).pathname + new URL((await download).url()).search).toBe(url);
  }
  // Retail, whose catalog says no example yet: disabled, saying so, with nothing fetched to learn why.
  await page.getByRole("radio", { name: /^Retail network/ }).click();
  for (const template of catalog.templates) {
    await expect(section(page, template.name).getByRole("button", { name: `Download example ${template.name}.csv` })).toBeDisabled();
    await expect(section(page, template.name).getByText("Example not available yet.", { exact: true })).toBeVisible();
  }
  // The page itself never requests an example (no "why unavailable" probe): the catalog decides.
  expect(calls.filter((c) => c.path.startsWith("templates/") && c.query.get("kind") === "example")).toEqual([]);
});
