import { expect, test } from '@playwright/test';
import { withScenario } from './helpers';
import run from '../../../contracts/review-platform/v1/examples/http/review-run.queued.json' with { type: 'json' };

test('отмена видна в результате, истории и списке после перезагрузки', async ({ page }, testInfo) => {
  await withScenario(page, 'run-cancellable');
  await page.goto(`/runs/${run.id}`);
  await expect(page.getByRole('button', { name: 'Отменить проверку' })).toBeEnabled();
  await page.screenshot({ path: testInfo.outputPath('before-cancel.png'), fullPage: true });
  await page.getByRole('button', { name: 'Отменить проверку' }).click();
  await expect(page.getByText(/Отменена$/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Отменить проверку' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Открыть отчёт' })).toHaveCount(0);
  await page.reload();
  await expect(page.getByText(/Отменена$/)).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('after-cancel.png'), fullPage: true });
  await page.getByRole('button', { name: 'История', exact: true }).click();
  await expect(page.getByRole('dialog').getByText(/Отменена/)).toBeVisible();
  await page.getByRole('button', { name: 'Закрыть историю' }).click();
  await page.getByRole('link', { name: 'Проверки', exact: true }).last().click();
  await expect(page.getByRole('cell', { name: 'Отменена', exact: true })).toBeVisible();
});
