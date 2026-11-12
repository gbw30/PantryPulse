import path from "node:path";
import { defineConfig } from "@playwright/test";
import base from "../../../playwright.config";

// W5-UI01/UI03: the screenshot capture is evidence, not a test, so it lives outside the default testMatch.
// CI rejects any skipped test (scripts/quality/require-test-evidence.py), and a capture that needs the
// connected stack would skip there. Run it through run-e2e.sh with `--config tests/e2e/connected/evidence.config.ts`.
export default defineConfig({
  ...base,
  testDir: __dirname,
  testMatch: "visual-evidence.capture.ts",
  workers: 1,
  // A step that hangs fails with its locator instead of waiting out the 30-minute test.
  use: { ...base.use, actionTimeout: 30_000, navigationTimeout: 60_000 },
  webServer: { ...(base.webServer as object), cwd: path.resolve(__dirname, "../../..") } as typeof base.webServer,
});
