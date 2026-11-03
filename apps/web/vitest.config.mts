import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  test: {
    include: ["tests/unit/**/*.test.{ts,tsx}"],
    environment: "jsdom",
    setupFiles: ["./tests/unit/setup.ts"],
    clearMocks: true,
    restoreMocks: true,
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      reportsDirectory: "../../artifacts/testing/web-coverage",
      include: ["src/components/overview/**/*.{ts,tsx}", "src/app/design-lab/outlook-data.ts", "src/lib/utils.ts"],
      exclude: ["**/types.ts"],
    },
  },
});
