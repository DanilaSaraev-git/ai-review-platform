import { beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { http } from 'msw';
import type { PutIssueResolution, PutReviewCycleLink } from '@/api/generated/model';
import { getGetReviewCycleMockHandler } from '@/api/generated/endpoints.msw';
import * as fixtures from '@/mocks/fixtures';
import { mockServer } from '@/mocks/server';
import { API, problem } from '@/mocks/scenarios/base';
import { cycleExample, documentCycle } from '@/mocks/scenarios/document-cycle';
import { renderWithProviders } from '@/test/render';
import { ReviewCyclePanel } from './ReviewCyclePage';

beforeEach(() => {
  sessionStorage.clear();
  mockServer.use(...documentCycle());
});

function renderCycle() { renderWithProviders(<ReviewCyclePanel workspaceId={fixtures.workspaceId} runId={cycleExample.run_id} />); }

describe('Изменения замечаний и решение человека', () => {
  it('переводит коды реального backend в рабочие пояснения', async () => {
    mockServer.use(getGetReviewCycleMockHandler({ ...cycleExample, entries: [{ ...cycleExample.entries[0]!, match_basis: 'exact_unique' }], limitations: ['review_conditions_changed', 'review_coverage_incomplete', 'comparison_failed'] }));
    renderCycle();
    expect(await screen.findByText('Найдено однозначное соответствие замечаний.')).toBeVisible();
    expect(screen.getByRole('list', { name: 'Ограничения сравнения' })).toHaveTextContent('Условия проверки изменились.');
    expect(screen.queryByText('review_coverage_incomplete')).not.toBeInTheDocument();
  });
  it('разделяет шесть исходов сопоставления и не называет исчезновение исправлением', async () => {
    renderCycle();
    for (const label of ['Повторилось', 'Новое', 'Больше не обнаружено', 'Связь требует проверки', 'Не проверено', 'Обнаружено снова']) {
      expect(await screen.findByText(label, { exact: true })).toBeVisible();
    }
    expect(screen.queryByText('Исправление подтверждено аналитиком')).not.toBeInTheDocument();
    expect(await screen.findByText('Оценка перенесена из предыдущей проверки')).toBeVisible();
    expect(screen.getByText('Прежнее решение — для справки')).toBeVisible();
    expect(screen.getByRole('link', { name: 'Базовая проверка для сравнения' })).toHaveAttribute('href', `/runs/${fixtures.runId}/report`);
    expect(screen.getAllByRole('link', { name: 'Предыдущее замечание и обсуждение' })[0]).toHaveAttribute('href', `/runs/${fixtures.runId}/report/findings/${fixtures.findingId}/dialogue`);
  });

  it('подтверждает исправление только с пояснением и сохраняет его после сравнения', async () => {
    let submitted: PutIssueResolution | undefined;
    mockServer.use(http.put(`${API}/workspaces/:workspaceId/review-runs/:runId/review-cycle/issues/:issueId/resolution`, async ({ request }) => {
      submitted = await request.clone().json() as PutIssueResolution;
      return undefined;
    }));
    renderCycle();
    const entry = await screen.findByRole('article', { name: 'Нет обработки пустого источника' });
    const confirm = within(entry).getByRole('button', { name: 'Подтвердить исправление' });
    expect(confirm).toBeDisabled();
    fireEvent.change(within(entry).getByLabelText('Пояснение к исправлению'), { target: { value: 'Проверил раздел 3: обработка добавлена.' } });
    fireEvent.click(confirm);
    expect(await within(entry).findByText('Исправление подтверждено аналитиком')).toBeVisible();
    expect(submitted).toEqual({ status: 'resolved', reason: 'Проверил раздел 3: обработка добавлена.', expected_revision: 0 });
    fireEvent.click(screen.getByRole('button', { name: 'Повторить сравнение' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Повторить сравнение' })).toBeEnabled());
    expect(within(entry).getByText('Исправление подтверждено аналитиком')).toBeVisible();
    expect(within(entry).getByText('Больше не обнаружено')).toBeVisible();
  });

  it('связывает только выбранную свободную проблему и разрешает разъединить', async () => {
    const sent: PutReviewCycleLink[] = [];
    mockServer.use(http.put(`${API}/workspaces/:workspaceId/review-runs/:runId/review-cycle/links/:findingId`, async ({ request }) => {
      sent.push(await request.clone().json() as PutReviewCycleLink);
      return undefined;
    }));
    renderCycle();
    const entry = await screen.findByRole('article', { name: 'Не описано удаление данных' });
    fireEvent.click(within(entry).getByText('Исправить связь замечаний'));
    const select = within(entry).getByLabelText('Предыдущая проблема');
    expect(within(select).getAllByRole('option')).toHaveLength(3);
    fireEvent.change(select, { target: { value: cycleExample.entries[2]!.issue_id } });
    fireEvent.click(within(entry).getByRole('button', { name: 'Связать' }));
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toEqual({ previous_issue_id: cycleExample.entries[2]!.issue_id, expected_revision: cycleExample.revision });
    const linked = await screen.findByRole('article', { name: 'Не описано удаление данных' });
    expect(within(linked).getByText('Повторилось')).toBeVisible();
    fireEvent.click(within(linked).getByText('Исправить связь замечаний'));
    fireEvent.click(within(linked).getByRole('button', { name: 'Разъединить' }));
    await waitFor(() => expect(sent).toHaveLength(2));
    expect(sent[1]!.previous_issue_id).toBeNull();
  });

  it('при 409 сохраняет пояснение и требует обновить состояние', async () => {
    mockServer.use(http.put(`${API}/workspaces/:workspaceId/review-runs/:runId/review-cycle/issues/:issueId/resolution`, () => problem(409, 'revision_conflict', 'Версия изменилась')));
    renderCycle();
    const entry = await screen.findByRole('article', { name: 'Нет обработки пустого источника' });
    const field = within(entry).getByLabelText('Пояснение к исправлению');
    fireEvent.change(field, { target: { value: 'Моё пояснение' } });
    fireEvent.click(within(entry).getByRole('button', { name: 'Подтвердить исправление' }));
    expect(await within(entry).findByRole('alert')).toHaveTextContent('Состояние изменилось');
    expect(field).toHaveValue('Моё пояснение');
    expect(within(entry).getByRole('button', { name: 'Подтвердить исправление' })).toBeDisabled();
    fireEvent.click(within(entry).getByRole('button', { name: 'Обновить состояние' }));
    await waitFor(() => expect(within(entry).getByRole('button', { name: 'Подтвердить исправление' })).toBeEnabled());
  });

  it('показывает ограничения неполного сравнения и сохраняет переход к отчёту', async () => {
    mockServer.use(getGetReviewCycleMockHandler({ ...cycleExample, status: 'unavailable', limitations: ['Анализ частичный; исчезновение замечаний не установлено.'] }));
    renderCycle();
    expect(await screen.findByText('Сравнение не завершено')).toBeVisible();
    expect(screen.getByText('Анализ частичный; исчезновение замечаний не установлено.')).toBeVisible();
    expect(screen.getByRole('link', { name: 'К замечаниям' })).toHaveAttribute('href', `/runs/${cycleExample.run_id}/report`);
  });
});
