// covers: V1-A06
import { expect, test } from "@playwright/test";
import { envelope, example, mockV1 } from "./v1-mocks";

// Mocked against packages/contracts/examples/v1 (TemplateCatalog, NetworkList): proves UI behavior,
// not the connected app. Until W3-P03 the API answers the example download with a 501 envelope.
const catalog = example("TemplateCatalog");
const NOT_YET = envelope("NOT_IMPLEMENTED", "not implemented", { task: "W3-P03" });

test("@V1-A06 each template offers blank and example downloads", async ({ page }) => {
  const routes: Parameters<typeof mockV1>[1] = { "GET networks": { body: example("NetworkList") }, "GET templates": { body: catalog } };
  for (const template of catalog.templates) {
    routes[`GET templates/${template.name}.csv`] = (call) => call.query.get("kind") === "example"
      ? { status: 501, body: NOT_YET }
      : { contentType: "text/csv", body: `${template.columns.map((c) => c.name).join(",")}\r\n` };
  }
  await mockV1(page, routes);
  await page.goto("/import");
  await expect(page.getByRole("heading", { level: 1, name: "Import your network" })).toBeVisible();

  for (const template of catalog.templates) {
    const section = page.getByRole("region", { name: new RegExp(`^${template.name}\\.csv`) });
    const blank = section.getByRole("link", { name: `Download blank ${template.name}.csv` });
    await expect(blank).toHaveAttribute("href", `/api/v1/templates/${template.name}.csv?kind=blank`);
    const download = page.waitForEvent("download");
    await blank.click();
    expect((await download).suggestedFilename()).toBe(`${template.name}.csv`);

    // example_available is false in the contract example: disabled, with the 501 envelope's reason.
    const exampleButton = section.getByRole("button", { name: `Download example ${template.name}.csv` });
    await expect(exampleButton).toBeDisabled();
    await expect(section.getByText("Example not available yet: not implemented (W3-P03)")).toBeVisible();
  }
});
