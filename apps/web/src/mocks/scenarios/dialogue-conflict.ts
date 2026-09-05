import { http } from 'msw';
import type { RequestHandler } from 'msw';
import { API, problem } from './base';
import { happyPath } from './happy-path';

/** Отправка хода поверх устаревшей ревизии диалога (FR-036). */
export function dialogueConflict(): RequestHandler[] {
  return [
    http.post(`${API}/workspaces/:workspaceId/review-runs/:runId/findings/:findingId/dialogue/turns`, () =>
      problem(409, 'revision_conflict', 'Версия диалога изменилась', 'Обновите диалог и повторите отправку.'),
    ),
    ...happyPath(),
  ];
}
