import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import * as fixtures from '@/mocks/fixtures';
import { API } from './base';
import { happyPath } from './happy-path';

export function reportLong(): RequestHandler[] {
  const finding = fixtures.report.findings[0]!;
  const findings = Array.from({ length: 8 }, (_, index) => ({
    ...finding,
    id: `80000000-0000-4000-8000-${String(index + 1).padStart(12, '0')}`,
    title: `${finding.title} · ${index + 1}`,
  }));
  return [
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/report`, () =>
      HttpResponse.json({ ...fixtures.report, findings }),
    ),
    ...happyPath(),
  ];
}
