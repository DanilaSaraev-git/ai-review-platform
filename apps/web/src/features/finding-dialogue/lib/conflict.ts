import { isRevisionConflict } from '@/api/errors';

/**
 * Конфликт ревизии диалога — отдельное состояние, а не ошибка формы
 * (FR-036, SC-005, решение R-07).
 *
 * Введённый вопрос остаётся в поле, рядом показывается актуальное состояние
 * диалога, и повтор доступен одним действием уже с новой ревизией.
 */
export interface DialogueConflictState {
  isConflict: boolean;
  title: string;
  hint: string;
}

export const NO_CONFLICT: DialogueConflictState = { isConflict: false, title: '', hint: '' };

export const DIALOGUE_CONFLICT: DialogueConflictState = {
  isConflict: true,
  title: 'Диалог изменился с момента, когда вы открыли форму',
  hint: 'Ниже показано актуальное состояние диалога. Ваш вопрос сохранён — повторите отправку.',
};

export function dialogueConflictState(error: unknown): DialogueConflictState {
  return isRevisionConflict(error) ? DIALOGUE_CONFLICT : NO_CONFLICT;
}
