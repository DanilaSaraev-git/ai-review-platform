import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import type { FindingDialogue } from '@/api/generated/model';
import * as fixtures from '@/mocks/fixtures';
import { API, problem } from './base';
import { happyPath } from './happy-path';

/** Отправка хода поверх устаревшей ревизии диалога (FR-036). */
export function dialogueConflict(): RequestHandler[] {
  let attempts = 0;
  let current: FindingDialogue = { ...fixtures.dialogueOpen, revision: 1, turn_count: 0, turns: [] };

  return [
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/findings/:findingId/dialogue`, () =>
      HttpResponse.json(current),
    ),
    http.post(`${API}/workspaces/:workspaceId/review-runs/:runId/findings/:findingId/dialogue/turns`, async ({ request }) => {
      attempts += 1;
      if (attempts === 1) {
        return problem(409, 'revision_conflict', 'Версия диалога изменилась', 'Обновите диалог и повторите отправку.');
      }
      const body = (await request.json()) as { message: string; expected_revision: number };
      if (body.expected_revision !== current.revision) {
        return problem(409, 'revision_conflict', 'Версия диалога изменилась');
      }
      current = {
        ...current,
        revision: current.revision + 1,
        turn_count: 1,
        turns: [{ ...fixtures.dialogueOpen.turns[0]!, member_message: body.message }],
      };
      return HttpResponse.json(current, { status: 202 });
    }),
    ...happyPath(),
  ];
}
