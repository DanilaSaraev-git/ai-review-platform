import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import * as fixtures from '@/mocks/fixtures';
import { API } from './base';
import { happyPath } from './happy-path';

/** Ход выполняется: отправка следующего недоступна с названной причиной (FR-031, FR-032). */
export function dialogueGenerating(): RequestHandler[] {
  return [
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/findings/:findingId/dialogue`, () =>
      HttpResponse.json(fixtures.dialogueGenerating, { status: 200 }),
    ),
    ...happyPath(),
  ];
}
