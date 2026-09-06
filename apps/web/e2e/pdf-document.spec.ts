import { expect, test } from '@playwright/test';
import { withScenario } from './helpers';

const runPath = '/runs/60000000-0000-4000-8000-000000000001';

test('PDF.js отображает обе страницы и сохраняет canvas при переходе к замечанию и вкладкам', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const pageErrors: string[] = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  await withScenario(page, 'pdf-document');
  await page.goto(`${runPath}/report`);

  const document = page.getByTestId('document-scroll');
  await expect(document.locator('canvas')).toHaveCount(2);
  await expect(page.getByText(/Отрисовываем страницу/u)).toHaveCount(0);
  const canvases = await document.locator('canvas').elementHandles();
  for (const canvas of canvases) {
    // Non-white painted pixels verify real rendering, rather than only canvas mounting.
    await expect.poll(() => canvas.evaluate((element) => {
      if (!(element instanceof HTMLCanvasElement)) return false;
      const context = element.getContext('2d');
      if (!context || element.width < 500 || element.height < 500) return false;
      const pixels = context.getImageData(0, 0, element.width, element.height).data;
      for (let index = 0; index < pixels.length; index += 64) {
        if (pixels[index + 3]! > 0 && pixels[index]! < 100 && pixels[index + 1]! < 100 && pixels[index + 2]! < 100) return true;
      }
      return false;
    })).toBe(true);
  }

  const originalDocument = await document.elementHandle();
  await page.getByRole('link', { name: /Не задано расписание обновления/u }).click();
  await expect(document.locator('[data-pdf-page="2"] .numbat-pdf-highlight')).toHaveCount(1);
  await expect.poll(() => document.evaluate((element) => element.scrollTop)).toBeGreaterThan(200);
  await document.evaluate((element) => { element.scrollTop = 200; });

  await page.getByRole('tab', { name: /Диалог/u }).click();
  await expect(page.getByRole('heading', { name: 'Диалог по замечанию' })).toBeVisible();
  expect(await originalDocument?.evaluate((element) => element.isConnected)).toBe(true);
  expect(await document.evaluate((element) => element.scrollTop)).toBe(200);

  await page.getByRole('tab', { name: 'Решение', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Ваше решение' })).toBeVisible();
  expect(await document.evaluate((element) => element.scrollTop)).toBe(200);
  for (const canvas of canvases) expect(await canvas.evaluate((element) => element.isConnected)).toBe(true);
  expect(pageErrors).toEqual([]);
});
