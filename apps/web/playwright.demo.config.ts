import { defineConfig, devices } from '@playwright/test';

/** Runs the actual /demo/ production bundle with synthetic runtime data. */
export default defineConfig({
  testDir: './e2e-demo',
  outputDir: './test-results/demo',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5176',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'demo-chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'VITE_MSW_SCENARIO=demo npm run build -- --base=/demo/ --outDir=dist-demo && npm run preview -- --host 127.0.0.1 --port 5176 --strictPort --base=/demo/ --outDir=dist-demo',
    url: 'http://127.0.0.1:5176/demo/',
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
