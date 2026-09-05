import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import * as fixtures from '@/mocks/fixtures';
import { API } from './base';
import { happyPath } from './happy-path';

/** Успешный запуск без замечаний — содержательный результат, не пустой экран (FR-023). */
export function emptyReport(): RequestHandler[] {
  return [
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/report`, () =>
      HttpResponse.json(
        {
          ...fixtures.report,
          summary: 'Замечаний не найдено: документ рассмотрен полностью.',
          findings: [],
        },
        { status: 200, headers: { ETag: '"synthetic-report-empty"' } },
      ),
    ),
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/finding-states`, () =>
      HttpResponse.json({ items: [] }, { status: 200 }),
    ),
    ...happyPath(),
  ];
}
