import { expect, test, type Page } from '@playwright/test';
import { openFinding, openReport, uploadSyntheticDocument, withScenario } from './helpers';

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

test('длинная панель отчёта скроллится внутри workspace на 1280×720', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await withScenario(page, 'report-long');
  await openReport(page);

  const panel = page.getByRole('complementary', { name: 'Панель разбора' });
  // The workspace is already mounted while the report request is still loading.
  const scrollArea = panel.locator('.numbat-panel-scroll');
  await expect(scrollArea).toBeVisible();
  await expect.poll(() => scrollArea.evaluate((element) => element.scrollHeight > element.clientHeight)).toBe(true);
  await page.getByRole('heading', { name: 'Чем выполнена проверка' }).scrollIntoViewIfNeeded();
  await expect.poll(() => scrollArea.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
});

test('разбор замечания сохраняет документ рядом с действиями', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openFinding(page);
  await page.getByRole('tab', { name: /Диалог/ }).click();

  await expect(page.getByRole('heading', { name: 'Исходный документ' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Диалог по замечанию' })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('finding-dialogue-1440.png'), fullPage: true });
});

test('mobile 390 px не создаёт горизонтальную прокрутку', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/new');
  await uploadSyntheticDocument(page);

  await expectNoPageOverflow(page);
  const uploadedName = page.locator('.entry-upload-title', { hasText: 'synthetic-spec.md' });
  await expect(uploadedName).toBeVisible();
  // Keep the filename readable instead of squeezing it between the icon and action.
  await expect.poll(() => uploadedName.evaluate((element) => element.getBoundingClientRect().width)).toBeGreaterThanOrEqual(160);
  await expect.poll(() => uploadedName.evaluate((element) => element.getBoundingClientRect().height)).toBeLessThan(50);
  await page.screenshot({ path: testInfo.outputPath('new-review-mobile-390.png'), fullPage: true });
});

test('отчёт на mobile сохраняет чтение документа и закрытые details', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openReport(page);

  await expectNoPageOverflow(page);
  await expect(page.locator('details[open]')).toHaveCount(0);
  await page.getByRole('heading', { name: 'Чем выполнена проверка' }).scrollIntoViewIfNeeded();
  await expect(page.getByText('Осталось рассмотреть: 1', { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('report-mobile-390.png'), fullPage: true });
});

test('диалог замечания на mobile остаётся привязан к документу', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openFinding(page);
  await page.getByRole('tab', { name: /Диалог/ }).click();

  await expectNoPageOverflow(page);
  await expect(page.locator('details[open]')).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('finding-dialogue-mobile-390.png'), fullPage: true });
});
