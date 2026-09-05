import { isRevisionConflict } from '@/api/errors';

/**
 * Конфликт ревизии решения — не ошибка формы, а отдельное состояние
 * (решение R-07). Диалог держит свой случай в собственном модуле, поэтому
 * области не зависят друг от друга.
 *
 * Введённый аналитиком текст не сбрасывается: обоснование, резолюция или
 * вопрос остаются в полях, рядом показывается актуальное сохранённое значение,
 * и повтор доступен одним действием уже с новой ревизией
 * (FR-027, FR-036, SC-005).
 */
export interface ConflictState {
  isConflict: boolean;
  title: string;
  hint: string;
}

export const DECISION_CONFLICT: ConflictState = {
  isConflict: true,
  title: 'Решение изменилось с момента, когда вы открыли форму',
  hint: 'Ниже показано актуальное сохранённое решение. Ваш текст сохранён — повторите сохранение, чтобы записать его поверх актуальной версии.',
};

export const NO_CONFLICT: ConflictState = { isConflict: false, title: '', hint: '' };

export function decisionConflictState(error: unknown): ConflictState {
  return isRevisionConflict(error) ? DECISION_CONFLICT : NO_CONFLICT;
}
