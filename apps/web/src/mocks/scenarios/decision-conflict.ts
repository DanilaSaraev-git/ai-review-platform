import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import type { HumanDecision } from '@/api/generated/model';
import * as fixtures from '@/mocks/fixtures';
import { API, problem } from './base';
import { happyPath } from './happy-path';

/**
 * Сохранение решения поверх устаревшей ревизии: 409 revision_conflict.
 * Интерфейс обязан показать актуальное значение и сохранить введённый текст
 * (FR-027, SC-005).
 */
export function decisionConflict(): RequestHandler[] {
  let attempts = 0;
  let current: HumanDecision = { ...fixtures.unreviewedDecision, revision: 1 };

  return [
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/finding-states`, () =>
      HttpResponse.json({
        items: [{
          finding_id: fixtures.findingId,
          decision: current,
          dialogue: fixtures.findingStates.items[0]!.dialogue,
        }],
      }),
    ),
    http.put(`${API}/workspaces/:workspaceId/review-runs/:runId/findings/:findingId/decision`, async ({ request }) => {
      attempts += 1;
      if (attempts === 1) {
        return problem(409, 'revision_conflict', 'Версия решения изменилась', 'Обновите замечание и повторите действие.');
      }
      const body = (await request.json()) as {
        status: HumanDecision['status']; reason: string | null; resolution: string | null; expected_revision: number;
      };
      if (body.expected_revision !== current.revision) {
        return problem(409, 'revision_conflict', 'Версия решения изменилась');
      }
      current = {
        status: body.status,
        revision: current.revision + 1,
        actor: fixtures.actor,
        reason: body.reason,
        resolution: body.resolution,
        decided_at: '2026-09-04T09:06:00Z',
      };
      return HttpResponse.json(current);
    }),
    ...happyPath(),
  ];
}
