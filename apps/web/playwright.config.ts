import { defineConfig, devices } from "@playwright/test";

const port = process.env.PLAYWRIGHT_PORT ?? "3100";
const baseURL = `http://127.0.0.1:${port}`;
const apiPort = process.env.PLAYWRIGHT_API_PORT ?? "8011";
const apiURL = `http://127.0.0.1:${apiPort}`;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  // Geometry/a11y checks share a dev server; avoid CPU contention changing layout timing.
  workers: 2,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: [["list"], ["html", { open: "never" }], ["junit", { outputFile: "test-results/junit.xml" }]],
  use: {
    baseURL, trace: "retain-on-failure", screenshot: "only-on-failure",
    video: "retain-on-failure", locale: "en-US", timezoneId: "America/New_York",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [{
    command: `npm run dev -- --port ${port}`,
    env: { PANTRYPULSE_E2E: "1" },
    url: baseURL,
    // Reuse is opt-in: a different checkout on this port is not test evidence.
    reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "1",
    timeout: 120_000,
  }, {
    command: `uv run --frozen --directory ../api uvicorn app.main:app --host 127.0.0.1 --port ${apiPort}`,
    url: `${apiURL}/api/v1/health`,
    reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "1",
    timeout: 60_000,
  }],
});

