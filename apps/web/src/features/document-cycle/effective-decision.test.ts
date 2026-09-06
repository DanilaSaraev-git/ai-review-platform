import { describe, expect, it } from 'vitest';
import * as fixtures from '@/mocks/fixtures';
import { effectiveDecision } from './effective-decision';

describe('Перенос оценки', () => {
  const carried = fixtures.persistingCycle.entries[0]!;
  it('показывает прежнюю оценку с исходным автором для нетронутого замечания', () => {
    expect(effectiveDecision(fixtures.unreviewedDecision, carried)).toBe(carried.previous_decision);
  });
  it('явный сброс и новая оценка имеют приоритет над переносом', () => {
    const reset = { ...fixtures.unreviewedDecision, revision: 1 };
    expect(effectiveDecision(reset, carried)).toBe(reset);
    const current = { ...fixtures.decision, revision: 2 };
    expect(effectiveDecision(current, carried)).toBe(current);
  });
  it('сомнительное соответствие оставляет прежнее решение справкой', () => {
    expect(effectiveDecision(fixtures.unreviewedDecision, { ...carried, decision_carried: false })).toBe(fixtures.unreviewedDecision);
  });
});
