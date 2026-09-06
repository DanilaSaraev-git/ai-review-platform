import { describe, expect, it } from 'vitest';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { MemoryRouter } from 'react-router';
import type { ReviewRun } from '@/api/generated/model';
import { runKey } from '@/api/query-keys';
import { runPollInterval } from '@/api/polling';
import { useReviewRun } from '../api/use-review-run';
import { RunStatePanel } from './RunStatePanel';
import { CancelRunControl } from './CancelRunControl';
import * as fixtures from '@/mocks/fixtures';
import { mockServer } from '@/mocks/server';
import { API, problem } from '@/mocks/scenarios/base';
import { createTestQueryClient, renderWithQueryClient } from '@/test/render';

const path = `${API}/workspaces/:workspaceId/review-runs/:runId`;
const active: ReviewRun = { ...fixtures.runQueued, state: 'reviewing' };
const cancelled: ReviewRun = { ...active, state: 'cancelled', cancel_requested_at: '2026-09-06T12:00:00Z', finished_at: '2026-09-06T12:00:00Z', report_available: false };

function ObservedRun() {
  const { run, progress } = useReviewRun(fixtures.workspaceId, active.id);
  return run ? <MemoryRouter><RunStatePanel run={run} progress={progress} /><CancelRunControl workspaceId={fixtures.workspaceId} run={run} isOffline={false} /></MemoryRouter> : null;
}

describe('Отмена проверки', () => {
  it.each(['queued', 'preparing', 'reviewing', 'validating'] as const)('доступна в состоянии %s', state => {
    renderWithQueryClient(<CancelRunControl workspaceId={fixtures.workspaceId} run={{ ...active, state }} isOffline={false} />);
    expect(screen.getByRole('button', { name: 'Отменить проверку' })).toBeEnabled();
  });

  it.each(['completed', 'failed', 'cancelled'] as const)('недоступна в состоянии %s', state => {
    renderWithQueryClient(<CancelRunControl workspaceId={fixtures.workspaceId} run={{ ...active, state }} isOffline={false} />);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('недоступна без сети', () => {
    renderWithQueryClient(<CancelRunControl workspaceId={fixtures.workspaceId} run={active} isOffline />);
    expect(screen.getByRole('button', { name: 'Отменить проверку' })).toBeDisabled();
  });

  it('ждёт подтверждения, блокирует повтор и обновляет состояние и историю', async () => {
    let respond!: () => void;
    const gate = new Promise<void>(resolve => { respond = resolve; });
    let posts = 0;
    mockServer.use(
      http.get(path, () => HttpResponse.json(active)),
      http.post(`${path}/cancel`, async ({ params }) => {
        expect(params.workspaceId).toBe(fixtures.workspaceId);
        expect(params.runId).toBe(active.id);
        posts++;
        await gate;
        return HttpResponse.json(cancelled, { status: 202 });
      }),
    );
    const cache = createTestQueryClient();
    cache.setDefaultOptions({ queries: { retry: false, gcTime: Infinity } });
    const latestKey = ['latest-family-run', fixtures.workspaceId, 'family'];
    const historyKey = ['family-runs', fixtures.workspaceId, 'family'];
    cache.setQueryData(latestKey, { items: [active] });
    cache.setQueryData(historyKey, { pages: [{ items: [active] }] });
    renderWithQueryClient(<ObservedRun />, cache);
    fireEvent.click(await screen.findByRole('button', { name: 'Отменить проверку' }));
    expect(await screen.findByRole('button', { name: 'Отменяем проверку…' })).toBeDisabled();
    expect(screen.queryByText('Отменена', { exact: true })).not.toBeInTheDocument();
    respond();
    expect(await screen.findByText('Отменена', { exact: true })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Отменить проверку' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Открыть отчёт' })).not.toBeInTheDocument();
    expect(posts).toBe(1);
    expect(cache.getQueryData(runKey(fixtures.workspaceId, active.id))).toEqual(cancelled);
    expect(runPollInterval(cancelled)).toBe(false);
    expect(cache.getQueryState(latestKey)?.isInvalidated).toBe(true);
    expect(cache.getQueryState(historyKey)?.isInvalidated).toBe(true);
  });

  it('после ошибки сохраняет активный статус и разрешает повтор', async () => {
    let fail = true;
    mockServer.use(
      http.get(path, () => HttpResponse.json(active)),
      http.post(`${path}/cancel`, () => fail ? problem(503, 'unavailable', 'Internal details') : HttpResponse.json(cancelled, { status: 202 })),
    );
    renderWithQueryClient(<ObservedRun />);
    fireEvent.click(await screen.findByRole('button', { name: 'Отменить проверку' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось подтвердить отмену');
    expect(screen.queryByText('Отменена', { exact: true })).not.toBeInTheDocument();
    expect(screen.queryByText('Internal details')).not.toBeInTheDocument();
    const button = screen.getByRole('button', { name: 'Отменить проверку' });
    await waitFor(() => expect(button).toBeEnabled());
    fail = false;
    fireEvent.click(button);
    expect(await screen.findByText('Отменена', { exact: true })).toBeVisible();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('поздний ответ опроса не возвращает отменённую проверку в работу', async () => {
    let release!: () => void;
    const gate = new Promise<void>(resolve => { release = resolve; });
    let gets = 0;
    mockServer.use(
      http.get(path, async () => {
        if (++gets > 1) await gate;
        return HttpResponse.json(active);
      }),
      http.post(`${path}/cancel`, () => HttpResponse.json(cancelled, { status: 202 })),
    );
    const cache = createTestQueryClient();
    renderWithQueryClient(<ObservedRun />, cache);
    const button = await screen.findByRole('button', { name: 'Отменить проверку' });
    const poll = cache.refetchQueries({ queryKey: runKey(fixtures.workspaceId, active.id) });
    await waitFor(() => expect(gets).toBe(2));
    fireEvent.click(button);
    expect(await screen.findByText('Отменена', { exact: true })).toBeVisible();
    await act(async () => { release(); await poll; });
    expect(cache.getQueryData<ReviewRun>(runKey(fixtures.workspaceId, active.id))?.state).toBe('cancelled');
    expect(screen.getByText('Отменена', { exact: true })).toBeVisible();
  });

  it('при гонке с завершением показывает опубликованный отчёт', async () => {
    let current = active;
    mockServer.use(
      http.get(path, () => HttpResponse.json(current)),
      http.post(`${path}/cancel`, () => {
        current = fixtures.runCompleted;
        return problem(409, 'run_terminal', 'A terminal review run cannot be cancelled.');
      }),
    );
    renderWithQueryClient(<ObservedRun />);
    fireEvent.click(await screen.findByRole('button', { name: 'Отменить проверку' }));
    expect(await screen.findByRole('link', { name: 'Открыть отчёт' })).toBeVisible();
    expect(screen.getByRole('alert')).toHaveTextContent('Проверка уже остановлена или завершена');
    expect(screen.queryByText('Отменена', { exact: true })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Отменить проверку' })).not.toBeInTheDocument();
  });
});
