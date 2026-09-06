import { expect, test } from '@playwright/test';
import path from 'node:path';

const runId = process.env.LIVE_RUN_ID;
const findingId = process.env.LIVE_FINDING_ID;

test('реальный API открывает историю, отчёт и адресуемый диалог', async ({ page }) => {
  test.skip(!runId || !findingId, 'LIVE_RUN_ID and LIVE_FINDING_ID are required');
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Проверки', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: /Проверка от/ }).first()).toBeVisible();

  await page.goto('/new');
  await expect(page.getByText('Параметры проверки', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Запустить проверку' })).toBeDisabled();

  await page.goto(`/runs/${runId}/report`);
  await expect(page.getByRole('heading', { name: 'Результат проверки' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Исходный документ' })).toBeVisible();

  await page.goto(`/runs/${runId}/report/findings/${findingId}/dialogue`);
  await expect(page.getByRole('tab', { name: /Диалог/ })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('heading', { name: 'Диалог по замечанию' })).toBeVisible();
  await expect(page.locator('ol > li').first()).toBeVisible();

  await page.getByRole('tab', { name: 'Решение' }).click();
  await expect(page.getByRole('radio', { name: /Принято к доработке/ })).toBeChecked();
  await expect(page.getByRole('button', { name: 'Сбросить решение' })).toBeVisible();
});

test('реальный API проходит upload → review → dialogue → decision → reload', async ({ page }) => {
  test.skip(process.env.LIVE_WRITE !== '1', 'LIVE_WRITE=1 is required for the isolated synthetic API');

  await page.goto('/new');
  await page.getByLabel('Файл документа').setInputFiles(
    path.resolve('../..', 'tests/fixtures/synthetic-review/synthetic-spec.md'),
  );
  await expect(page.getByText('synthetic-spec.md', { exact: true })).toBeVisible();

  const start = page.getByRole('button', { name: 'Запустить проверку' });
  await expect(start).toBeEnabled();
  await start.click();
  await expect(page.getByText('Завершено')).toBeVisible({ timeout: 30_000 });
  await page.getByRole('link', { name: 'Открыть отчёт' }).click();
  await expect(page.getByRole('heading', { name: 'Результат проверки' })).toBeVisible();

  const firstFinding = page.locator('section[aria-labelledby="findings-title"] a').first();
  await expect(firstFinding).toBeVisible();
  await firstFinding.click();
  await page.getByRole('tab', { name: /Диалог/ }).click();
  await page.getByRole('textbox', { name: /уточняющий вопрос/i }).fill('Clarify the retry limit.');
  await page.getByRole('button', { name: 'Отправить', exact: true }).click();
  await expect(page.locator('ol > li').first()).toBeVisible({ timeout: 30_000 });

  await page.getByRole('tab', { name: 'Решение' }).click();
  await page.getByRole('radio', { name: /Принято к доработке/ }).check();
  const reason = 'Подтверждено сквозной проверкой интерфейса и API.';
  await page.getByRole('textbox', { name: 'Обоснование' }).fill(reason);
  await page.getByRole('button', { name: 'Сохранить решение' }).click();
  await expect(page.getByText('Решение сохранено')).toBeVisible();

  await page.reload();
  await expect(page.getByRole('radio', { name: /Принято к доработке/ })).toBeChecked();
  await expect(page.getByRole('textbox', { name: 'Обоснование' })).toHaveValue(reason);
});
