import type { PublicLimits } from '@/api/generated/model';

/**
 * Лимит числа контекстных материалов (FR-008, US5-2).
 * Интерфейс показывает остаток и отказывает в подключении сверх лимита,
 * называя действующее значение.
 */
export interface ContextLimitState {
  used: number;
  max: number;
  remaining: number;
  canAttachMore: boolean;
  limitReachedReason: string | null;
}

export function contextLimitState(attachedCount: number, limits: PublicLimits): ContextLimitState {
  const max = limits.max_context_documents;
  const used = Math.max(0, attachedCount);
  const remaining = Math.max(0, max - used);
  const canAttachMore = remaining > 0;

  return {
    used,
    max,
    remaining,
    canAttachMore,
    limitReachedReason: canAttachMore
      ? null
      : `Подключено максимальное число контекстных материалов: ${max}. Отключите лишний, чтобы добавить другой.`,
  };
}
