import { expect, test } from '@playwright/test';

test('full synthetic cycle survives refresh and never reaches a live API', async ({ page }) => {
  const liveApiResponses: string[] = [];
  page.on('response', response => {
    if (/\/(?:api|v1)(?:\/|$)/u.test(new URL(response.url()).pathname) && !response.fromServiceWorker()) liveApiResponses.push(response.url());
  });
  await page.goto('/demo/new');
  await expect(page.getByLabel('Демонстрационный режим')).toContainText('без модели');
  await page.getByRole('button', { name: 'Взять демофайл', exact: true }).click();
  await page.getByRole('button', { name: 'Запустить проверку', exact: true }).click();
  await page.getByRole('link', { name: 'Открыть отчёт', exact: true }).click();
  await page.getByRole('link', { name: 'Продолжить разбор', exact: true }).click();
  await page.getByRole('tab', { name: 'Диалог', exact: true }).click();
  await expect(page.getByRole('tabpanel', { name: 'Диалог' })).toContainText('С какой периодичностью');
  await page.getByRole('textbox', { name: 'Ответ или уточняющий вопрос по замечанию' }).fill('Уточним расписание');
  await page.getByRole('button', { name: 'Отправить', exact: true }).click();
  await expect(page.getByRole('tabpanel', { name: 'Диалог' })).toContainText('ежедневно в 06:00');
  await page.reload();
  await expect(page.getByRole('tabpanel', { name: 'Диалог' })).toContainText('Уточним расписание');
  await page.getByRole('tab', { name: 'Решение', exact: true }).click();
  for (let index = 0; index < 2; index++) {
    await page.getByRole('radio', { name: 'Принято к доработке', exact: true }).check();
    await page.getByRole('textbox', { name: 'Обоснование', exact: true }).fill('Внесём согласованные правки');
    await page.getByRole('button', { name: 'Сохранить решение', exact: true }).click();
    await expect(page.getByRole('status')).toContainText('Решение сохранено');
    if (index === 0) await page.getByRole('link', { name: 'Следующее замечание →', exact: true }).click();
  }
  await page.getByRole('button', { name: 'Загрузить новую версию', exact: true }).click();
  await expect(page.getByText('Использовать текущий файл', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Взять демоверсию с правками', exact: true }).click();
  await page.getByRole('button', { name: 'Проверить новую версию', exact: true }).click();
  await page.getByRole('link', { name: 'Открыть отчёт', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Подтвердите исправления: 2', exact: true })).toBeVisible();
  for (const title of ['Не задано расписание обновления', 'Не определён срок хранения обращений']) {
    const card = page.getByRole('article', { name: title, exact: true });
    await card.getByRole('textbox', { name: 'Пояснение к исправлению' }).fill('Проверено в исходнике версии 2');
    await card.getByRole('button', { name: 'Подтвердить исправление', exact: true }).click();
  }
  await page.getByRole('button', { name: 'Завершить проверку', exact: true }).click();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Проверка завершена', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'История', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'История проверки' })).toContainText('Версия 1');
  await expect(page.getByRole('dialog', { name: 'История проверки' })).toContainText('Версия 2');
  const status = await page.evaluate(async () => [
    (await fetch('/demo/api/v1/not-implemented')).status,
    (await fetch('/api/v1/bootstrap')).status,
  ]);
  expect(status).toEqual([503, 503]);
  expect(liveApiResponses).toEqual([]);
});

test('packaged synthetic demo works without private mounted data', async ({ page }) => {
  await page.route('**/demo/data/**', route => route.fulfill({ status: 503 }));
  await page.goto('/demo/');
  await expect(page.getByRole('link', { name: 'Демо — витрина обращений', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Numbat — проверки', exact: true }).locator('img')).toHaveAttribute('src', '/demo/numbat-icon.png');
});
