import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { Route, Routes } from 'react-router';
import { getListDocumentFamilyRunsMockHandler } from '@/api/generated/endpoints.msw';
import * as fixtures from '@/mocks/fixtures';
import { mockServer } from '@/mocks/server';
import { renderWithProviders } from '@/test/render';
import { DocumentFamilyPage } from './DocumentFamilyPage';

describe('совместимость ссылки на семейство', () => {
  it('открывает последний результат вместо отдельного экрана версий', async () => {
    mockServer.use(getListDocumentFamilyRunsMockHandler({ items: [fixtures.runCompleted], next_cursor: null }));
    renderWithProviders(<Routes><Route path="/documents/:familyId" element={<DocumentFamilyPage />} /><Route path="/runs/:runId/report" element={<h1>Последний результат</h1>} /></Routes>, `/documents/${fixtures.documentFamily.id}`);
    expect(await screen.findByRole('heading', { name: 'Последний результат' })).toBeVisible();
    expect(screen.queryByText('Версии и проверки')).not.toBeInTheDocument();
  });
});
