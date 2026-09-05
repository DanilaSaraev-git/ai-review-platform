import { expect, test, type Page } from '@playwright/test';
import { openFinding, openReport, uploadSyntheticDocument } from './helpers';

async function expectNoPageOverflow(page: Page): Promise<void> {
  const fits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  expect(fits).toBe(true);
}

test('подготовка сохраняет главное действие в viewport 1280×720', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/new');
  await uploadSyntheticDocument(page);

  const start = page.getByRole('button', { name: /Запустить проверку/ });
  await expect(start).toBeVisible();
  const box = await start.boundingBox();
  expect(box && box.y + box.height <= 720).toBeTruthy();
  await expectNoPageOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('new-review-1280.png'), fullPage: true });
});

test('отчёт держит документ и панель рядом на 1440 px', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openReport(page);

  const document = page.getByRole('heading', { name: 'Исходный документ' });
  const panel = page.getByRole('complementary', { name: 'Панель разбора' });
  await expect(document).toBeVisible();
  await expect(panel).toBeVisible();
  const documentBox = await document.boundingBox();
  const panelBox = await panel.boundingBox();
  expect(documentBox && panelBox && documentBox.x < panelBox.x).toBeTruthy();
  await expectNoPageOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('report-1440.png'), fullPage: true });
});

test('разбор замечания сохраняет документ рядом с действиями', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openFinding(page);

  await expect(page.getByRole('heading', { name: 'Исходный документ' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Ваше решение' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Диалог по замечанию' })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('finding-dialogue-1440.png'), fullPage: true });
});

test('mobile 390 px не создаёт горизонтальную прокрутку', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/new');
  await uploadSyntheticDocument(page);

  await expectNoPageOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('new-review-mobile-390.png'), fullPage: true });
});
