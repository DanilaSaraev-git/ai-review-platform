import { beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { Route, Routes } from 'react-router';
import { http, HttpResponse } from 'msw';
import { getUploadDocumentVersionMockHandler } from '@/api/generated/endpoints.msw';
import * as fixtures from '@/mocks/fixtures';
import { mockServer } from '@/mocks/server';
import { documentCycle } from '@/mocks/scenarios/document-cycle';
import { API } from '@/mocks/scenarios/base';
import { renderWithProviders } from '@/test/render';
import { DocumentFamilyPage } from './DocumentFamilyPage';

beforeEach(() => { sessionStorage.clear(); mockServer.use(...documentCycle()); });
function renderFamily() { renderWithProviders(<Routes><Route path="/documents/:familyId" element={<DocumentFamilyPage />} /></Routes>, `/documents/${fixtures.documentFamily.id}`); }

describe('История версий документа', () => {
  it('сохраняет старые исходники и загружает следующую версию без автоматической проверки', async () => {
    let starts = 0;
    mockServer.use(
      http.post(`${API}/workspaces/:workspaceId/review-runs`, () => { starts += 1; return undefined; }),
      getUploadDocumentVersionMockHandler(() => {
        return { ...fixtures.documentFamilyVersion, version_number: 3, document: { ...fixtures.mainDocument, id: '40000000-0000-4000-8000-000000000003', filename: 'synthetic-v3.md' } };
      }),
    );
    renderFamily();
    expect(await screen.findByRole('button', { name: 'Версия 1 · synthetic-spec.md' })).toBeVisible();
    const input = screen.getByLabelText('Файл новой версии');
    fireEvent.change(input, { target: { files: [new File(['# Исправленный синтетический документ'], 'synthetic-v3.md', { type: 'text/markdown' })] } });
    fireEvent.click(screen.getByRole('button', { name: 'Загрузить новую версию' }));
    expect(await screen.findByRole('link', { name: 'Проверить версию 3' })).toHaveAttribute('href', '/new?document=40000000-0000-4000-8000-000000000003');
    expect(starts).toBe(0);
    fireEvent.click(screen.getByRole('button', { name: 'Версия 1 · synthetic-spec.md' }));
    expect(screen.getByRole('link', { name: 'Проверить версию 1' })).toBeVisible();
    expect(await within(screen.getByRole('region', { name: 'Исходный документ' })).findByText('Обновление витрины выполняется регулярно.')).toBeVisible();
  });

  it('сохраняет ключ повторной загрузки и историю при сетевой ошибке', async () => {
    const keys: string[] = [];
    mockServer.use(http.post(`${API}/workspaces/:workspaceId/document-families/:familyId/versions`, ({ request }) => {
      keys.push(request.headers.get('Idempotency-Key') ?? '');
      return HttpResponse.error();
    }));
    renderFamily();
    const input = await screen.findByLabelText('Файл новой версии');
    fireEvent.change(input, { target: { files: [new File(['# Синтетический документ'], 'synthetic-v3.md', { type: 'text/markdown' })] } });
    fireEvent.click(screen.getByRole('button', { name: 'Загрузить новую версию' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось загрузить версию');
    fireEvent.click(screen.getByRole('button', { name: 'Загрузить новую версию' }));
    await waitFor(() => expect(keys).toHaveLength(2));
    expect(keys[0]).toBeTruthy();
    expect(keys[0]).toBe(keys[1]);
    expect(screen.getByRole('button', { name: 'Версия 1 · synthetic-spec.md' })).toBeVisible();
  });

  it('явно показывает неизменность байтов новой версии', async () => {
    mockServer.use(getUploadDocumentVersionMockHandler({ ...fixtures.documentFamilyVersion, version_number: 3, unchanged_from_previous: true }));
    renderFamily();
    const input = await screen.findByLabelText('Файл новой версии');
    fireEvent.change(input, { target: { files: [new File(['# Синтетический документ'], 'synthetic-v3.md', { type: 'text/markdown' })] } });
    fireEvent.click(screen.getByRole('button', { name: 'Загрузить новую версию' }));
    expect(await screen.findByText('Содержимое совпадает с предыдущей версией.')).toBeVisible();
  });
});
