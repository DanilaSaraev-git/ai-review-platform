import { describe, expect, it } from 'vitest';
import { decisionSchema, toFormValues, toPutFindingDecision } from './decision-schema';
import * as fixtures from '@/mocks/fixtures';

describe('правила формы решения (FR-024 — FR-026)', () => {
  it('требует обоснование при любом статусе, кроме «не рассмотрено»', () => {
    for (const status of ['confirmed', 'rejected', 'needs_context'] as const) {
      const result = decisionSchema.safeParse({ status, reason: '   ', resolution: '' });
      expect(result.success).toBe(false);
    }
  });

  it('принимает статус с непустым обоснованием', () => {
    const result = decisionSchema.safeParse({
      status: 'confirmed',
      reason: 'Расписание нужно согласовать до разработки.',
      resolution: '',
    });
    expect(result.success).toBe(true);
  });

  it('не требует обоснование для «не рассмотрено»', () => {
    expect(decisionSchema.safeParse({ status: 'unreviewed', reason: '', resolution: '' }).success).toBe(true);
  });

  it('очищает обоснование и резолюцию при сбросе в «не рассмотрено»', () => {
    const body = toPutFindingDecision({ status: 'unreviewed', reason: 'что-то', resolution: 'что-то' }, 3);
    expect(body).toEqual({ status: 'unreviewed', reason: null, resolution: null, expected_revision: 3 });
  });

  it('отправляет пустую резолюцию как null и всегда передаёт ожидаемую ревизию', () => {
    const body = toPutFindingDecision({ status: 'rejected', reason: '  причина  ', resolution: '   ' }, 7);
    expect(body).toEqual({
      status: 'rejected',
      reason: 'причина',
      resolution: null,
      expected_revision: 7,
    });
  });

  it('строит значения формы из сохранённого решения', () => {
    expect(toFormValues(fixtures.decision)).toEqual({
      status: 'confirmed',
      reason: fixtures.decision.reason,
      resolution: fixtures.decision.resolution,
    });
  });

  it('для нерассмотренного замечания даёт пустую форму', () => {
    expect(toFormValues(undefined)).toEqual({ status: 'unreviewed', reason: '', resolution: '' });
  });
});
