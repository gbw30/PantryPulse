import { defineConfig, devices } from '@playwright/test';

// Intended location: apps/web/playwright.config.ts. Implement the documented API seed entry point first.
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL: 'http://127.0.0.1:3000', trace: 'retain-on-failure', screenshot: 'only-on-failure', video: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
  webServer: [
    {
      command: 'uv run --frozen alembic upgrade head && uv run --frozen python -m app.seed_demo --reset --organization demo --fixed-date 2026-10-24 && uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000',
      cwd: '../api',
      url: 'http://127.0.0.1:8000/healthz',
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: process.env.CI ? 'npm run start -- --port 3000' : 'npm run dev -- --port 3000',
      url: 'http://127.0.0.1:3000',
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
