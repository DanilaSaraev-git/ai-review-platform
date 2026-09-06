import { expect, test } from '@playwright/test';
import { startRun, uploadSyntheticDocument, withScenario } from './helpers';

/**
 * US1: аналитик загружает документ, запускает фоновую проверку и наблюдает
 * её состояние до терминального (SC-002, SC-009, SC-012, SC-013).
 */
test.describe('Запуск проверки загруженного ТЗ', () => {
  test('без подключённой модели объясняет причину у главного действия', async ({ page }) => {
    await withScenario(page, 'model-unconfigured');
    await page.goto('/new');

    await expect(page.getByText('Модель ещё не подключена')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Запустить проверку' })).toBeDisabled();
  });

  test('проходит путь от стартовых данных до успешного завершения', async ({ page }) => {
    await page.goto('/');

    // Имя пространства видно сразу, вторичные лимиты раскрываются по запросу (FR-001).
    await expect(page.getByText('Команда витрин', { exact: true }).first()).toBeVisible();
    await page.getByText('Команда витрин', { exact: true }).first().click();
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

  test('новое намерение с теми же настройками создаёт отдельный запуск', async ({ page }) => {
    await page.goto('/new');
    await uploadSyntheticDocument(page);
    await startRun(page);
    await expect(page).toHaveURL(/\/runs\/[0-9a-f-]+$/);

    // Новая открытая форма — новое намерение (SpecKit 009). Сетевые повторы
    // внутри одной формы сохраняют ключ; одинаковые параметры новой формы
    // больше не возвращают навсегда прежний запуск.
    await page.goto('/new');
    await uploadSyntheticDocument(page);
    await startRun(page);
    await expect(page).toHaveURL(/\/runs\/[0-9a-f-]+$/);

    await page.goto('/');
    await expect(page.getByRole('link', { name: /Проверка от/ })).toHaveCount(2);
  });

  test('неудачное завершение называет причину и не предлагает отчёт', async ({ page }) => {
    await withScenario(page, 'run-failed');
    await page.goto('/new');
    await uploadSyntheticDocument(page);
    await startRun(page);

    await expect(page.getByText('Не удалось')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText('Отчёт не опубликован.', { exact: true })).toBeVisible();
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
