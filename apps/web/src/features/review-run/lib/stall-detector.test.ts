import { describe, expect, it } from 'vitest';
import type { ReviewRun } from '@/api/generated/model';
import * as fixtures from '@/mocks/fixtures';
import { runProgressState, runStateFingerprint } from './stall-detector';

const NOW = Date.parse('2026-09-04T10:00:00Z');
const MINUTE = 60 * 1000;

function runningSince(minutesAgo: number, state: ReviewRun['state'] = 'reviewing'): ReviewRun {
  return {
    ...fixtures.runQueued,
    state,
    started_at: new Date(NOW - minutesAgo * MINUTE).toISOString(),
    finished_at: null,
  };
}

describe('runProgressState (FR-039, SC-013)', () => {
  it('не предупреждает, пока не пройдено 15 минут без смены состояния', () => {
    const state = runProgressState(runningSince(14), NOW - 14 * MINUTE, NOW);
    expect(state.isStalled).toBe(false);
    expect(state.warning).toBeNull();
  });

  it('предупреждает после 15 минут без смены состояния и показывает длительность', () => {
    const state = runProgressState(runningSince(21), NOW - 21 * MINUTE, NOW);
    expect(state.isStalled).toBe(true);
    expect(state.warning).toMatch(/дольше обычного/u);
    expect(state.durationMs).toBe(21 * MINUTE);
  });

  it('сбрасывает отсчёт, когда состояние сменилось только что', () => {
    const state = runProgressState(runningSince(40), NOW - MINUTE, NOW);
    expect(state.isStalled).toBe(false);
  });

  it('не предупреждает о терминальном запуске', () => {
    const completed: ReviewRun = {
      ...fixtures.runCompleted,
      started_at: new Date(NOW - 40 * MINUTE).toISOString(),
      finished_at: new Date(NOW - 20 * MINUTE).toISOString(),
    };
    const state = runProgressState(completed, NOW - 40 * MINUTE, NOW);
    expect(state.isStalled).toBe(false);
    expect(state.durationMs).toBe(20 * MINUTE);
  });

  it('различает состояния по отпечатку, чтобы смена прогресса сбрасывала отсчёт', () => {
    const first = runStateFingerprint(runningSince(5, 'queued'));
    const second = runStateFingerprint(runningSince(5, 'reviewing'));
    expect(first).not.toBe(second);
  });
});
