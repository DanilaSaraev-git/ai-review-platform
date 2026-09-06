import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import type { DocumentFamily } from '@/api/generated/model';
import * as fixtures from '@/mocks/fixtures';
import { API } from './base';
import { happyPath } from './happy-path';

const families: DocumentFamily[] = Array.from({ length: 21 }, (_, index) => ({
  ...fixtures.documentFamily,
  id: `60000000-0000-4000-8000-${String(index + 1).padStart(12, '0')}`,
  created_at: `2026-09-${String(5 - Math.floor(index / 10)).padStart(2, '0')}T${String(20 - (index % 10)).padStart(2, '0')}:00:00.000000Z`,
}));

export function historyPagination(): RequestHandler[] {
  return [
    http.get(`${API}/workspaces/:workspaceId/document-families`, ({ request }) => {
      const cursor = new URL(request.url).searchParams.get('cursor');
      return HttpResponse.json(cursor
        ? { items: families.slice(20), next_cursor: null }
        : { items: families.slice(0, 20), next_cursor: 'page-2' });
    }),
    ...happyPath(),
  ];
}
