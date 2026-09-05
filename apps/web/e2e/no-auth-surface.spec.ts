import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { openFinding, openReport, uploadSyntheticDocument, withScenario } from './helpers';

/**
 * Граница доверенного развёртывания v1 (FR-002, SC-010, принцип IV).
 * В интерфейсе нет ни одного экрана входа, регистрации и управления
 * аккаунтами, ролями или участниками.
 */
const FORBIDDEN_TEXT = [
  /войти/iu,
  /вход в систему/iu,
  /выйти/iu,
  /регистрац/iu,
  /пароль/iu,
  /участник/iu,
  /роли/iu,
  /управление аккаунт/iu,
];

async function assertNoAuthSurface(page: Page): Promise<void> {
  const body = (await page.textContent('body')) ?? '';
  for (const pattern of FORBIDDEN_TEXT) {
    expect(body).not.toMatch(pattern);
  }
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
}

test.describe('Отсутствие поверхностей авторизации', () => {
  test('на списке проверок и в подготовке запуска', async ({ page }) => {
    await page.goto('/');
    await assertNoAuthSurface(page);

    await page.goto('/new');
    await uploadSyntheticDocument(page);
    await assertNoAuthSurface(page);
  });

  test('в отчёте и при разборе замечания', async ({ page }) => {
    await openReport(page);
    await assertNoAuthSurface(page);

    await openFinding(page);
    await assertNoAuthSurface(page);
  });

  test('чужой идентификатор не упоминает прав доступа', async ({ page }) => {
    await withScenario(page, 'not-found');
    await page.goto('/runs/00000000-0000-4000-8000-000000000999');
    await expect(page.getByRole('heading', { name: 'Не найдено' })).toBeVisible();

    const body = ((await page.textContent('body')) ?? '').toLowerCase();
    expect(body).not.toContain('доступ');
    expect(body).not.toContain('права');
  });
});
