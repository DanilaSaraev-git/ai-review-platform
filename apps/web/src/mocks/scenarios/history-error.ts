import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import * as fixtures from '@/mocks/fixtures';
import { API, problem } from './base';
import { happyPath } from './happy-path';

export function historyError(): RequestHandler[] {
  let attempts = 0;
  return [
    http.get(`${API}/workspaces/:workspaceId/document-families`, () => {
      attempts += 1;
      return attempts === 1
        ? problem(500, 'internal_error', 'История временно недоступна')
        : HttpResponse.json({ items: [fixtures.documentFamily], next_cursor: null });
    }),
    ...happyPath(),
  ];
}
