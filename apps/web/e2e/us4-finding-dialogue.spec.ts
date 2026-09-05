import { expect, test } from '@playwright/test';
import { openFinding, withScenario } from './helpers';

const QUESTION = 'Предложи проверяемую формулировку расписания для этого требования.';

/** US4: один ход диалога по замечанию (SC-007, SC-008). */
test.describe('Диалог по замечанию', () => {
  test('проводит один ход и показывает ответ с предложенной резолюцией', async ({ page }) => {
    await openFinding(page);

    await page.getByRole('textbox', { name: /Уточняющий вопрос/ }).fill(QUESTION);
    await page.getByRole('button', { name: 'Отправить вопрос' }).click();

    await expect(page.getByText(QUESTION)).toBeVisible();
    await expect(page.getByText('Предложена резолюция')).toBeVisible();
    await expect(page.getByText('Предложенная моделью формулировка')).toBeVisible();
  });

  test('во время генерации хода отправка следующего недоступна с названной причиной', async ({ page }) => {
    await withScenario(page, 'dialogue-generating');
    await openFinding(page);

    await expect(page.getByText('Предыдущий ход ещё не завершён.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Отправить вопрос' })).toBeDisabled();
    await expect(page.getByText('Ответ готовится…')).toBeVisible();
  });

  test('ход с ошибкой показывает причину и позволяет повтор без повторного ввода', async ({ page }) => {
    await withScenario(page, 'dialogue-failed');
    await openFinding(page);

    await expect(page.getByText('Ответ не получен')).toBeVisible();
    await expect(page.getByText('Профиль модели временно недоступен.').first()).toBeVisible();

    await page.getByRole('button', { name: 'Повторить ход' }).click();
    await expect(page.getByText('Предложена резолюция')).toBeVisible();
  });

  test('конфликт ревизии диалога не теряет введённый вопрос', async ({ page }) => {
    await withScenario(page, 'dialogue-conflict');
    await openFinding(page);

    await page.getByRole('textbox', { name: /Уточняющий вопрос/ }).fill(QUESTION);
    await page.getByRole('button', { name: 'Отправить вопрос' }).click();

    await expect(page.getByRole('alert')).toContainText('Диалог изменился');
    await expect(page.getByRole('textbox', { name: /Уточняющий вопрос/ })).toHaveValue(QUESTION);
    await expect(page.getByRole('button', { name: 'Повторить отправку' })).toBeEnabled();
  });

  test('предложенная резолюция становится решением только отдельным действием', async ({ page }) => {
    await openFinding(page);

    await page.getByRole('textbox', { name: /Уточняющий вопрос/ }).fill(QUESTION);
    await page.getByRole('button', { name: 'Отправить вопрос' }).click();
    await expect(page.getByText('Предложенная моделью формулировка')).toBeVisible();

    // Пока аналитик ничего не сделал, решение остаётся нерассмотренным (SC-007).
    await expect(page.getByText('Не рассмотрено').first()).toBeVisible();
    await expect(page.getByRole('textbox', { name: /Формулировка резолюции/ })).toHaveValue('');

    // Первое действие: перенос текста в форму. Решение всё ещё не сохранено.
    await page.getByRole('button', { name: 'Использовать предложение' }).click();
    await expect(page.getByRole('textbox', { name: /Формулировка резолюции/ })).not.toHaveValue('');
    await expect(page.getByText('Решение сохранено')).toHaveCount(0);

    // Второе действие: сохранение решения человеком.
    await page.getByRole('radio', { name: /Подтверждено/ }).check();
    await page.getByRole('textbox', { name: 'Обоснование' }).fill('Формулировка подходит.');
    await page.getByRole('button', { name: 'Сохранить решение' }).click();
    await expect(page.getByText('Решение сохранено')).toBeVisible();
  });
});
