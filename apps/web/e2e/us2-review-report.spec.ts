import { expect, test } from '@playwright/test';
import { openReport, withScenario } from './helpers';

/**
 * US2: разбор замечаний в неизменяемом отчёте с переходом к фрагменту
 * (SC-003, SC-004, SC-010).
 */
test.describe('Разбор замечаний в неизменяемом отчёте', () => {
  test('показывает сводку, замечания, охват и источники', async ({ page }) => {
    await openReport(page);

    await expect(page.getByRole('heading', { name: 'Отчёт проверки' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Результат проверки' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Охват проверки' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Источники проверки' })).toBeVisible();
    await expect(page.getByText('Ограничения результата')).toBeVisible();
  });

  test('от замечания переходит к процитированному фрагменту документа', async ({ page }) => {
    await openReport(page);

    await page.getByRole('link', { name: /Не задано расписание обновления/ }).click();

    // Замечание показано с приоритетом и вопросом (FR-020).
    await expect(page.getByText('Вопрос для уточнения')).toBeVisible();

    // Фрагмент исходного документа виден рядом (FR-021, SC-003).
    await expect(page.getByRole('heading', { name: 'Исходный документ' })).toBeVisible();
    await expect(page.getByText('Обновление витрины выполняется регулярно.')).toBeVisible();
  });

  test('частичный охват показывает пропуски и статусы всех источников', async ({ page }) => {
    await withScenario(page, 'report-partial');
    await openReport(page);

    await expect(page.getByText('Неполный охват')).toBeVisible();
    await expect(page.getByText('Результат неполный')).toBeVisible();
    await expect(page.getByText(/Источник не удалось прочитать/)).toBeVisible();
    await expect(page.getByText('Недоступен').first()).toBeVisible();
  });

  test('пустой отчёт показан как содержательный результат', async ({ page }) => {
    await withScenario(page, 'empty-report');
    await openReport(page);

    await expect(page.getByText('Замечаний не найдено').first()).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Охват проверки' })).toBeVisible();
  });

  test('чужой идентификатор даёт «не найдено» без упоминания прав доступа', async ({ page }) => {
    await withScenario(page, 'not-found');
    await page.goto('/runs/00000000-0000-4000-8000-000000000999/report');

    await expect(page.getByRole('heading', { name: 'Не найдено' })).toBeVisible();

    const body = (await page.textContent('body')) ?? '';
    for (const forbidden of ['доступ', 'права', 'войти', 'авториз']) {
      expect(body.toLowerCase()).not.toContain(forbidden);
    }
  });

  test('у неуспешного запуска отчёт не показывается даже частично', async ({ page }) => {
    await withScenario(page, 'run-failed');
    await page.goto('/runs/60000000-0000-4000-8000-000000000002/report');

    await expect(page.getByText('Отчёта пока нет')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Замечания' })).toHaveCount(0);
  });
});
