import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import * as fixtures from '@/mocks/fixtures';
import { renderWithProviders } from '@/test/render';
import { NewReviewPage } from './NewReviewPage';

describe('новая проверка требует выбора файла', () => {
  it('прежняя ссылка повтора не позволяет запустить сохранённый файл', async () => {
    renderWithProviders(<NewReviewPage />, `/new?repeat=${fixtures.runId}`);
    expect(await screen.findByRole('button', { name: /Запустить проверку/u })).toBeDisabled();
    expect(screen.getByLabelText('Файл документа')).toBeInTheDocument();
    expect(screen.queryByText('Повторная проверка')).not.toBeInTheDocument();
  });
});
