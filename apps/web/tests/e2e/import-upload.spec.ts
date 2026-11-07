// covers: V1-A07, V1-A20, V1-A23
import { expect, test, type Page } from "@playwright/test";
import { expectNoSeriousA11yViolations } from "./a11y";
import { example, mockV1, type Call, type Schemas } from "./v1-mocks";

// Mocked against packages/contracts/examples/v1 (TemplateCatalog, ImportCreated, ImportFile,
// ImportAccepted, ImportStatus, NetworkList, Network): proves UI behavior, not the connected app.

type Status = Schemas["ImportStatus"];
const created = example("ImportCreated");
const accepted = example("ImportAccepted");
const failedStatus = example("ImportStatus");
const IMPORT = created.import_id;

/**
 * The contract example lists two templates. The real catalog lists all seven, so the other five are
 * cloned from those two entries with their name and required flag changed (V1-SPEC §6.1 table).
 */
function fullCatalog(): Schemas["TemplateCatalog"] {
  const catalog = example("TemplateCatalog");
  const [required, history] = catalog.templates;
  const clone = (from: Schemas["Template"], name: Schemas["Template"]["name"], isRequired: boolean) =>
    ({ ...structuredClone(from), name, required: isRequired, description: `${name} rows.` });
  catalog.templates = [required, clone(required, "products", true), clone(required, "inventory", true), history,
    clone(required, "routes", false), clone(history, "inbound", false), clone(history, "donation_history", false)];
  return catalog;
}
const REQUIRED = ["locations", "products", "inventory", "demand_history"] as const;
const csv = (name: string) => ({ name: `${name}.csv`, mimeType: "text/csv",
  buffer: Buffer.from(name === "demand_history" ? "location_id,product_id,date,quantity,basis\nP1,W,2026-11-04,3,demand\n" : "id\n1\n") });

function doneStatus(): Status {
  return { ...example("ImportStatus"), phase: "done", failure: null, errors: [], error_count: 0, errors_truncated: false,
    network_id: example("Network").id, dataset_version_id: example("Network").dataset_version_id, as_of_date: "2026-11-05",
    files: REQUIRED.map((name) => ({ ...example("ImportFile"), name })) };
}

async function mockImport(page: Page, final: Status, networksAfter = example("NetworkList")) {
  let polls = 0;
  let finished = false;
  const calls = await mockV1(page, {
    // Before the import, the network the examples import (North County) doesn't exist yet.
    "GET networks": () => ({ body: finished && final.phase === "done" ? networksAfter
      : { networks: example("NetworkList").networks.filter((n) => n.id !== example("Network").id) } }),
    "GET templates": { body: fullCatalog() },
    "POST imports": { status: 201, body: created },
    [`POST imports/${IMPORT}/commit`]: { status: 202, body: accepted },
    [`GET imports/${IMPORT}`]: () => {
      polls += 1;
      if (polls < 2) return { body: { ...final, phase: "validating", progress: { unit: "checks", done: 3, total: 8 }, failure: null, errors: [], error_count: 0 } };
      finished = true;
      return { body: final };
    },
    ...Object.fromEntries(fullCatalog().templates.map((t) => [`POST imports/${IMPORT}/files/${t.name}`, { body: { ...example("ImportFile"), name: t.name } }])),
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  return calls;
}

async function fillNewNetwork(page: Page, name: string) {
  await page.getByLabel("Network name").fill(name);
  await page.getByRole("radio", { name: /^Pantry network/ }).click();
  for (const file of REQUIRED) await page.getByLabel(`${file}.csv (required)`).setInputFiles(csv(file));
}

const uploads = (calls: Call[]) => calls.filter((c) => c.method === "POST" && c.path.includes("/files/")).map((c) => c.path.split("/").at(-1));

test("@V1-A07 rejected import shows the failure message (failed, nothing saved, why, what to do), the per-row fixes, and no new network in the switcher", async ({ page }) => {
  const calls = await mockImport(page, failedStatus);
  await page.goto("/import");
  await fillNewNetwork(page, "North County Pantry Network");
  await page.getByRole("button", { name: "Check and import" }).click();

  const failure = page.getByRole("alert").filter({ hasText: failedStatus.failure!.message });
  await expect(failure).toBeVisible();
  await expect(failure).toContainText(failedStatus.failure!.reason);
  for (const step of failedStatus.failure!.next_steps) await expect(failure.getByText(step)).toBeVisible();
  const rows = page.getByRole("table", { name: /Rows to fix/ });
  for (const error of failedStatus.errors) {
    await expect(rows.getByRole("row", { name: new RegExp(`${error.file}\\.csv.*\\b${error.line}\\b.*${error.column}`) })).toContainText(error.fix);
  }
  const create = calls.find((c) => c.method === "POST" && c.path === "imports")!;
  expect(JSON.parse(create.body!)).toEqual({ network: { name: "North County Pantry Network", mode: "PANTRY", timezone: expect.any(String) } });
  expect(JSON.parse(calls.find((c) => c.path.endsWith("/commit"))!.body!)).toEqual({ as_of_date: "2026-11-05" });

  // Nothing was saved: the switcher still lists only the networks that existed before.
  await page.getByRole("combobox", { name: "Network", exact: true }).click();
  await expect(page.getByRole("option")).toHaveCount(example("NetworkList").networks.length - 1);
  await expect(page.getByRole("option", { name: /North County/ })).toHaveCount(0);
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "Start a new import" }).click();
  await expect(page.getByRole("table", { name: /Rows to fix/ })).toHaveCount(0);
  await expect(page.getByLabel("locations.csv (required)")).toHaveValue("");
});

test("@V1-A23 inbound and donation files are optional and labeled", async ({ page }) => {
  const calls = await mockImport(page, doneStatus());
  await page.goto("/import");
  await expect(page.getByLabel("inbound.csv (optional)")).toBeVisible();
  await expect(page.getByLabel("donation_history.csv (optional)")).toBeVisible();
  await expect(page.getByText(/Confirmed deliveries arriving in the 7 forecast days/)).toBeVisible();
  await expect(page.getByText(/A 0 means reported, nothing received; a missing day stays unknown/)).toBeVisible();

  await fillNewNetwork(page, "North County Pantry Network");
  await page.getByRole("button", { name: "Check and import" }).click();
  const summary = page.getByRole("region", { name: "Import finished" });
  await expect(summary).toContainText("no scheduled deliveries provided");
  expect(uploads(calls).sort()).toEqual([...REQUIRED].sort());
  // The new network is now listed and chosen.
  await expect(page.getByRole("combobox", { name: "Network", exact: true })).toContainText(example("Network").name);
});

for (const [width, height] of [[1440, 900], [1280, 720], [390, 844]] as const) {
  test(`@V1-A20 import keyboard-only path + axe at ${width}x${height}`, async ({ page }, testInfo) => {
    await mockImport(page, failedStatus);
    await page.setViewportSize({ width, height });
    await page.goto("/import");
    await expect(page.getByRole("heading", { level: 1, name: "Import your network" })).toBeVisible();
    await expectNoSeriousA11yViolations(page, testInfo, `import ${width}`);

    // From the skip link, Tab through the page and operate every control with the keyboard only.
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
    await page.keyboard.press("Enter");
    const focusedName = () => page.evaluate(() => {
      const el = document.activeElement as HTMLElement & { labels?: NodeListOf<HTMLLabelElement> };
      return (el.getAttribute("aria-label") ?? el.labels?.[0]?.textContent ?? el.textContent ?? "").trim();
    });
    const tabTo = async (name: RegExp) => {
      for (let i = 0; i < 120; i++) {
        await page.keyboard.press("Tab");
        if (name.test(await focusedName())) return;
      }
      throw new Error(`Never reached ${name} with Tab`);
    };
    await tabTo(/^Network name$/);
    await page.keyboard.type("Keyboard Network");
    await tabTo(/^Pantry network/);
    await page.keyboard.press("Space");
    await expect(page.getByRole("radio", { name: /^Pantry network/ })).toBeChecked();
    for (const file of REQUIRED) {
      await tabTo(new RegExp(`^${file}\\.csv \\(required\\)`));
      const chooser = page.waitForEvent("filechooser");
      await page.keyboard.press("Space");
      await (await chooser).setFiles(csv(file));
    }
    await tabTo(/^Check and import$/);
    await page.keyboard.press("Enter");
    await expect(page.getByRole("button", { name: "Start a new import" })).toBeVisible();
    await expectNoSeriousA11yViolations(page, testInfo, `import failed ${width}`);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
