import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import { getGetDocumentMockHandler } from '@/api/generated/endpoints.msw';
import * as fixtures from '@/mocks/fixtures';
import { API } from './base';
import { happyPath } from './happy-path';

/**
 * Недоступный контекстный источник даёт частичный отчёт, а не неудачный
 * запуск: контекст не роняет проверку основного документа (FR-022, US5-4).
 */
export function contextPartial(): RequestHandler[] {
  return [
    getGetDocumentMockHandler(({ params }) =>
      String(params.documentId) === fixtures.contextDocument.id ? fixtures.contextDocument : fixtures.mainDocument,
    ),
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/report`, () =>
      HttpResponse.json(fixtures.reportPartial, { status: 200, headers: { ETag: '"synthetic-report-partial"' } }),
    ),
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/finding-states`, () =>
      HttpResponse.json({ items: [] }, { status: 200 }),
    ),
    ...happyPath(),
  ];
}
