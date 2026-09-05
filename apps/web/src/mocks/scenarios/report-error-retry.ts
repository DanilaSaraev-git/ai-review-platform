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
      // StrictMode может прервать первый запрос при проверочном remount.
      return attempts <= 2
        ? problem(500, 'internal_error', 'Отчёт временно недоступен')
        : HttpResponse.json(fixtures.report, { headers: { ETag: '"synthetic-report-v1"' } });
    }),
    ...happyPath(),
  ];
}
