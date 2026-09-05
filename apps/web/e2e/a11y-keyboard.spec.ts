import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { SYNTHETIC_SPEC } from './helpers';

/**
 * Весь основной сценарий проходится с клавиатуры (FR-041, SC-014).
 * Мышь в этой проверке не используется: только Tab, стрелки, пробел и Enter.
 */
async function focusedText(page: Page): Promise<string> {
  return page.evaluate(() => document.activeElement?.textContent?.trim() ?? '');
}

/** Переход табуляцией до элемента, удовлетворяющего условию. */
async function tabUntil(
  page: Page,
  predicate: (info: { text: string; role: string | null; name: string | null }) => boolean,
  limit = 60,
): Promise<void> {
  for (let step = 0; step < limit; step += 1) {
    await page.keyboard.press('Tab');
    const info = await page.evaluate(() => {
      const element = document.activeElement;
      return {
        text: element?.textContent?.trim() ?? '',
        role: element?.getAttribute('role') ?? element?.tagName.toLowerCase() ?? null,
        name: element?.getAttribute('aria-label') ?? element?.getAttribute('name') ?? null,
      };
    });
    if (predicate(info)) {
      return;
    }
  }
  throw new Error('Нужный элемент не достижим с клавиатуры');
}

test('основной сценарий проходится только с клавиатуры', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'Новая проверка' }).waitFor();

  // Переход к созданию проверки.
  await tabUntil(page, ({ text }) => text === 'Новая проверка');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Новая проверка' })).toBeVisible();

  // Загрузка документа: поле достижимо табуляцией, файл задаётся программно,
  // поскольку системный диалог выбора файла вне управления страницы.
  await tabUntil(page, ({ role }) => role === 'input');
  await page
    .getByLabel('Файл документа')
    .setInputFiles({ name: 'synthetic-spec.md', mimeType: 'text/markdown', buffer: Buffer.from(SYNTHETIC_SPEC) });
  await expect(page.getByText('Текст извлечён')).toBeVisible();

  // Выбор профилей стрелками и пробелом.
  const reviewProfile = page.getByRole('radio').first();
  await reviewProfile.focus();
  await page.keyboard.press('Space');
  await expect(reviewProfile).toBeChecked();

  const modelProfile = page.getByRole('radio', { name: /Сбалансированный/ });
  await modelProfile.focus();
  await page.keyboard.press('Space');
  await expect(modelProfile).toBeChecked();

  // Запуск проверки с клавиатуры.
  const startButton = page.getByRole('button', { name: /Запустить проверку/ });
  await startButton.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Состояние проверки' })).toBeVisible();

  // Переход к отчёту.
  const reportLink = page.getByRole('link', { name: 'Открыть отчёт' });
  await reportLink.waitFor({ timeout: 20_000 });
  await reportLink.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Отчёт проверки' })).toBeVisible();

  // Переход к замечанию.
  const findingLink = page.getByRole('link', { name: /Не задано расписание обновления/ });
  await findingLink.focus();
  expect(await focusedText(page)).toContain('Не задано расписание');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Ваше решение' })).toBeVisible();

  // Сохранение решения с клавиатуры.
  const confirmed = page.getByRole('radio', { name: /Подтверждено/ });
  await confirmed.focus();
  await page.keyboard.press('Space');

  const reason = page.getByRole('textbox', { name: 'Обоснование' });
  await reason.focus();
  await page.keyboard.type('Уточнение нужно до передачи в разработку.');

  const saveButton = page.getByRole('button', { name: 'Сохранить решение' });
  await saveButton.focus();
  await page.keyboard.press('Enter');

  await expect(page.getByText('Решение сохранено')).toBeVisible();
});
