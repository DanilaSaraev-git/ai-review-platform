import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import * as fixtures from '@/mocks/fixtures';
import { API, problem } from './base';
import { happyPath } from './happy-path';

export function reportErrorRetry(): RequestHandler[] {
  let attempts = 0;
  return [
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/report`, () => {
      attempts += 1;
      // Общий layout держит один запрос отчёта: первый ответ — ошибка,
      // явный повтор пользователя — успешный ответ.
      return attempts === 1
        ? problem(500, 'internal_error', 'Отчёт временно недоступен')
        : HttpResponse.json(fixtures.report, { headers: { ETag: '"synthetic-report-v1"' } });
    }),
    ...happyPath(),
  ];
}
