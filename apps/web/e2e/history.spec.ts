import { expect, test } from '@playwright/test';
import { withScenario } from './helpers';

test('история загружает следующую страницу по серверному cursor', async ({ page }) => {
  await withScenario(page, 'history-pagination');
  await page.goto('/');

  await expect(page.getByRole('rowheader').getByRole('link')).toHaveCount(20, { timeout: 15_000 });
  await page.getByRole('button', { name: 'Показать ещё' }).click();
  await expect(page.getByRole('rowheader').getByRole('link')).toHaveCount(21);
  await expect(page.getByRole('button', { name: 'Показать ещё' })).toHaveCount(0);
});

test('ошибка истории предлагает рабочий повтор', async ({ page }) => {
  await withScenario(page, 'history-error');
  await page.goto('/');

  await expect(page.getByText('Не удалось загрузить проверки')).toBeVisible({ timeout: 15_000 });
  await page.getByRole('button', { name: 'Повторить' }).click();
  await expect(page.getByRole('rowheader').getByRole('link')).toHaveCount(1);
});
