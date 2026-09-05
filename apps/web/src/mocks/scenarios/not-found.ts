import { http } from 'msw';
import type { RequestHandler } from 'msw';
import { API, baseHandlers, problem } from './base';

/**
 * Идентификатор запуска отсутствует в namespace настроенного рабочего
 * пространства: обычное «не найдено», без семантики доступа (FR-003, US2-8).
 */
export function notFound(): RequestHandler[] {
  return [
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId`, () => problem(404, 'not_found', 'Ресурс не найден')),
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/report`, () =>
      problem(404, 'not_found', 'Ресурс не найден'),
    ),
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/finding-states`, () =>
      problem(404, 'not_found', 'Ресурс не найден'),
    ),
    ...baseHandlers(),
  ];
}
