import type { FindingDialogue, ProposedResolution } from '@/api/generated/model';

/**
 * Перенос предложенной моделью резолюции в форму решения (FR-029, SC-007).
 *
 * Предложение никогда не становится решением автоматически. Действие ниже
 * только подставляет текст в поле резолюции; сохранение решения остаётся
 * вторым, отдельным действием аналитика (принцип V).
 */
export const TRANSFER_LABEL = 'Использовать предложение';

export const TRANSFER_HINT =
  'Текст подставится в поле резолюции. Решение не сохранится, пока вы не выберете статус и не нажмёте «Сохранить решение».';

/** Последнее предложение в диалоге: именно оно доступно к переносу. */
export function latestProposedResolution(dialogue: FindingDialogue | undefined): ProposedResolution | null {
  if (!dialogue) {
    return null;
  }
  for (let index = dialogue.turns.length - 1; index >= 0; index -= 1) {
    const proposal = dialogue.turns[index]?.assistant_response?.proposed_resolution;
    if (proposal) {
      return proposal;
    }
  }
  return null;
}

/** Текст для подстановки в поле резолюции формы решения. */
export function resolutionTextFor(proposal: ProposedResolution | null): string | null {
  return proposal ? proposal.text : null;
}
