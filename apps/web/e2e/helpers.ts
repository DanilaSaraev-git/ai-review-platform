import type { Page } from '@playwright/test';

/**
 * Общие шаги E2E-проверок.
 *
 * Сценарий моков выбирается до загрузки страницы и влияет только на сетевой
 * слой: код приложения о нём не знает (принцип III). Тот же набор проверок
 * выполняется против реального backend, если сценарий не задан.
 */
export async function withScenario(page: Page, scenario: string): Promise<void> {
  await page.addInitScript((name) => {
    (globalThis as unknown as Record<string, string>).__MSW_SCENARIO__ = name;
  }, scenario);
}

/** Синтетический документ ТЗ: материалы клиента в проверках не используются. */
export const SYNTHETIC_SPEC = [
  '# Витрина обращений абонентов',
  '',
  'Обновление витрины выполняется регулярно.',
  'Источник — топик обращений; приёмник — витрина отчётности.',
].join('\n');

export async function uploadSyntheticDocument(page: Page): Promise<void> {
  await page
    .getByLabel('Файл документа')
    .setInputFiles({ name: 'synthetic-spec.md', mimeType: 'text/markdown', buffer: Buffer.from(SYNTHETIC_SPEC) });
  // Ждём карточку загруженного документа, каким бы ни было состояние
  // извлечения: негативные сценарии проверяют именно неуспешные состояния.
  await page.getByText(/\.(md|pdf|txt)$/).first().waitFor();
}

export async function selectProfiles(page: Page): Promise<void> {
  await page.getByRole('radio').first().check();
  await page.getByRole('radio', { name: /Сбалансированный/ }).check();
}

export async function startRun(page: Page): Promise<void> {
  await selectProfiles(page);
  await page.getByRole('button', { name: /Запустить проверку/ }).click();
}

/** Быстрый путь к отчёту готового запуска. */
export async function openReport(page: Page): Promise<void> {
  await page.goto('/new');
  await uploadSyntheticDocument(page);
  await startRun(page);
  await page.getByRole('link', { name: 'Открыть отчёт' }).click({ timeout: 20_000 });
}

/** Быстрый путь к разбору первого замечания отчёта. */
export async function openFinding(page: Page): Promise<void> {
  await openReport(page);
  await page.getByRole('link', { name: /Не задано расписание обновления/ }).click();
  await page.getByRole('heading', { name: 'Ваше решение' }).waitFor();
}
