import { describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { getGetReviewRunMockHandler, getListModelProfilesMockHandler } from '@/api/generated/endpoints.msw';
import type { CreateReviewRun } from '@/api/generated/model';
import * as fixtures from '@/mocks/fixtures';
import { mockServer } from '@/mocks/server';
import { API } from '@/mocks/scenarios/base';
import { renderWithProviders } from '@/test/render';
import { NewReviewPage } from './NewReviewPage';

describe('Повтор сохранённой проверки', () => {
  it('открывает документ и параметры без загрузки, запускает только по явному действию', async () => {
    const created = vi.fn();
    mockServer.use(
      getGetReviewRunMockHandler(fixtures.runCompleted),
      http.post(`${API}/workspaces/:workspaceId/review-runs`, async ({ request }) => {
        created(await request.json());
        return HttpResponse.json(fixtures.runQueued, { status: 202 });
      }),
    );
    renderWithProviders(<NewReviewPage />, `/new?repeat=${fixtures.runId}`);
    expect(await screen.findByRole('region', { name: 'Исходный документ' }, { timeout: 5000 })).toBeVisible();
    const start = await screen.findByRole('button', { name: /Запустить проверку/u });
    await waitFor(() => expect(start).toBeEnabled());
    expect(created).not.toHaveBeenCalled();
    expect(screen.queryByLabelText('Файл документа')).not.toBeInTheDocument();
    fireEvent.click(start);
    await waitFor(() => expect(created).toHaveBeenCalledOnce());
    const body = created.mock.calls[0]![0] as CreateReviewRun;
    expect(body.document_id).toBe(fixtures.mainDocument.id);
    expect(body.profile).toEqual({ id: fixtures.reviewProfiles[0]!.id, version: fixtures.reviewProfiles[0]!.version });
  });

  it('разрешает выбрать доступную модель, если прежняя недоступна', async () => {
    mockServer.use(
      getGetReviewRunMockHandler(fixtures.runFailed),
      getListModelProfilesMockHandler({ items: [{ ...fixtures.modelProfiles[0]!, id: 'replacement-model', availability: 'available' }] }),
    );
    renderWithProviders(<NewReviewPage />, `/new?repeat=${fixtures.runFailed.id}`);
    expect(await screen.findByText(/Прежняя модель недоступна/u)).toBeVisible();
    await waitFor(() => expect(screen.getByRole('button', { name: /Запустить проверку/u })).toBeEnabled());
  });

  it('сохраняет ключ сетевого повтора и выдаёт новый ключ новому намеренному запуску', async () => {
    const keys: string[] = [];
    mockServer.use(
      getGetReviewRunMockHandler(fixtures.runCompleted),
      http.post(`${API}/workspaces/:workspaceId/review-runs`, ({ request }) => {
        keys.push(request.headers.get('Idempotency-Key') ?? '');
        return HttpResponse.error();
      }),
    );
    const first = renderWithProviders(<NewReviewPage />, `/new?repeat=${fixtures.runId}`);
    await screen.findByRole('region', { name: 'Исходный документ' }, { timeout: 5000 });
    await waitFor(() => expect(screen.getByRole('button', { name: /Запустить проверку/u })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /Запустить проверку/u }));
    await screen.findByText('Не удалось создать проверку');
    fireEvent.click(screen.getByRole('button', { name: /Запустить проверку/u }));
    await waitFor(() => expect(keys).toHaveLength(2));
    expect(keys[0]).toBe(keys[1]);
    first.unmount();
    renderWithProviders(<NewReviewPage />, `/new?repeat=${fixtures.runId}`);
    await screen.findByRole('region', { name: 'Исходный документ' }, { timeout: 5000 });
    await waitFor(() => expect(screen.getByRole('button', { name: /Запустить проверку/u })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /Запустить проверку/u }));
    await waitFor(() => expect(keys).toHaveLength(3));
    expect(keys[2]).not.toBe(keys[0]);
  });
});
