import { defineConfig, devices } from '@playwright/test';

// Сценарий моков передаётся в dev-сервер переменной окружения.
// Тот же набор спецификаций выполняется против реального backend,
// если VITE_MSW_SCENARIO пуст, а VITE_API_BASE_URL указывает на API.
const scenario = process.env.VITE_MSW_SCENARIO ?? 'happy-path';
const port = Number(process.env.PLAYWRIGHT_PORT ?? 5173);

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: `http://localhost:${port}`,
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
    url: `http://localhost:${port}`,
    reuseExistingServer: !process.env.CI,
    env: {
      VITE_MSW_SCENARIO: scenario,
    },
  },
});
