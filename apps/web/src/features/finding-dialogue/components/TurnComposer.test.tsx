import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import type { FindingDialogue, DialogueSummary } from '@/api/generated/model';
import * as fixtures from '@/mocks/fixtures';
import { BLOCKED_REASON_TEXT } from '@/lib/error-messages';
import { renderWithQueryClient } from '@/test/render';
import { TurnComposer } from './TurnComposer';

type BlockedReason = NonNullable<DialogueSummary['blocked_reason']>;

function dialogueWith(overrides: Partial<FindingDialogue>): FindingDialogue {
  return { ...fixtures.dialogueOpen, ...overrides };
}

function renderComposer(dialogue: FindingDialogue) {
  return renderWithQueryClient(
    <TurnComposer
      workspaceId={fixtures.workspaceId}
      runId={fixtures.runId}
      findingId={fixtures.findingId}
      dialogue={dialogue}
    />,
  );
}

describe('TurnComposer (FR-031, FR-032, SC-008)', () => {
  it.each(Object.keys(BLOCKED_REASON_TEXT) as BlockedReason[])(
    'называет причину недоступности «%s», а не оставляет кнопку молча неактивной',
    (reason) => {
      renderComposer(dialogueWith({ can_send_message: false, blocked_reason: reason }));

      expect(screen.getByText(BLOCKED_REASON_TEXT[reason])).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Отправить вопрос/u })).toBeDisabled();
    },
  );

  it('во время генерации хода отправка следующего недоступна', () => {
    renderComposer(dialogueWith({ can_send_message: false, blocked_reason: 'generation_in_progress' }));

    expect(screen.getByRole('button', { name: /Отправить вопрос/u })).toBeDisabled();
    expect(screen.getByLabelText(/Уточняющий вопрос/u)).toBeDisabled();
    expect(screen.getByText(/Предыдущий ход ещё не завершён/u)).toBeInTheDocument();
  });

  it('разрешает отправку, когда сервер сообщает can_send_message', () => {
    renderComposer(dialogueWith({ can_send_message: true, blocked_reason: null }));
    expect(screen.getByLabelText(/Уточняющий вопрос/u)).toBeEnabled();
  });
});
