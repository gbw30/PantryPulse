import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, type BrowserContext, type Page } from "@playwright/test";

// Helpers for the connected v1 specs (PP_RUN_CONNECTED=1): a real browser, the Next proxy, the API,
// PostgreSQL and the production worker. Nothing here mocks a route. Run them as the CI connected
// step does (.github/workflows/pantrypulse-ci.yml), with DATABASE_URL and PP_DATABASE_SCHEMA set
// for the read-only probe.

export const CONNECTED = process.env.PP_RUN_CONNECTED === "1";
export const NEEDS_BACKEND = "Requires the isolated seeded API, PostgreSQL and the production worker (PP_RUN_CONNECTED=1)";
const ROOT = path.resolve(__dirname, "../../../..");
const FIXTURES = path.join(__dirname, "fixtures", "v1-connected");
export const REQUIRED = ["locations", "products", "inventory", "demand_history"] as const;
export type TemplateFile = (typeof REQUIRED)[number] | "routes" | "inbound" | "donation_history";

export const fixturePath = (set: string, name: TemplateFile) => path.join(FIXTURES, set, `${name}.csv`);
export const fixtureText = (set: string, name: TemplateFile) => readFileSync(fixturePath(set, name), "utf8");
/** A name no earlier run in the same schema used (CI keeps one schema per run, with retries). */
export const uniqueName = (base: string) => `${base} ${Date.now().toString(36)}`;

// The API allows 5 presenter logins a minute per address (presenter_access.LoginLimiter), so a worker signs
// in through the form once and later tests reuse that session's cookies.
let session: Awaited<ReturnType<BrowserContext["storageState"]>> | null = null;

/** Sign in from the sidebar footer with the run's generated presenter credentials (never hard-coded). */
export async function signIn(page: Page, at = "/import") {
  if (session) await page.context().addCookies(session.cookies);
  await page.goto(at);
  if (!session) {
    await page.getByRole("button", { name: "Presenter sign in" }).click();
    await page.getByLabel("Username", { exact: true }).fill(process.env.PP_E2E_USERNAME ?? "presenter");
    const password = page.getByLabel("Password", { exact: true });
    await password.fill(process.env.PP_E2E_PASSWORD ?? "");
    try {
      // A rejected login (429, wrong password) never reloads: fail fast instead of at the test timeout.
      await Promise.all([page.waitForEvent("load", { timeout: 30_000 }), page.getByRole("button", { name: "Sign in", exact: true }).click()]);
    } catch (error) {
      await password.fill("").catch(() => {}); // keep the password out of the failure snapshot
      throw error;
    }
  }
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  session ??= await page.context().storageState();
}

/** Fill the import form for a new network from a fixture set and press "Check and import". */
export async function startImport(page: Page, { name, mode, set, files }: { name: string; mode: "Pantry" | "Retail"; set: string; files: readonly TemplateFile[] }) {
  if (!page.url().endsWith("/import")) await page.goto("/import");
  await page.getByLabel("Network name").fill(name);
  await page.getByRole("radio", { name: new RegExp(`^${mode} network`) }).click();
  for (const file of files) {
    const kind = (REQUIRED as readonly string[]).includes(file) ? "required" : "optional";
    await page.getByLabel(`${file}.csv (${kind})`).setInputFiles(fixturePath(set, file));
  }
  await page.getByRole("button", { name: "Check and import" }).click();
}

/** Import a fixture set and wait for the finished summary; returns the new network's id. */
export async function importNetwork(page: Page, options: Parameters<typeof startImport>[1]) {
  await startImport(page, options);
  await expect(page.getByRole("region", { name: "Import finished" })).toBeVisible({ timeout: 90_000 });
  const switcher = page.getByRole("combobox", { name: "Network", exact: true });
  await expect(switcher).toContainText(options.name);
  return page.evaluate(() => window.localStorage.getItem("pantrypulse.network"));
}

const PYTHON = path.join(ROOT, "apps", "api", ".venv", "bin", "python");

/** Read-only digest per table ("md5:count") of the connected schema (connected/db_probe.py). */
export function probe(tables: readonly string[]): Record<string, string> {
  return JSON.parse(execFileSync(PYTHON, [path.join(__dirname, "connected", "db_probe.py"), ...tables], { encoding: "utf8" })) as Record<string, string>;
}

/**
 * Escalation E-1 (approved): the v1 forecast routes are 501 until W3-F03 (W4), so the journeys seed a
 * FIXTURE forecast run from the set's forecast.json (connected/seed_forecast.py). It is never forecast
 * evidence; import, scenario, comparison, decisions and export stay real. Returns the run's id.
 */
export async function seedForecast(page: Page, networkId: string, set: string) {
  const listed = await page.request.get("/api/v1/networks");
  expect(listed.status()).toBe(200);
  const { networks } = (await listed.json()) as { networks: { id: string; dataset_version_id: string | null }[] };
  const version = networks.find((n) => n.id === networkId)?.dataset_version_id;
  expect(version, "the imported network has a dataset version").toBeTruthy();
  return execFileSync(PYTHON, [path.join(__dirname, "connected", "seed_forecast.py"), networkId, version!, path.join(FIXTURES, set, "forecast.json")], { encoding: "utf8" }).trim();
}
