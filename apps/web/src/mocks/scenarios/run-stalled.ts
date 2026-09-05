import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import * as fixtures from '@/mocks/fixtures';
import { API, baseHandlers } from './base';

/**
 * Запуск не меняет состояние: started_at отодвинут в прошлое более чем на
 * 15 минут, поэтому интерфейс показывает предупреждение и длительность,
 * не подменяя состояние и не прекращая опрос (FR-039, SC-013).
 */
export function runStalled(): RequestHandler[] {
  const startedAt = new Date(Date.now() - 21 * 60 * 1000).toISOString();
  const stuck = {
    ...fixtures.runQueued,
    state: 'reviewing' as const,
    progress: { percent: 40, message: 'Идёт проверка документа' },
    started_at: startedAt,
  };
  return [
    http.post(`${API}/workspaces/:workspaceId/review-runs`, () => HttpResponse.json(stuck, { status: 202 })),
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId`, () => HttpResponse.json(stuck, { status: 200 })),
    ...baseHandlers(),
  ];
}
