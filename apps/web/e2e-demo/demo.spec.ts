import { expect, test, type Page } from '@playwright/test';
import type { DemoPackage } from '../src/mocks/demo-package';
import { installSyntheticDemoPackage } from './fixture';

let data: DemoPackage;
test.beforeAll(async () => { data = await installSyntheticDemoPackage(); });

async function expectNumbatDesign(page: Page, name: string): Promise<void> {
  const brand = page.getByRole('link', { name, exact: true });
  await expect(brand).toBeVisible();
  await expect(brand.locator('img')).toHaveAttribute('src', '/demo/numbat-icon.png');
  await expect.poll(() => brand.locator('img').evaluate((element) => (element as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  await expect(page.locator('.numbat-sidebar')).toHaveCSS('background-color', 'rgb(143, 24, 40)');
  await expect(page.locator('body')).toHaveCSS('font-family', /Onest/u);
  await expect.poll(() => page.evaluate(async () => {
    await document.fonts.ready;
    return [...document.fonts].some((font) => font.family.includes('Onest') && font.status === 'loaded');
  })).toBe(true);
}

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
  await expectNumbatDesign(page, 'Numbat — история проверок');
  await page.getByLabel('Файл документа').setInputFiles({
    name: 'arbitrary-input.txt', mimeType: 'text/plain', buffer: Buffer.from('UNRELATED FILE CONTENT MUST NOT BECOME THE REPORT'),
  });
  await expect(page.getByText('Выбран файл «arbitrary-input.txt»', { exact: false })).toBeVisible();
  await expect(page.locator('.entry-upload-title', { hasText: 'synthetic-demo.pdf' })).toBeVisible();
  await page.getByRole('button', { name: 'Запустить проверку' }).click();
  await page.getByRole('link', { name: 'Открыть отчёт' }).click();
  await expect(page.getByText('Тестовый результат', { exact: false })).toBeVisible();
  const document = page.getByTestId('document-scroll');
  await expect(document.locator('canvas')).toHaveCount(2);
  for (const pageNumber of [1, 2]) {
    await expect(document.getByLabel(`Страница ${pageNumber} исходного документа`)).toHaveAttribute('width', /[1-9]\d+/u);
  }
  await expect(document.getByRole('status')).toHaveCount(0);
  const originalViewer = await document.elementHandle();
  const originalSecondPage = await document.locator('[data-pdf-page="2"]').elementHandle();
  const reportUrl = page.url();
  await page.getByRole('link', { name: /Не задано расписание обновления/u }).click();
  await expect(document.locator('[data-pdf-page="2"] .numbat-pdf-highlight')).toHaveCount(1);
  await expect.poll(() => document.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
  // Reader input ends automatic anchor tracking without starting an animated scroll.
  await document.focus();
  await page.keyboard.press('Shift');
  await document.evaluate((element) => { element.scrollTop = 150; });
  await page.getByRole('tab', { name: /Диалог/u }).click();
  await expect(page.getByRole('heading', { name: 'Диалог по замечанию' })).toBeVisible();
  expect(await originalViewer!.evaluate((element) => element.isConnected)).toBe(true);
  expect(await originalSecondPage!.evaluate((element) => element.isConnected)).toBe(true);
  expect(await document.evaluate((element) => element.scrollTop)).toBe(150);
  await expect(document.locator('canvas')).toHaveCount(2);
  await page.getByRole('textbox', { name: /Уточняющий вопрос/u }).fill('Произвольный вопрос для проверки интерфейса');
  await page.getByRole('button', { name: 'Отправить вопрос' }).click();
  await expect(page.getByText('Подготовленная формулировка', { exact: true })).toBeVisible();
  await expect(page.getByText('Заранее подготовленный ответ для демонстрации', { exact: false }).first()).toBeVisible();
  await page.reload();
  await expect(page.getByText('Произвольный вопрос для проверки интерфейса', { exact: true })).toBeVisible();
  await expect(document.locator('canvas')).toHaveCount(2);
  await expect(document.getByRole('status')).toHaveCount(0);
  const refreshedViewer = await document.elementHandle();
  await document.focus();
  await page.keyboard.press('Shift');
  await document.evaluate((element) => { element.scrollTop = 150; });
  await page.getByRole('button', { name: 'Использовать предложение' }).click();
  await expect(page.getByRole('tab', { name: 'Решение', exact: true })).toHaveAttribute('aria-selected', 'true');
  expect(await refreshedViewer!.evaluate((element) => element.isConnected)).toBe(true);
  expect(await document.evaluate((element) => element.scrollTop)).toBe(150);
  await page.getByRole('radio', { name: /Подтверждено/u }).check();
  await page.getByRole('textbox', { name: 'Обоснование' }).fill('Тестовое решение сохранено локально');
  await page.getByRole('button', { name: 'Сохранить решение' }).click();
  await expect(page.getByText('Решение сохранено', { exact: false })).toBeVisible();
  expect(await refreshedViewer!.evaluate((element) => element.isConnected)).toBe(true);
  expect(await document.evaluate((element) => element.scrollTop)).toBe(150);
  await expect(document.locator('canvas')).toHaveCount(2);
  await page.reload();
  await expect(page.getByRole('textbox', { name: 'Обоснование' })).toHaveValue('Тестовое решение сохранено локально');
  await expect(page.getByRole('radio', { name: /Подтверждено/u })).toBeChecked();
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
  await expectNumbatDesign(page, 'Numbat');
  await expect(page.getByText(/Модель не вызывалась/u)).toBeVisible();
  expect(apiRequests).toEqual([]);
});
