import type { AsyncError, CoverageGap, DialogueError, DialogueSummary } from '@/api/generated/model';

/**
 * Человекочитаемые тексты по кодам контракта (FR-015, FR-032).
 * Текст выбирается по коду, а не по серверной строке (решение R-11):
 * серверная формулировка может не подходить экрану и не различает случаи.
 */

export const RUN_ERROR_TEXT: Record<AsyncError['code'], string> = {
  invalid_document: 'Документ не удалось прочитать как корректный файл.',
  unsupported_document: 'Формат документа не поддерживается проверкой.',
  extraction_failed: 'Не удалось извлечь текст документа.',
  context_limit: 'Материалы не поместились в допустимый объём проверки.',
  model_unavailable: 'Профиль модели временно недоступен.',
  model_output_invalid: 'Модель вернула результат, не соответствующий контракту.',
  validation_failed: 'Результат проверки не прошёл валидацию и не был опубликован.',
  cancelled: 'Проверка была отменена.',
  internal_error: 'Внутренняя ошибка сервиса проверки.',
};

export const COVERAGE_GAP_TEXT: Record<CoverageGap['code'], string> = {
  source_unavailable: 'Источник не удалось прочитать',
  source_partial: 'Источник прочитан частично',
  context_budget: 'Источник не поместился в объём проверки',
  context_limit: 'Достигнут предел объёма контекста',
  processing_failed: 'Обработка источника не завершилась',
  unsupported_content: 'Содержимое источника не поддерживается',
  other: 'Источник не учтён',
};

export const DIALOGUE_ERROR_TEXT: Record<DialogueError['code'], string> = {
  model_unavailable: 'Профиль модели временно недоступен.',
  context_limit: 'Материалы хода не поместились в допустимый объём.',
  content_blocked: 'Ответ не был выдан из-за ограничений содержимого.',
  model_output_invalid: 'Модель вернула ответ, не соответствующий контракту.',
  validation_failed: 'Ответ не прошёл проверку и не был сохранён.',
  internal_error: 'Внутренняя ошибка при подготовке ответа.',
};

type BlockedReason = NonNullable<DialogueSummary['blocked_reason']>;

/** Причина недоступности отправки хода: неактивная кнопка всегда объяснена (FR-032). */
export const BLOCKED_REASON_TEXT: Record<BlockedReason, string> = {
  generation_in_progress: 'Предыдущий ход ещё не завершён.',
  turn_limit_reached: 'Исчерпан лимит ходов по этому замечанию.',
  human_decision_recorded: 'Решение по замечанию сохранено, диалог закрыт.',
  dialogue_not_supported: 'Диалог по этому замечанию не поддерживается.',
  model_unavailable: 'Профиль модели временно недоступен.',
};

export function blockedReasonText(reason: DialogueSummary['blocked_reason']): string | null {
  if (!reason) {
    return null;
  }
  return BLOCKED_REASON_TEXT[reason] ?? 'Отправка хода сейчас недоступна.';
}

/** Состояния запуска: подпись и пояснение для каждого (FR-013). */
export const RUN_STATE_TEXT = {
  queued: { label: 'В очереди', hint: 'Проверка ожидает свободного исполнителя.' },
  preparing: { label: 'Подготовка', hint: 'Готовим источники к проверке.' },
  reviewing: { label: 'Проверка', hint: 'Модель разбирает документ.' },
  validating: { label: 'Проверка результата', hint: 'Сверяем результат с контрактом.' },
  completed: { label: 'Завершено', hint: 'Отчёт опубликован.' },
  failed: { label: 'Не удалось', hint: 'Проверка остановлена, отчёт не опубликован.' },
  cancelled: { label: 'Отменено', hint: 'Проверка прекращена, отчёт не публиковался.' },
} as const;

/** Состояния извлечения текста документа (FR-040). */
export const EXTRACTION_STATE_TEXT = {
  pending: 'Документ ещё готовится',
  completed: 'Текст извлечён',
  partial: 'Текст извлечён частично',
  failed: 'Текст извлечь не удалось',
} as const;

export const DECISION_STATUS_TEXT = {
  unreviewed: 'Не рассмотрено',
  confirmed: 'Подтверждено',
  rejected: 'Отклонено',
  needs_context: 'Нужен контекст',
} as const;

export const FINDING_KIND_TEXT = {
  ambiguity: 'Неоднозначность',
  contradiction: 'Противоречие',
  missing: 'Отсутствует',
  inconsistency: 'Несогласованность',
  other: 'Иное',
} as const;

export const PRIORITY_TEXT = {
  high: 'Высокий',
  medium: 'Средний',
  low: 'Низкий',
} as const;

export const SOURCE_STATUS_TEXT = {
  available: 'Доступен',
  partial: 'Частично доступен',
  unavailable: 'Недоступен',
} as const;

export const SOURCE_ROLE_TEXT = {
  document: 'Основной документ',
  context: 'Контекст',
} as const;

export const ASSISTANT_ACTION_TEXT = {
  clarify: 'Уточнение',
  propose_resolution: 'Предложена резолюция',
  escalate: 'Требуется эскалация',
} as const;
