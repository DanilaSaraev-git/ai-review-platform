import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { getDownloadReviewPdfMockHandler } from '@/api/generated/endpoints.msw';
import { API } from '@/mocks/scenarios/base';
import { mockServer } from '@/mocks/server';
import * as fixtures from '@/mocks/fixtures';
import { renderWithProviders } from '@/test/render';
import { DownloadPdfButton } from './DownloadPdfButton';

afterEach(() => vi.restoreAllMocks());

describe('PDF выбранной проверки', () => {
  it('скачивает PDF выбранного запуска без параметров экранного фильтра', async () => {
    let path = '';
    mockServer.use(getDownloadReviewPdfMockHandler(({ request }) => { path = request.url; return new TextEncoder().encode('%PDF-1.4').buffer; }));
    const createUrl = vi.fn(() => 'blob:synthetic-pdf');
    Object.defineProperty(URL, 'createObjectURL', { value: createUrl, configurable: true });
    Object.defineProperty(URL, 'revokeObjectURL', { value: vi.fn(), configurable: true });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    renderWithProviders(<DownloadPdfButton workspaceId={fixtures.workspaceId} runId={fixtures.runId} />, '/?priority=high');
    fireEvent.click(screen.getByRole('button', { name: 'Скачать PDF' }));
    await waitFor(() => expect(click).toHaveBeenCalledOnce());
    expect(path.endsWith(`/review-runs/${fixtures.runId}/report.pdf`)).toBe(true);
    expect(createUrl).toHaveBeenCalledOnce();
    expect((click.mock.instances[0] as HTMLAnchorElement).download).toBe(`numbat-${fixtures.runId}.pdf`);
  });

  it('показывает сетевую ошибку и позволяет повторить выгрузку', async () => {
    mockServer.use(http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/report.pdf`, () => HttpResponse.error()));
    renderWithProviders(<DownloadPdfButton workspaceId={fixtures.workspaceId} runId={fixtures.runId} />);
    fireEvent.click(screen.getByRole('button', { name: 'Скачать PDF' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось скачать PDF');
    expect(screen.getByRole('button', { name: 'Скачать PDF' })).toBeEnabled();
  });
});
