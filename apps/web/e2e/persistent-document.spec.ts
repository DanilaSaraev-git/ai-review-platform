import { expect, test } from '@playwright/test';
import { withScenario } from './helpers';

const runPath = '/runs/60000000-0000-4000-8000-000000000001';

test('основной документ не размонтируется и сохраняет прокрутку при ходе проверки, разборе, диалоге и решении', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await withScenario(page, 'persistent-document');
  await page.goto(runPath);
  const document = page.getByTestId('document-scroll');
  await expect(document.getByText('Синтетический раздел 200. Описание поля и правила загрузки.')).toBeAttached();
  const originalViewer = await document.elementHandle();
  await document.evaluate((element) => { element.scrollTop = 600; });
  await page.getByRole('link', { name: 'Открыть отчёт' }).click();
  await expect(page.getByRole('heading', { name: 'Результат проверки' })).toBeVisible();
  expect(await originalViewer?.evaluate((element) => element.isConnected)).toBe(true);
  expect(await document.evaluate((element) => element.scrollTop)).toBe(600);

  await page.getByRole('link', { name: /Не задано расписание обновления/ }).click();
  await expect(document.locator('[data-line="100"]')).toHaveAttribute('data-highlighted', 'true');
  await expect.poll(() => document.evaluate((element) => element.scrollTop)).toBeGreaterThan(1000);
  expect(await page.evaluate(() => window.scrollY)).toBe(0);

  await document.evaluate((element) => { element.scrollTop = 800; });
  await page.getByRole('tab', { name: /Диалог/ }).click();
  await expect(page.getByRole('heading', { name: 'Диалог по замечанию' })).toBeVisible();
  expect(await originalViewer?.evaluate((element) => element.isConnected)).toBe(true);
  expect(await document.evaluate((element) => element.scrollTop)).toBe(800);

  await page.getByRole('tab', { name: 'Решение', exact: true }).click();
  await page.getByRole('radio', { name: /Подтверждено/ }).check();
  await page.getByRole('textbox', { name: 'Обоснование' }).fill('В синтетическом ТЗ требуется точное расписание.');
  await page.getByRole('button', { name: 'Сохранить решение' }).click();
  await expect(page.getByText('Решение сохранено')).toBeVisible();
  expect(await document.evaluate((element) => element.scrollTop)).toBe(800);
  await page.getByRole('link', { name: 'К списку замечаний' }).click();
  expect(await originalViewer?.evaluate((element) => element.isConnected)).toBe(true);
  expect(await document.evaluate((element) => element.scrollTop)).toBe(800);
});

test('на узком экране полный документ и панель имеют отдельную прокрутку и остаются в viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await withScenario(page, 'persistent-document');
  await page.goto(`${runPath}/report`);
  const document = page.getByTestId('document-scroll');
  const panel = page.getByRole('complementary', { name: 'Панель разбора' });
  await expect(document).toBeVisible();
  await expect(panel).toBeVisible();
  const documentBox = await document.boundingBox();
  const panelBox = await panel.boundingBox();
  expect(documentBox && panelBox && documentBox.y + documentBox.height <= panelBox.y).toBeTruthy();
  expect(panelBox && panelBox.y + panelBox.height <= 845).toBeTruthy();
  await document.evaluate((element) => { element.scrollTop = element.scrollHeight; });
  await expect(document.getByText('Синтетический раздел 200. Описание поля и правила загрузки.')).toBeVisible();
  expect(await page.evaluate(() => window.document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test('вкладки замечания переключаются клавиатурой и сохраняют документ', async ({ page }) => {
  await withScenario(page, 'persistent-document');
  await page.goto(`${runPath}/report`);
  await page.getByRole('link', { name: /Не задано расписание обновления/ }).click();
  const decision = page.getByRole('tab', { name: 'Решение', exact: true });
  const dialogue = page.getByRole('tab', { name: /Диалог/ });
  await decision.focus();
  await page.keyboard.press('ArrowRight');
  await expect(dialogue).toBeFocused();
  await expect(dialogue).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('tabpanel', { name: /Диалог/ })).toBeVisible();
  await expect(page).toHaveURL(/\/dialogue$/);
  await page.keyboard.press('Home');
  await expect(decision).toBeFocused();
  await expect(page.getByRole('tabpanel', { name: 'Решение', exact: true })).toBeVisible();
  await page.keyboard.press('End');
  await expect(dialogue).toBeFocused();
  await page.keyboard.press('ArrowLeft');
  await expect(decision).toBeFocused();
  await expect(page.getByTestId('document-scroll')).toBeVisible();
});
