import { z } from 'zod';
import type { HumanDecision, PutFindingDecision } from '@/api/generated/model';

/**
 * Правила формы решения (FR-024 — FR-026).
 *
 * Обоснование обязательно при любом статусе, кроме «не рассмотрено»: решение
 * без причины не поможет ни автору ТЗ, ни самому аналитику при возврате к
 * разбору. Сброс в «не рассмотрено» очищает обоснование и резолюцию.
 */
export const DECISION_STATUSES = ['unreviewed', 'confirmed', 'rejected', 'needs_context'] as const;

export const REASON_REQUIRED_MESSAGE = 'Укажите обоснование: без него решение сохранить нельзя.';

export const decisionSchema = z
  .object({
    status: z.enum(DECISION_STATUSES),
    reason: z.string().max(4000).default(''),
    resolution: z.string().max(8000).default(''),
  })
  .refine((value) => value.status === 'unreviewed' || value.reason.trim().length > 0, {
    path: ['reason'],
    message: REASON_REQUIRED_MESSAGE,
  });

export type DecisionFormValues = z.input<typeof decisionSchema>;

/** Приведение значений формы к телу запроса контракта. */
export function toPutFindingDecision(values: DecisionFormValues, expectedRevision: number): PutFindingDecision {
  if (values.status === 'unreviewed') {
    return { status: 'unreviewed', reason: null, resolution: null, expected_revision: expectedRevision };
  }
  const resolution = (values.resolution ?? '').trim();
  return {
    status: values.status,
    reason: (values.reason ?? '').trim(),
    resolution: resolution.length > 0 ? resolution : null,
    expected_revision: expectedRevision,
  };
}

/** Значения формы из текущего сохранённого решения. */
export function toFormValues(decision: HumanDecision | undefined): DecisionFormValues {
  return {
    status: decision?.status ?? 'unreviewed',
    reason: decision?.reason ?? '',
    resolution: decision?.resolution ?? '',
  };
}
