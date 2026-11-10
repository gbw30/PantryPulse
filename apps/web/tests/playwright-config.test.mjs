import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { test } from "node:test";

// CR-w3-web-2 (approved 2026-11-09): connected runs sign in with the presenter password, and a trace keeps
// it (the fill value, DOM snapshots, the login request), so they record none. Mocked runs keep theirs.
const trace = (production, connected = "") => execFileSync(process.execPath, ["--input-type=module", "-e",
  "const { default: config } = await import('./playwright.config.ts'); process.stdout.write(String(config.use?.trace));"],
  { cwd: new URL("..", import.meta.url), env: { ...process.env, PP_E2E_PRODUCTION: production, PP_RUN_CONNECTED: connected }, encoding: "utf8" });

test("connected runs (PP_E2E_PRODUCTION=1 or PP_RUN_CONNECTED=1) record no trace; mocked runs keep retain-on-failure", () => {
  assert.equal(trace("1"), "off");
  assert.equal(trace("", "1"), "off"); // the local connected runner (connected/run-e2e.sh) sets only this one (M1)
  assert.equal(trace("1", "1"), "off");
  assert.equal(trace("0", "0"), "retain-on-failure");
  assert.equal(trace("", ""), "retain-on-failure");
});
