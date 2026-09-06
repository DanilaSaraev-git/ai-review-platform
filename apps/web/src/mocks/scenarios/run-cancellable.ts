import { http, HttpResponse } from 'msw';
import type { ReviewRun } from '@/api/generated/model';
import * as fixtures from '@/mocks/fixtures';
import { readState, writeState } from '@/mocks/store';
import { API, baseHandlers, problem } from './base';

/** Synthetic active run; cancellation survives navigation and reload. */
export function runCancellable() {
  let run = readState<ReviewRun>('cancellable-run', {
    ...fixtures.runQueued, state: 'reviewing', started_at: new Date().toISOString(),
    progress: { percent: 40, message: 'Идёт проверка документа' },
  });
  const path = `${API}/workspaces/:workspaceId/review-runs`;
  return [
    http.get(`${path}/:runId`, () => HttpResponse.json(run)),
    http.post(`${path}/:runId/cancel`, () => {
      if (run.state === 'cancelled') return problem(409, 'run_terminal', 'Проверка уже отменена');
      const now = new Date().toISOString();
      run = { ...run, state: 'cancelled', cancel_requested_at: now, finished_at: now, report_available: false };
      writeState('cancellable-run', run);
      return HttpResponse.json(run, { status: 202 });
    }),
    http.get(`${API}/workspaces/:workspaceId/document-families/:familyId/review-runs`, () => HttpResponse.json({ items: [run], next_cursor: null })),
    ...baseHandlers(),
  ];
}
