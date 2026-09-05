import { describe, expect, it } from 'vitest';
import type { PublicLimits } from '@/api/generated/model';
import { contextLimitState } from './context-limit';

const limits: PublicLimits = { document_upload_max_bytes: 1024, max_context_documents: 2 };

describe('contextLimitState (FR-008, US5-2)', () => {
  it('показывает остаток, пока лимит не достигнут', () => {
    const state = contextLimitState(1, limits);
    expect(state.remaining).toBe(1);
    expect(state.canAttachMore).toBe(true);
    expect(state.limitReachedReason).toBeNull();
  });

  it('отказывает в подключении сверх лимита и называет действующее значение', () => {
    const state = contextLimitState(2, limits);
    expect(state.canAttachMore).toBe(false);
    expect(state.limitReachedReason).toMatch(/2/u);
  });

  it('не уходит в отрицательный остаток', () => {
    expect(contextLimitState(5, limits).remaining).toBe(0);
  });
});
