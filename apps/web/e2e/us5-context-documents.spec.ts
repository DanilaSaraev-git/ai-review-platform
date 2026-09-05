import { expect, test } from '@playwright/test';
import { SYNTHETIC_SPEC, startRun, uploadSyntheticDocument, withScenario } from './helpers';

/** US5: контекстные материалы и частичный охват (SC-004). */
test.describe('Контекстные материалы', () => {
  test('подключает контекст отдельно от основного документа и показывает остаток лимита', async ({ page }) => {
    await page.goto('/new');
    await uploadSyntheticDocument(page);

    await expect(page.getByRole('heading', { name: 'Контекстные материалы' })).toBeVisible();
    await expect(page.getByText(/Подключено 0 из \d+/)).toBeVisible();

    await page
      .getByLabel('Файл контекстного материала')
      .setInputFiles({ name: 'synthetic-rules.md', mimeType: 'text/markdown', buffer: Buffer.from(SYNTHETIC_SPEC) });

    await expect(page.getByText(/Подключено 1 из \d+/)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Отключить' })).toBeVisible();
  });

  test('недоступный контекст даёт частичный отчёт, а не неудачный запуск', async ({ page }) => {
    await withScenario(page, 'context-partial');
    await page.goto('/new');
    await uploadSyntheticDocument(page);

    await page
      .getByLabel('Файл контекстного материала')
      .setInputFiles({ name: 'synthetic-rules.md', mimeType: 'text/markdown', buffer: Buffer.from(SYNTHETIC_SPEC) });

    await startRun(page);
    await page.getByRole('link', { name: 'Открыть отчёт' }).click({ timeout: 20_000 });

    // Запуск успешен, но результат честно помечен неполным (US5-4).
    await expect(page.getByText('Неполный охват')).toBeVisible();
    await expect(page.getByText(/Источник контекста не удалось извлечь/)).toBeVisible();
    await expect(page.getByText('Контекст').first()).toBeVisible();
    await expect(page.getByText('Недоступен').first()).toBeVisible();
  });

  test('основной документ с неудачным извлечением не даёт запустить проверку', async ({ page }) => {
    await withScenario(page, 'document-extraction-failed');
    await page.goto('/new');
    await uploadSyntheticDocument(page);

    await expect(page.getByRole('button', { name: /Запустить проверку/ })).toBeDisabled();
  });
});
