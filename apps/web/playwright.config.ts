import { defineConfig, devices } from '@playwright/test';

// Сценарий моков передаётся в dev-сервер переменной окружения.
// Тот же набор спецификаций выполняется против реального backend,
// если VITE_MSW_SCENARIO пуст, а VITE_API_BASE_URL указывает на API.
const scenario = process.env.VITE_MSW_SCENARIO ?? 'happy-path';
const port = Number(process.env.VITE_E2E_PORT ?? process.env.PLAYWRIGHT_PORT ?? '5175');
const baseURL = `http://localhost:${port}`;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'desktop-chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: `npm run dev -- --port ${port} --strictPort`,
    url: baseURL,
    // Never reuse the real local backend frontend for MSW checks.
    reuseExistingServer: false,
    env: {
      VITE_MSW_SCENARIO: scenario,
    },
  },
});
