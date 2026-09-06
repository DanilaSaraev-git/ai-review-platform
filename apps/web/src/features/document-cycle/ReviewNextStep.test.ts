import { describe, expect, it } from 'vitest';
import type { FindingState } from '@/api/generated/model';
import * as fixtures from '@/mocks/fixtures';
import { nextStep } from './ReviewNextStep';

describe('следующий шаг проверки', () => {
  it('контекст остаётся открытым, принятые замечания ведут к новой версии', () => {
    const report = { ...fixtures.report, findings: [fixtures.report.findings[0]!] };
    const id = report.findings[0]!.id;
    const state = (status: FindingState['decision']['status']) => new Map([[id, { finding_id: id, decision: { ...fixtures.decision, status } } as FindingState]]);
    const cycle = { ...fixtures.persistingCycle, limitations: [], entries: [], status: 'ready' as const };
    expect(nextStep(report, state('needs_context'), cycle).dialogue).toBe(true);
    expect(nextStep(report, state('confirmed'), cycle).upload).toBe(true);
    expect(nextStep(report, state('rejected'), cycle).complete).toBe(true);
    expect(nextStep(report, state('rejected'), { ...cycle, limitations: ['review_coverage_incomplete'] }).complete).toBeUndefined();
  });
});
