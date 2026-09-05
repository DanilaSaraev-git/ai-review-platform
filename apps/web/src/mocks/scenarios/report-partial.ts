import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import * as fixtures from '@/mocks/fixtures';
import { API } from './base';
import { happyPath } from './happy-path';

/** Частичный охват: пропуски с причинами и статусы всех источников (FR-022). */
export function reportPartial(): RequestHandler[] {
  return [
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/report`, () =>
      HttpResponse.json(fixtures.reportPartial, { status: 200, headers: { ETag: '"synthetic-report-partial"' } }),
    ),
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/finding-states`, () =>
      HttpResponse.json({ items: [] }, { status: 200 }),
    ),
    ...happyPath(),
  ];
}
