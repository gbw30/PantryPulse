import type { Page } from "@playwright/test";
import { example, mockV1, type Schemas } from "./v1-mocks";

// Import-screen mocks shared by import-upload.spec.ts and v1-a11y.spec.ts, built from
// packages/contracts/examples/v1 (TemplateCatalog, ImportCreated, ImportFile, ImportAccepted,
// ImportStatus, NetworkList, Network): they prove UI behavior, not the connected app.

type Status = Schemas["ImportStatus"];
const created = example("ImportCreated");
const accepted = example("ImportAccepted");
export const failedStatus = example("ImportStatus");
const IMPORT = created.import_id;

/**
 * The contract example lists two templates. The real catalog lists all seven, so the other five are
 * cloned from those two entries with their name and required flag changed (V1-SPEC §6.1 table).
 */
export function fullCatalog(): Schemas["TemplateCatalog"] {
  const catalog = example("TemplateCatalog");
  const [required, history] = catalog.templates;
  const clone = (from: Schemas["Template"], name: Schemas["Template"]["name"], isRequired: boolean) =>
    ({ ...structuredClone(from), name, required: isRequired, description: `${name} rows.` });
  catalog.templates = [required, clone(required, "products", true), clone(required, "inventory", true), history,
    clone(required, "routes", false), clone(history, "inbound", false), clone(history, "donation_history", false)];
  return catalog;
}
export const REQUIRED = ["locations", "products", "inventory", "demand_history"] as const;
export const csv = (name: string) => ({ name: `${name}.csv`, mimeType: "text/csv",
  buffer: Buffer.from(name === "demand_history" ? "location_id,product_id,date,quantity,basis\nP1,W,2026-11-04,3,demand\n" : "id\n1\n") });

export function doneStatus(): Status {
  return { ...example("ImportStatus"), phase: "done", failure: null, errors: [], error_count: 0, errors_truncated: false,
    network_id: example("Network").id, dataset_version_id: example("Network").dataset_version_id, as_of_date: "2026-11-05",
    files: REQUIRED.map((name) => ({ ...example("ImportFile"), name })) };
}

export async function mockImport(page: Page, final: Status, networksAfter = example("NetworkList")) {
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
