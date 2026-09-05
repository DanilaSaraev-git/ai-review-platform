import { expect, test } from '@playwright/test';
import { startRun, uploadSyntheticDocument, withScenario } from './helpers';

/**
 * US1: аналитик загружает документ, запускает фоновую проверку и наблюдает
 * её состояние до терминального (SC-002, SC-009, SC-012, SC-013).
 */
test.describe('Запуск проверки загруженного ТЗ', () => {
  test('проходит путь от стартовых данных до успешного завершения', async ({ page }) => {
    await page.goto('/');

    // Рабочее пространство и лимиты видны сразу (FR-001).
    await expect(page.getByRole('heading', { name: 'Рабочее пространство' })).toBeVisible();
    await expect(page.getByText(/файл до/)).toBeVisible();

    await page.getByRole('link', { name: 'Новая проверка' }).click();
    await uploadSyntheticDocument(page);
    await startRun(page);

    // Запуск сразу отображается как поставленный в очередь (FR-013).
    await expect(page.getByRole('heading', { name: 'Состояние проверки' })).toBeVisible();

    // Состояния сменяются без действий пользователя (FR-014, SC-012).
    await expect(page.getByText('Завершено')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole('link', { name: 'Открыть отчёт' })).toBeVisible();
  });

  test('повторный запуск с теми же настройками не создаёт второй запуск', async ({ page }) => {
    await page.goto('/new');
    await uploadSyntheticDocument(page);
    await startRun(page);
    await expect(page).toHaveURL(/\/runs\/[0-9a-f-]+$/);

    // Повтор того же намерения: тот же документ, тот же профиль, тот же
    // профиль модели. Ключ идемпотентности совпадает, поэтому сервис
    // воспроизводит исходный запуск (FR-012, SC-009).
    await page.goto('/new');
    await uploadSyntheticDocument(page);
    await startRun(page);
    await expect(page).toHaveURL(/\/runs\/[0-9a-f-]+$/);

    await page.goto('/');
    await expect(page.getByRole('link', { name: /Проверка от/ })).toHaveCount(1);
  });

  test('неудачное завершение называет причину и не предлагает отчёт', async ({ page }) => {
    await withScenario(page, 'run-failed');
    await page.goto('/new');
    await uploadSyntheticDocument(page);
    await startRun(page);

    await expect(page.getByText('Не удалось')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText('Отчёт не опубликован.')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Открыть отчёт' })).toHaveCount(0);
  });

  test('документ с неудачным извлечением не даёт запустить проверку', async ({ page }) => {
    await withScenario(page, 'document-extraction-failed');
    await page.goto('/new');
    await uploadSyntheticDocument(page);

    await expect(page.getByText('Текст извлечь не удалось')).toBeVisible();
    await expect(page.getByText(/в другом виде/)).toBeVisible();
    await expect(page.getByRole('button', { name: /Запустить проверку/ })).toBeDisabled();
  });

  test('запуск без смены состояния 15 минут показывает предупреждение и длительность', async ({ page }) => {
    await withScenario(page, 'run-stalled');
    await page.goto('/new');
    await uploadSyntheticDocument(page);
    await startRun(page);

    await expect(page.getByText('Проверка идёт дольше обычного').first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/Идёт \d/)).toBeVisible();
    // Предупреждение не подменяет состояние запуска (FR-039).
    await expect(page.getByText('Идёт проверка документа')).toBeVisible();
  });

  test('запуск находится в списке после возврата на страницу', async ({ page }) => {
    await page.goto('/new');
    await uploadSyntheticDocument(page);
    await startRun(page);
    // Дожидаемся созданного запуска, иначе уход на главную обгонит ответ.
    await expect(page).toHaveURL(/\/runs\/[0-9a-f-]+$/);

    await page.goto('/');
    await expect(page.getByRole('link', { name: /Проверка от/ })).toBeVisible();
  });
});
