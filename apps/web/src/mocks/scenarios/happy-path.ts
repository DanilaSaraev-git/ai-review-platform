import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import type { FindingDialogue, HumanDecision, ReviewRun } from '@/api/generated/model';
import * as fixtures from '@/mocks/fixtures';
import { readState, writeState } from '@/mocks/store';
import { API, baseHandlers, problem } from './base';

/**
 * Полный путь: очередь → работа → успешное завершение → неизменяемый отчёт →
 * один ход диалога → сохранённое решение.
 *
 * Состояния запуска сменяются при повторных запросах, поэтому проверяется
 * настоящее наблюдение, а не единичный снимок (SC-012).
 *
 * Идемпотентность воспроизводится честно: повтор с тем же Idempotency-Key
 * возвращает исходный запуск и не создаёт второй (FR-012, SC-009).
 */
const RUN_SEQUENCE: ReviewRun['state'][] = ['queued', 'preparing', 'reviewing', 'validating', 'completed'];

export function happyPath(): RequestHandler[] {
  let polls = readState('polls', 0);
  // Состояние переживает перезагрузку страницы, поэтому запуск находится в
  // списке после возврата (US1-8), а повтор того же намерения не создаёт
  // второй запуск (FR-012, SC-009).
  const keys = new Map<string, ReviewRun>(Object.entries(readState<Record<string, ReviewRun>>('runsByKey', {})));
  const createdRuns: ReviewRun[] = readState<ReviewRun[]>('createdRuns', []);
  let decision: HumanDecision = readState<HumanDecision>('decision', fixtures.unreviewedDecision);
  let dialogue: FindingDialogue = readState<FindingDialogue>('dialogue', {
    ...fixtures.dialogueOpen,
    revision: 0,
    turn_count: 0,
    turns: [],
    can_send_message: true,
    blocked_reason: null,
  });

  const currentRun = (): ReviewRun => {
    const index = Math.min(polls, RUN_SEQUENCE.length - 1);
    const state = RUN_SEQUENCE[index]!;
    const finished = state === 'completed';
    return {
      ...fixtures.runQueued,
      id: fixtures.runId,
      state,
      progress: {
        percent: Math.round((index / (RUN_SEQUENCE.length - 1)) * 100),
        message: PROGRESS_TEXT[state] ?? '',
      },
      started_at: index > 0 ? '2026-09-04T09:01:01Z' : null,
      finished_at: finished ? '2026-09-04T09:01:14Z' : null,
      report_available: finished,
      error: null,
    };
  };

  return [
    http.post(`${API}/workspaces/:workspaceId/review-runs`, async ({ request }) => {
      const key = request.headers.get('Idempotency-Key') ?? '';
      const replayed = keys.get(key);
      if (replayed) {
        // Тот же ключ и то же тело воспроизводят исходный результат (FR-012).
        return HttpResponse.json(replayed, { status: 202 });
      }
      polls = 0;
      const created = { ...currentRun(), id: `60000000-0000-4000-8000-00000000000${createdRuns.length + 1}` };
      keys.set(key, created);
      createdRuns.unshift(created);
      writeState('polls', polls);
      writeState('runsByKey', Object.fromEntries(keys));
      writeState('createdRuns', createdRuns);
      return HttpResponse.json(created, { status: 202 });
    }),

    http.get(`${API}/workspaces/:workspaceId/review-runs`, () =>
      HttpResponse.json({ items: createdRuns, next_cursor: null }, { status: 200 }),
    ),


    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId`, ({ params }) => {
      const run = { ...currentRun(), id: String(params.runId) };
      polls += 1;
      writeState('polls', polls);
      return HttpResponse.json(run, { status: 200 });
    }),

    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/report`, () =>
      HttpResponse.json(fixtures.report, {
        status: 200,
        headers: { ETag: '"synthetic-report-v1"' },
      }),
    ),

    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/finding-states`, () =>
      HttpResponse.json(
        {
          items: [
            {
              finding_id: fixtures.findingId,
              decision,
              dialogue: {
                dialogue_id: dialogue.id,
                revision: dialogue.revision,
                state: dialogue.state,
                turn_count: dialogue.turn_count,
                can_send_message: dialogue.can_send_message,
                blocked_reason: dialogue.blocked_reason,
                policy: dialogue.policy,
              },
            },
          ],
        },
        { status: 200 },
      ),
    ),

    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/findings/:findingId/dialogue`, () =>
      HttpResponse.json(dialogue, { status: 200 }),
    ),

    http.post(
      `${API}/workspaces/:workspaceId/review-runs/:runId/findings/:findingId/dialogue/turns`,
      async ({ request }) => {
        const body = (await request.json()) as { message: string; expected_revision: number };
        if (body.expected_revision !== dialogue.revision) {
          return problem(409, 'revision_conflict', 'Версия диалога изменилась');
        }
        const completed = fixtures.dialogueOpen.turns[0]!;
        dialogue = {
          ...dialogue,
          revision: dialogue.revision + 1,
          turn_count: 1,
          state: 'open',
          can_send_message: true,
          blocked_reason: null,
          turns: [{ ...completed, member_message: body.message }],
        };
        writeState('dialogue', dialogue);
        return HttpResponse.json(dialogue, { status: 202 });
      },
    ),

    http.put(
      `${API}/workspaces/:workspaceId/review-runs/:runId/findings/:findingId/decision`,
      async ({ request }) => {
        const body = (await request.json()) as {
          status: HumanDecision['status'];
          reason: string | null;
          resolution: string | null;
          expected_revision: number;
        };
        if (body.expected_revision !== decision.revision) {
          return problem(409, 'revision_conflict', 'Версия решения изменилась');
        }
        decision =
          body.status === 'unreviewed'
            ? { ...fixtures.unreviewedDecision, revision: decision.revision + 1 }
            : {
                status: body.status,
                revision: decision.revision + 1,
                actor: fixtures.actor,
                reason: body.reason,
                resolution: body.resolution,
                decided_at: '2026-09-04T09:05:00Z',
              };
        // Решение закрывает диалог по замечанию (blocked_reason из контракта).
        dialogue = { ...dialogue, can_send_message: false, blocked_reason: 'human_decision_recorded' };
        writeState('decision', decision);
        writeState('dialogue', dialogue);
        return HttpResponse.json(decision, { status: 200 });
      },
    ),

    ...baseHandlers(),
  ];
}

const PROGRESS_TEXT: Partial<Record<ReviewRun['state'], string>> = {
  queued: 'Проверка поставлена в очередь',
  preparing: 'Готовим источники',
  reviewing: 'Идёт проверка документа',
  validating: 'Проверяем результат модели',
  completed: 'Проверка завершена',
};
