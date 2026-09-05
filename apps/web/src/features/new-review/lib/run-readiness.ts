import type { Document } from '@/api/generated/model';

/**
 * Допуск к запуску по состоянию извлечения текста основного документа (FR-040).
 *
 * Неудачное извлечение означает, что проверять нечего: запуск запрещён, чтобы
 * аналитик не тратил время на заведомо обречённый прогон. Частичное извлечение
 * оставляет пригодный текст, и решение принимает человек, а не интерфейс.
 */
export interface RunReadiness {
  canStart: boolean;
  /** Причина запрета: показывается, когда запуск недоступен. */
  blockedReason: string | null;
  /** Предупреждение при доступном запуске: показывается вместе с кнопкой. */
  warning: string | null;
  nextStep: string | null;
}

export function runReadiness(document: Document | undefined): RunReadiness {
  if (!document) {
    return {
      canStart: false,
      blockedReason: 'Документ на проверку не выбран.',
      warning: null,
      nextStep: 'Загрузите один документ ТЗ.',
    };
  }

  switch (document.extraction_state) {
    case 'failed':
      return {
        canStart: false,
        blockedReason: 'Текст документа извлечь не удалось, проверять нечего.',
        warning: null,
        nextStep: 'Загрузите документ в другом виде — например, PDF с текстовым слоем, Markdown или обычный текст.',
      };
    case 'pending':
      return {
        canStart: false,
        blockedReason: 'Документ ещё готовится: извлечение текста не завершено.',
        warning: null,
        nextStep: 'Дождитесь окончания подготовки документа.',
      };
    case 'partial':
      return {
        canStart: true,
        blockedReason: null,
        warning: 'Часть текста прочитать не удалось: она не будет проверена.',
        nextStep: null,
      };
    case 'completed':
      return { canStart: true, blockedReason: null, warning: null, nextStep: null };
    default:
      return { canStart: false, blockedReason: 'Состояние документа неизвестно.', warning: null, nextStep: null };
  }
}
