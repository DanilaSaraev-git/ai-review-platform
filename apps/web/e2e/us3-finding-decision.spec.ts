import { expect, test } from '@playwright/test';
import { openFinding, withScenario } from './helpers';

const REASON = 'Расписание действительно нужно согласовать до разработки.';

/** US3: решение человека и конфликт ревизии (SC-005, SC-006). */
test.describe('Решение по замечанию', () => {
  test('сохраняет решение и переживает обновление страницы', async ({ page }) => {
    await openFinding(page);

    await page.getByRole('radio', { name: /Подтверждено/ }).check();
    await page.getByRole('textbox', { name: 'Обоснование' }).fill(REASON);
    await page.getByRole('button', { name: 'Сохранить решение' }).click();

    await expect(page.getByText('Решение сохранено')).toBeVisible();

    await page.reload();
    await expect(page.getByText(REASON).first()).toBeVisible();
    await expect(page.getByText('Подтверждено').first()).toBeVisible();
  });

  test('не сохраняет решение без обоснования и объясняет причину', async ({ page }) => {
    await openFinding(page);

    await page.getByRole('radio', { name: /Отклонено/ }).check();
    await page.getByRole('button', { name: 'Сохранить решение' }).click();

    await expect(page.getByRole('alert')).toContainText('Укажите обоснование');
  });

  test('при конфликте ревизии не теряет ввод и предлагает повтор одним действием', async ({ page }) => {
    await withScenario(page, 'decision-conflict');
    await openFinding(page);

    await page.getByRole('radio', { name: /Подтверждено/ }).check();
    await page.getByRole('textbox', { name: 'Обоснование' }).fill(REASON);
    await page.getByRole('button', { name: 'Сохранить решение' }).click();

    await expect(page.getByRole('alert')).toContainText('Решение изменилось');
    // Введённый текст сохранён (SC-005).
    await expect(page.getByRole('textbox', { name: 'Обоснование' })).toHaveValue(REASON);
    await expect(page.getByRole('button', { name: 'Повторить с актуальной версией' })).toBeEnabled();
  });

  test('решение не изменяет отчёт', async ({ page }) => {
    await openFinding(page);

    await page.getByRole('radio', { name: /Подтверждено/ }).check();
    await page.getByRole('textbox', { name: 'Обоснование' }).fill(REASON);
    await page.getByRole('button', { name: 'Сохранить решение' }).click();
    await expect(page.getByText('Решение сохранено')).toBeVisible();

    await page.getByRole('link', { name: 'К списку замечаний' }).click();

    // Содержание отчёта прежнее (FR-018, SC-006).
    await expect(page.getByText('Найдено одно уточнение по расписанию обновления.')).toBeVisible();
    await expect(page.getByRole('link', { name: /Не задано расписание обновления/ })).toBeVisible();
    await expect(page.getByText(/разобрано 1 из 1/i)).toBeVisible();
  });
});
