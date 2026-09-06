import { expect, test } from '@playwright/test';
import { withScenario } from './helpers';

const runId = '60000000-0000-4000-8000-000000000002';

test.beforeEach(async ({ page }) => { await withScenario(page, 'document-cycle'); });

test('документ → новая версия → отдельный запуск → повтор без файла', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/documents');
  await page.getByRole('link', { name: 'synthetic-spec.md', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Версии и проверки' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Исходный документ' })).toBeVisible();
  await page.getByLabel('Файл новой версии').setInputFiles({ name: 'synthetic-v3.md', mimeType: 'text/markdown', buffer: Buffer.from('# Синтетическое ТЗ v3\nПроверка версии.') });
  await page.getByRole('button', { name: 'Загрузить новую версию' }).click();
  await expect(page.getByRole('button', { name: 'Версия 3 · synthetic-v3.md' })).toBeVisible();
  await expect(page.getByText('Проверка версии.', { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('document-family-desktop.png'), fullPage: false });
  await page.getByRole('link', { name: 'Проверить версию 3' }).click();
  await expect(page.getByRole('button', { name: /Запустить проверку/u })).toBeEnabled();
  await expect(page.getByLabel('Файл документа')).toHaveCount(0);
  await page.getByRole('button', { name: /Запустить проверку/u }).click();
  await expect(page).toHaveURL(/\/runs\//u);
  const firstRun = page.url();
  await page.getByRole('link', { name: 'Проверить повторно', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Повторная проверка' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Исходный документ' })).toBeVisible();
  await page.getByRole('button', { name: /Запустить проверку/u }).click();
  await expect(page).toHaveURL(/\/runs\//u);
  expect(page.url()).not.toBe(firstRun);
});

test('сравнение сохраняет исходник, подтверждение аналитика и ручную связь', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`/runs/${runId}/report`);
  const document = page.getByRole('region', { name: 'Исходный документ' });
  await expect(document).toBeVisible();
  await document.evaluate((node) => { node.setAttribute('data-cycle-preserved', 'yes'); });
  await page.getByRole('link', { name: 'Изменения замечаний', exact: true }).click();
  await expect(document).toHaveAttribute('data-cycle-preserved', 'yes');
  await expect(page.getByText(/Обнаружено снова/u)).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('document-cycle-desktop.png'), fullPage: false });
  const absent = page.getByRole('article', { name: 'Нет обработки пустого источника' });
  await expect(absent.getByRole('button', { name: 'Подтвердить исправление' })).toBeDisabled();
  await absent.getByLabel('Пояснение к исправлению').fill('Проверил обработку пустого источника в новой версии.');
  await absent.getByRole('button', { name: 'Подтвердить исправление' }).click();
  await expect(absent.getByText('Исправление подтверждено аналитиком')).toBeVisible();
  const current = page.getByRole('article', { name: 'Не описано удаление данных' });
  await current.getByText('Исправить связь замечаний').click();
  await current.getByLabel('Предыдущая проблема').selectOption('91000000-0000-4000-8000-000000000005');
  await current.getByRole('button', { name: 'Связать', exact: true }).click();
  await expect(current.getByText(/Повторилось/u)).toBeVisible();
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
  await page.getByRole('link', { name: 'Изменения замечаний', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Изменения замечаний' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  for (const link of await page.getByRole('navigation', { name: 'Основные разделы' }).getByRole('link').all()) {
    const box = await link.boundingBox();
    expect(box && box.x >= 0 && box.x + box.width <= 390).toBe(true);
  }
  await page.screenshot({ path: testInfo.outputPath('document-cycle-mobile.png'), fullPage: false });
});
