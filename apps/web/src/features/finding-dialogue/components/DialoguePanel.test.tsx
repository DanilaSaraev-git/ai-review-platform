import { describe, expect, it } from 'vitest';
import { delay, http } from 'msw';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import * as fixtures from '@/mocks/fixtures';
import { mockServer } from '@/mocks/server';
import { dialogueKey } from '@/api/query-keys';
import { API, problem } from '@/mocks/scenarios/base';
import { createTestQueryClient, renderWithQueryClient } from '@/test/render';
import { DialoguePanel } from './DialoguePanel';

describe('DialoguePanel', () => {
  it('при ошибке фонового обновления сохраняет историю и введённый draft', async () => {
    mockServer.use(
      http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/findings/:findingId/dialogue`, async () => {
        await delay(80);
        return problem(500, 'internal_error', 'Диалог временно недоступен');
      }),
    );
    const queryClient = createTestQueryClient();
    queryClient.setQueryData(
      dialogueKey(fixtures.workspaceId, fixtures.runId, fixtures.findingId),
      fixtures.dialogueOpen,
    );
    const user = userEvent.setup();
    renderWithQueryClient(
      <DialoguePanel workspaceId={fixtures.workspaceId} runId={fixtures.runId} findingId={fixtures.findingId} />,
      queryClient,
    );

    const composer = screen.getByRole('textbox', { name: /Уточняющий вопрос/u });
    await user.type(composer, 'Черновик вопроса');
    expect(await screen.findByText('Не удалось обновить диалог')).toBeInTheDocument();
    expect(composer).toHaveValue('Черновик вопроса');
    expect(screen.getByText(fixtures.dialogueOpen.turns[0]!.member_message)).toBeInTheDocument();
  });
});
