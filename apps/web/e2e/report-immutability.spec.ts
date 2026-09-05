import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { openFinding } from './helpers';

/**
 * Сквозная проверка неизменяемости отчёта (SC-006, принцип V).
 *
 * После решений и хода диалога отчёт должен совпадать сам с собой: сводка,
 * состав и формулировки замечаний, охват и происхождение результата.
 */
async function reportSnapshot(page: Page): Promise<string> {
  const summary = (await page.getByRole('heading', { name: 'Результат проверки' }).locator('..').textContent()) ?? '';
  // Берутся только неизменяемые части замечания: заголовок и поля результата.
  // Значок статуса решения накладывается на карточку, но в отчёт не входит.
  const findings = (await page.getByRole('article').locator('h3, dl').allTextContents()).join('|');
  const coverage = (await page.getByRole('heading', { name: 'Охват проверки' }).locator('..').textContent()) ?? '';
  const provenance =
    (await page.getByRole('heading', { name: 'Чем выполнена проверка' }).locator('..').textContent()) ?? '';
  // Счётчик разобранных замечаний — часть изменяемого состояния, а не отчёта.
  return [summary.replace(/разобрано \d+ из \d+/iu, ''), findings, coverage, provenance].join('\n');
}

test('решения и диалог не изменяют отчёт', async ({ page }) => {
  await openFinding(page);
  await page.getByRole('link', { name: 'К списку замечаний' }).click();
  const before = await reportSnapshot(page);

  // Один ход диалога и одно сохранённое решение.
  await page.getByRole('link', { name: /Не задано расписание обновления/ }).click();
  await page.getByRole('textbox', { name: /Уточняющий вопрос/ }).fill('Как проверить это требование?');
  await page.getByRole('button', { name: 'Отправить вопрос' }).click();
  await expect(page.getByText('Предложена резолюция')).toBeVisible();

  await page.getByRole('radio', { name: /Подтверждено/ }).check();
  await page.getByRole('textbox', { name: 'Обоснование' }).fill('Уточнение нужно до передачи в разработку.');
  await page.getByRole('button', { name: 'Сохранить решение' }).click();
  await expect(page.getByText('Решение сохранено')).toBeVisible();

  await page.getByRole('link', { name: 'К списку замечаний' }).click();
  const after = await reportSnapshot(page);

  expect(after).toBe(before);
});
