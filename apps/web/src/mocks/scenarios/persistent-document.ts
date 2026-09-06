import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import * as fixtures from '@/mocks/fixtures';
import { API } from './base';
import { happyPath } from './happy-path';

/** Long synthetic source makes document scroll retention observable in the browser. */
export function persistentDocument(): RequestHandler[] {
  const finding = fixtures.report.findings[0]!;
  const quote = finding.anchors[0]!.quote;
  const content = Array.from({ length: 200 }, (_, index) => index === 99 ? quote : `Синтетический раздел ${index + 1}. Описание поля и правила загрузки.`).join('\n');
  return [
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId`, () => HttpResponse.json(fixtures.runCompleted)),
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/report`, () => HttpResponse.json({
      ...fixtures.report,
      findings: [{ ...finding, anchors: [{ ...finding.anchors[0], location: { kind: 'text', line_start: 100, line_end: 100 } }] }],
    })),
    http.get(`${API}/workspaces/:workspaceId/documents/:documentId/content`, () => HttpResponse.text(content, { headers: { 'Content-Type': 'text/markdown' } })),
    ...happyPath(),
  ];
}
