import { expect, test } from '@playwright/test';
import { withScenario } from './helpers';

const runId = '60000000-0000-4000-8000-000000000002';

test.beforeEach(async ({ page }) => { await withScenario(page, 'document-cycle'); });

test('новая версия проверяется из общей карточки и сохраняет историю', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`/runs/${runId}/report`);
  await page.getByRole('button', { name: 'Загрузить новую версию' }).click();
  await page.getByLabel('Файл новой версии').setInputFiles({ name: 'synthetic-v3.md', mimeType: 'text/markdown', buffer: Buffer.from('# Синтетическое ТЗ v3\nПроверка версии.') });
  await page.getByRole('button', { name: 'Проверить новую версию' }).click();
  await expect(page).toHaveURL(/\/runs\/[0-9a-f-]+$/);
  expect(page.url()).not.toContain(runId);
  await expect(page.getByRole('region', { name: 'Исходный документ' })).toBeVisible();
  await page.getByRole('button', { name: 'История', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('heading', { name: 'Версия 3' })).toBeVisible();
  await expect(page.getByRole('dialog').getByRole('heading', { name: 'Версия 2' })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('document-family-desktop.png'), fullPage: false });
});

test('сравнение сохраняет исходник, подтверждение аналитика и ручную связь', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`/runs/${runId}/report`);
  const document = page.getByRole('region', { name: 'Исходный документ' });
  await expect(document).toBeVisible();
  await document.evaluate((node) => { node.setAttribute('data-cycle-preserved', 'yes'); });
  await page.getByRole('heading', { name: 'Проверить исправления', exact: true }).scrollIntoViewIfNeeded();
  await expect(document).toHaveAttribute('data-cycle-preserved', 'yes');
  await expect(page.getByText(/Обнаружено снова/u)).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('document-cycle-desktop.png'), fullPage: false });
  const absent = page.getByRole('article', { name: 'Нет обработки пустого источника' });
  await expect(absent.getByRole('button', { name: 'Подтвердить исправление' })).toBeDisabled();
  await absent.getByLabel('Пояснение к исправлению').fill('Проверил обработку пустого источника в новой версии.');
  await absent.getByRole('button', { name: 'Подтвердить исправление' }).click();
  await expect(absent.getByText('Исправление подтверждено аналитиком')).toBeVisible();
  const current = page.getByRole('article', { name: 'Не определён ключ записи' });
  await current.getByText('Исправить связь замечаний').click();
  await current.getByLabel('Предыдущая проблема').selectOption('91000000-0000-4000-8000-000000000005');
  await current.getByRole('button', { name: 'Связать', exact: true }).click();
  await expect(current).toHaveCount(0); // После ручного подтверждения связь больше не требует проверки.
  await page.reload();
  await expect(page.getByRole('article', { name: 'Нет обработки пустого источника' }).getByText('Исправление подтверждено аналитиком')).toBeVisible();
});

test('PDF относится к выбранной проверке; узкий экран сохраняет документ', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/runs/${runId}/report`);
  await expect(page.getByRole('region', { name: 'Исходный документ' })).toBeVisible();
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Скачать PDF' }).click();
  expect((await downloaded).suggestedFilename()).toBe(`numbat-${runId}.pdf`);
  await page.getByRole('heading', { name: 'Проверить исправления', exact: true }).scrollIntoViewIfNeeded();
  await expect(page.getByRole('heading', { name: 'Проверить исправления' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  for (const link of await page.getByRole('navigation', { name: 'Основные разделы' }).getByRole('link').all()) {
    const box = await link.boundingBox();
    expect(box && box.x >= 0 && box.x + box.width <= 390).toBe(true);
  }
  await page.screenshot({ path: testInfo.outputPath('document-cycle-mobile.png'), fullPage: false });
});
