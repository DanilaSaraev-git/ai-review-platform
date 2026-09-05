import { defineConfig, devices } from '@playwright/test';

/** Read-only browser smoke against a running real API through the Vite dev proxy. */
export default defineConfig({
  testDir: './e2e',
  testMatch: 'live-api.spec.ts',
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5176',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'live-chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 5176 --strictPort',
    url: 'http://127.0.0.1:5176',
    reuseExistingServer: false,
    env: {
      VITE_MSW_SCENARIO: '',
      VITE_API_PROXY_TARGET: process.env.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:18081',
    },
  },
});
