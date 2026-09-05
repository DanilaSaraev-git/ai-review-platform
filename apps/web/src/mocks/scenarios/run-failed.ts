import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import * as fixtures from '@/mocks/fixtures';
import { API, baseHandlers, problem } from './base';

/** Неудачное завершение с причиной; отчёт не публикуется (FR-015, US1-6). */
export function runFailed(): RequestHandler[] {
  return [
    http.post(`${API}/workspaces/:workspaceId/review-runs`, () =>
      HttpResponse.json({ ...fixtures.runFailed, state: 'queued', finished_at: null, error: null }, { status: 202 }),
    ),
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId`, () =>
      HttpResponse.json(fixtures.runFailed, { status: 200 }),
    ),
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/report`, () =>
      problem(409, 'report_unavailable', 'Отчёт не опубликован'),
    ),
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/finding-states`, () =>
      problem(409, 'report_unavailable', 'Отчёт не опубликован'),
    ),
    ...baseHandlers(),
  ];
}
