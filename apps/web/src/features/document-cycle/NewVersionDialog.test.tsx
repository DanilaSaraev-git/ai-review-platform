import { describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { getUploadDocumentVersionMockHandler } from '@/api/generated/endpoints.msw';
import { mockServer } from '@/mocks/server';
import { API } from '@/mocks/scenarios/base';
import * as fixtures from '@/mocks/fixtures';
import { renderWithProviders } from '@/test/render';
import { NewVersionDialog } from './NewVersionDialog';

describe('запуск новой версии из результата', () => {
  it('требует новый файл и запускает его только по явному нажатию', async () => {
    const create = vi.fn(), close = vi.fn();
    mockServer.use(getUploadDocumentVersionMockHandler(fixtures.documentFamilyVersion),
      http.post(`${API}/workspaces/:workspaceId/review-runs`, async ({ request }) => {
        create(await request.json()); return HttpResponse.json(fixtures.runQueued, { status: 202 });
      }));
    renderWithProviders(<NewVersionDialog workspaceId={fixtures.workspaceId} familyId={fixtures.documentFamily.id} prior={{ ...fixtures.runCompleted, context_document_ids: [] }} onClose={close} />);
    const start = screen.getByRole('button', { name: 'Проверить новую версию' });
    expect(start).toBeDisabled();
    expect(screen.queryByText('Использовать текущий файл')).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Выбрать файл' })).toBeEnabled());
    fireEvent.change(screen.getByLabelText('Файл новой версии'), { target: { files: [new File(['Synthetic revision'], 'revision.txt', { type: 'text/plain' })] } });
    await waitFor(() => expect(start).toBeEnabled());
    expect(create).not.toHaveBeenCalled();
    fireEvent.click(start);
    await waitFor(() => expect(close).toHaveBeenCalledOnce());
    expect(create.mock.calls[0]![0].document_id).toBe(fixtures.documentFamilyVersion.document.id);
  });
});
