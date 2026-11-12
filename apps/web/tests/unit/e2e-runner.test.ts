// covers: V1-A22
import { spawnSync } from "node:child_process";
import { copyFileSync, mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { createServer, type Server } from "node:net";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, expect, it, vi } from "vitest";

// W5-UI05 (W4-03 known limits): a local connected run must never test a leftover server. Playwright reuses
// any server already on its port outside CI, and that server serves a stale build.
const RUNNER = path.resolve(__dirname, "../e2e/connected/run-e2e.sh");
let server: Server | null = null;
afterEach(() => { server?.close(); server = null; vi.unstubAllEnvs(); vi.resetModules(); });

it("run-e2e.sh exits with a clear message when its Playwright port is already in use", async () => {
  server = createServer();
  const port = await new Promise<number>((resolve) => server!.listen(0, "127.0.0.1", () => resolve((server!.address() as { port: number }).port)));
  // A throwaway repo root with the runner at its real depth, the lane env and a run directory.
  const root = mkdtempSync(path.join(tmpdir(), "pp-runner-"));
  const dir = path.join(root, "apps/web/tests/e2e/connected");
  mkdirSync(dir, { recursive: true });
  copyFileSync(RUNNER, path.join(dir, "run-e2e.sh"));
  writeFileSync(path.join(root, ".env.lane"), `PLAYWRIGHT_PORT=${port}\nPP_API_PORT=1\nPP_TEST_DATABASE_URL=postgresql://unused\n`);
  mkdirSync(path.join(root, "run"));
  writeFileSync(path.join(root, "run/demo.env"), "");
  writeFileSync(path.join(root, "run/schema"), "unused");
  const result = spawnSync("bash", [path.join(dir, "run-e2e.sh"), "--list"], { env: { ...process.env, RUN: path.join(root, "run") }, encoding: "utf8" });
  expect(result.status).not.toBe(0);
  expect(result.stderr).toContain(`port ${port} is already in use`);
  expect(result.stdout + result.stderr, "Playwright never started").not.toMatch(/Listing tests|No tests found|npm (warn|error)/);
});

it("connected runs never reuse an existing server; other local runs still may", async () => {
  vi.stubEnv("CI", "");
  vi.stubEnv("PP_RUN_CONNECTED", "1");
  const connected = (await import("../../playwright.config")).default;
  expect(connected.webServer).toMatchObject({ reuseExistingServer: false });
  vi.resetModules();
  vi.stubEnv("PP_RUN_CONNECTED", "");
  const local = (await import("../../playwright.config")).default;
  expect(local.webServer).toMatchObject({ reuseExistingServer: true });
});
