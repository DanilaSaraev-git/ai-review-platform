import { expect, test } from '@playwright/test';
import type { DemoPackage } from '../src/mocks/demo-package';
import { installSyntheticDemoPackage } from './fixture';

let data: DemoPackage;
test.beforeAll(async () => { data = await installSyntheticDemoPackage(); });

test('arbitrary file opens the prepared PDF, dialogue and decision survive refresh without a live API', async ({ page }) => {
  const liveApiResponses: string[] = [];
  const demoApiResponses: string[] = [];
  page.on('response', (response) => {
    if (/\/(?:api|v1)(?:\/|$)/u.test(new URL(response.url()).pathname)) {
      (response.fromServiceWorker() ? demoApiResponses : liveApiResponses).push(response.url());
    }
  });
  await page.goto('/demo/new');
  await expect(page.getByLabel('Демонстрационный режим')).toContainText('Выбранный файл не анализируется');
  await expect(page.getByRole('link', { name: 'Numbat' })).toBeVisible();
  await page.getByLabel('Файл документа').setInputFiles({
    name: 'arbitrary-input.txt', mimeType: 'text/plain', buffer: Buffer.from('UNRELATED FILE CONTENT MUST NOT BECOME THE REPORT'),
  });
  await expect(page.getByText('Выбран файл «arbitrary-input.txt»', { exact: false })).toBeVisible();
  await expect(page.getByText('synthetic-demo.pdf', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Запустить проверку' }).click();
  await page.getByRole('link', { name: 'Открыть отчёт' }).click();
  await expect(page.getByText('Тестовый результат', { exact: false })).toBeVisible();
  await expect(page.getByText('Страница 1', { exact: true })).toBeVisible();
  await expect(page.locator('canvas')).toHaveAttribute('width', /[1-9]\d+/u);
  const reportUrl = page.url();
  await page.getByRole('link', { name: /Не задано расписание обновления/u }).click();
  await expect(page.getByText('Страница 2', { exact: true })).toBeVisible();
  await page.getByRole('tab', { name: /Диалог/u }).click();
  await page.getByRole('textbox', { name: /Уточняющий вопрос/u }).fill('Произвольный вопрос для проверки интерфейса');
  await page.getByRole('button', { name: 'Отправить вопрос' }).click();
  await expect(page.getByText('Подготовленная формулировка', { exact: true })).toBeVisible();
  await expect(page.getByText('Заранее подготовленный ответ для демонстрации', { exact: false }).first()).toBeVisible();
  await page.reload();
  await expect(page.getByText('Произвольный вопрос для проверки интерфейса', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Использовать предложение' }).click();
  await page.getByRole('radio', { name: /Подтверждено/u }).check();
  await page.getByRole('textbox', { name: 'Обоснование' }).fill('Тестовое решение сохранено локально');
  await page.getByRole('button', { name: 'Сохранить решение' }).click();
  await expect(page.getByText('Решение сохранено', { exact: false })).toBeVisible();
  await page.reload();
  await expect(page.getByText('Тестовое решение сохранено локально', { exact: true }).first()).toBeVisible();
  await page.getByRole('tab', { name: /Диалог/u }).click();
  await expect(page.getByRole('button', { name: 'Отправить вопрос' })).toBeDisabled();
  await page.goto(reportUrl);
  await expect(page.getByText(data.report.summary, { exact: true })).toBeVisible();
  await page.getByRole('link', { name: /Не определено поведение при повторной загрузке/u }).click();
  await page.getByRole('tab', { name: /Диалог/u }).click();
  await expect(page.getByText('Произвольный вопрос для проверки интерфейса', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('textbox', { name: /Уточняющий вопрос/u })).toBeEnabled();

  const result = await page.evaluate(async () => {
    const unsupported = await fetch('/demo/api/v1/not-implemented');
    const accidentalLive = await fetch('/api/v1/bootstrap');
    const registrations = await navigator.serviceWorker.getRegistrations();
    return { unsupported: unsupported.status, accidentalLive: accidentalLive.status, scopes: registrations.map((item) => new URL(item.scope).pathname) };
  });
  expect(result).toEqual({ unsupported: 503, accidentalLive: 503, scopes: ['/demo/'] });
  expect(demoApiResponses.length).toBeGreaterThan(10);
  expect(liveApiResponses).toEqual([]);
  await page.screenshot({ path: 'test-results/demo-finding.png', fullPage: true });
});

test('missing private package fails closed before the application calls an API', async ({ page }) => {
  const apiRequests: string[] = [];
  page.on('request', (request) => {
    if (/\/(?:api|v1)(?:\/|$)/u.test(new URL(request.url()).pathname)) apiRequests.push(request.url());
  });
  await page.route('**/demo/data/demo.json', (route) => route.fulfill({ status: 503, body: 'Unavailable' }));
  await page.goto('/demo/new');
  await expect(page.getByRole('heading', { name: 'Деморежим недоступен' })).toBeVisible();
  await expect(page.getByText(/Модель не вызывалась/u)).toBeVisible();
  expect(apiRequests).toEqual([]);
});
