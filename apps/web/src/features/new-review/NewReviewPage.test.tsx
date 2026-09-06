import { describe, expect, it } from 'vitest';
import { fireEvent, screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { getUploadDocumentMockHandler } from '@/api/generated/endpoints.msw';
import * as fixtures from '@/mocks/fixtures';
import { API } from '@/mocks/scenarios/base';
import { mockServer } from '@/mocks/server';
import { renderWithProviders } from '@/test/render';
import { NewReviewPage } from './NewReviewPage';

describe('Подготовка проверки с открытым основным документом', () => {
  it('сохраняет полный документ при открытии контекста и параметров модели', async () => {
    renderWithProviders(<NewReviewPage />, '/new');
    const input = await screen.findByLabelText('Файл документа');
    fireEvent.change(input, {
      target: { files: [new File([fixtures.mainDocumentText], 'synthetic-spec.md', { type: 'text/markdown' })] },
    });

    const document = await screen.findByRole('region', { name: 'Исходный документ' });
    const lastLine = fixtures.mainDocumentText.trim().split('\n').at(-1)!;
    expect(await within(document).findByText(lastLine, { exact: false })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Контекст/u }));
    expect(screen.getByRole('heading', { name: 'Контекстные материалы' })).toBeVisible();
    expect(screen.getByRole('region', { name: 'Исходный документ' })).toBe(document);
    expect(within(document).getByText(lastLine, { exact: false })).toBeInTheDocument();

    fireEvent.click(screen.getByText('Модель', { exact: true }));
    expect(screen.getByRole('radiogroup', { name: 'Профиль модели' })).toBeVisible();
    expect(screen.getByRole('region', { name: 'Исходный документ' })).toBe(document);
    expect(within(document).getByText(lastLine, { exact: false })).toBeInTheDocument();
  });

  it('убирает предыдущий текст сразу после замены документа, пока загружается новый', async () => {
    renderWithProviders(<NewReviewPage />, '/new');
    const input = await screen.findByLabelText('Файл документа');
    fireEvent.change(input, {
      target: { files: [new File([fixtures.mainDocumentText], 'synthetic-spec.md', { type: 'text/markdown' })] },
    });
    const previousViewer = await screen.findByRole('region', { name: 'Исходный документ' });
    const previousLastLine = fixtures.mainDocumentText.trim().split('\n').at(-1)!;
    await within(previousViewer).findByText(previousLastLine, { exact: false });

    const replacement = { ...fixtures.contextDocument, filename: 'synthetic-replacement.md' };
    const replacementText = '# Синтетический поток заказов\nЗагрузка выполняется каждый час.\nКонец нового документа.';
    let releaseContent!: () => void;
    const contentReady = new Promise<void>((resolve) => { releaseContent = resolve; });
    mockServer.use(
      getUploadDocumentMockHandler(replacement),
      http.get(`${API}/workspaces/:workspaceId/documents/${replacement.id}/content`, async () => {
        await contentReady;
        return HttpResponse.text(replacementText, { headers: { 'Content-Type': 'text/markdown' } });
      }),
    );

    fireEvent.change(input, {
      target: { files: [new File([replacementText], replacement.filename, { type: 'text/markdown' })] },
    });
    try {
      await screen.findByText(replacement.filename);
      const replacementViewer = screen.getByRole('region', { name: 'Исходный документ' });
      expect(replacementViewer).not.toBe(previousViewer);
      expect(within(replacementViewer).getByRole('status')).toHaveTextContent('Загружаем документ…');
      expect(screen.queryByText(previousLastLine, { exact: false })).not.toBeInTheDocument();
    } finally {
      releaseContent();
    }

    const replacementViewer = screen.getByRole('region', { name: 'Исходный документ' });
    expect(await within(replacementViewer).findByText('Конец нового документа.')).toBeInTheDocument();
    expect(within(replacementViewer).getByText('Загрузка выполняется каждый час.')).toBeInTheDocument();
    expect(screen.queryByText(previousLastLine, { exact: false })).not.toBeInTheDocument();
  });
});
