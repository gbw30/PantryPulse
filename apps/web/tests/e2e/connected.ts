import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, type BrowserContext, type Locator, type Page } from "@playwright/test";
import { signInThroughForm } from "./sign-in";

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

/** Sign in once per worker with the run's generated presenter credentials (PP_E2E_USERNAME, PP_E2E_PASSWORD). */
export async function signIn(page: Page, at = "/import") {
  if (session) await page.context().addCookies(session.cookies);
  await page.goto(at);
  if (!session) await signInThroughForm(page);
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
  const finished = page.getByRole("region", { name: "Import finished" });
  const full = page.getByRole("alert").filter({ hasText: "The import didn't start (compute queue full)" });
  await untilQueued(page, finished, full, () => full.getByRole("button", { name: "Retry" }).click(), 90_000);
  const switcher = page.getByRole("combobox", { name: "Network", exact: true });
  await expect(switcher).toContainText(options.name);
  return page.evaluate(() => window.localStorage.getItem("pantrypulse.network"));
}

const PYTHON = path.join(ROOT, "apps", "api", ".venv", "bin", "python");

/**
 * Read-only digest per table ("md5:count") of the connected schema (connected/db_probe.py). With `dataset`,
 * tables keyed by dataset version are read for that version only, so parallel specs' imports don't count.
 */
export function probe(tables: readonly string[], dataset?: string): Record<string, string> {
  const scope = dataset ? ["--dataset", dataset] : [];
  return JSON.parse(execFileSync(PYTHON, [path.join(__dirname, "connected", "db_probe.py"), ...scope, ...tables], { encoding: "utf8" })) as Record<string, string>;
}

/** The database clock, for probeExcept. */
export const dbNow = () => (JSON.parse(execFileSync(PYTHON, [path.join(__dirname, "connected", "db_probe.py"), "--clock"], { encoding: "utf8" })) as { now: string }).now;

/**
 * Whole-table digests, leaving out rows of the networks and dataset versions that parallel specs recorded since
 * `since` (any network not named `name`). Anything saved under `name`, or with no network, still counts.
 */
export function probeExcept(tables: readonly string[], since: string, name: string): Record<string, string> {
  return JSON.parse(execFileSync(PYTHON, [path.join(__dirname, "connected", "db_probe.py"), "--since", since, "--name", name, ...tables], { encoding: "utf8" })) as Record<string, string>;
}

/** The network's current dataset version, read from GET /networks. */
export async function datasetOf(page: Page, networkId: string) {
  const listed = await page.request.get("/api/v1/networks");
  expect(listed.status()).toBe(200);
  const { networks } = (await listed.json()) as { networks: { id: string; dataset_version_id: string | null }[] };
  const version = networks.find((n) => n.id === networkId)?.dataset_version_id;
  expect(version, "the network has a dataset version").toBeTruthy();
  return version!;
}

/**
 * CR-w3-samples-1: no route marks a network as a sample and the seeded samples arrive in W4, so this runs
 * the importer with the internal seed's `is_sample` flag on a fixture set (connected/seed_sample.py).
 * Returns the sample network's id.
 */
export function seedSample(name: string, mode: "PANTRY" | "RETAIL", set: string) {
  return execFileSync(PYTHON, [path.join(__dirname, "connected", "seed_sample.py"), name, mode, path.join(FIXTURES, set)], { encoding: "utf8" }).trim();
}

/** The fictional samples a first start seeds, by mode: their network ids and names. */
export type Samples = Record<"PANTRY" | "RETAIL", { id: string; name: string }>;

/**
 * W4-02 (V1-A05): run the first-start sample seed on the connected schema (connected/seed_samples.py runs
 * `seed_local.seed`, as the compose `seed` service does on every start). Idempotent, like every start.
 */
export function seedSamples(): Samples {
  return JSON.parse(execFileSync(PYTHON, [path.join(__dirname, "connected", "seed_samples.py")], { encoding: "utf8" })) as Samples;
}

/** Choose a network in the sidebar switcher, as a person does. */
export async function chooseNetwork(page: Page, name: string) {
  const switcher = page.getByRole("combobox", { name: "Network", exact: true });
  await switcher.click();
  await page.getByRole("option", { name: new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}( \\(sample\\))?$`) }).click();
  await expect(switcher).toContainText(name);
}

/**
 * Wait for `done`. While the API refuses the job because its queue is full (it queues 2 jobs per kind, and the
 * parallel specs share one API), wait as a person would and `retry`, until `timeout` runs out.
 */
export async function untilQueued(page: Page, done: Locator, full: Locator, retry: () => Promise<unknown>, timeout: number) {
  const deadline = Date.now() + timeout;
  for (;;) {
    await expect(done.or(full).first()).toBeVisible({ timeout: Math.max(1, deadline - Date.now()) });
    if (await done.isVisible()) return;
    expect(Date.now() + 15_000, "the job queue had room before the timeout").toBeLessThan(deadline);
    await page.waitForTimeout(15_000);
    await retry();
  }
}

// forecast.v1's ceiling is 270 s, behind whatever jobs the parallel specs queued first.
export const FORECAST_TIMEOUT = 600_000;

/**
 * W4-02 (Escalation E-1 closed): run a real forecast.v1 for the chosen network through the Overview's
 * "Run forecast" control and wait until it finishes. Returns the published run every v1 view now uses,
 * read independently of the page from GET /networks/{id}/forecasts.
 */
export async function runForecast(page: Page, name: string) {
  await page.goto("/overview");
  const section = page.getByRole("region", { name: `Danger ranking · ${name}` });
  const button = section.getByRole("button", { name: "Run forecast" });
  await expect(button).toBeVisible();
  await expect(button).not.toHaveAttribute("aria-disabled", "true");
  await button.click();
  // A new run, or the API replayed the finished run of the same input (a database where this forecast already ran).
  const finished = section.getByText(/^(Forecast finished\. The views below use the new run\.|The forecast is already up to date with the current data\.)$/);
  const full = section.getByRole("alert").filter({ hasText: "Forecast not started: compute queue full (COMPUTE_QUEUE_FULL)." });
  await untilQueued(page, finished, full, () => button.click(), FORECAST_TIMEOUT);
  const networks = (await (await page.request.get("/api/v1/networks")).json()) as { networks: { id: string; name: string; dataset_version_id: string | null }[] };
  const named = networks.networks.filter((n) => n.name === name);
  expect(named, `one network is named ${name}`).toHaveLength(1);
  const [network] = named;
  const id = network.id;
  const listed = await page.request.get(`/api/v1/networks/${id}/forecasts`);
  expect(listed.status()).toBe(200);
  const { runs } = (await listed.json()) as { runs: { job_id: string; forecast_run_id: string | null; dataset_version_id: string; state: string }[] };
  const run = runs.find((r) => r.dataset_version_id === network.dataset_version_id);
  expect(run?.state, "the newest forecast of the current data succeeded").toBe("SUCCEEDED");
  expect(run!.forecast_run_id).toBeTruthy();
  return { networkId: id, jobId: run!.job_id, forecastRunId: run!.forecast_run_id! };
}
