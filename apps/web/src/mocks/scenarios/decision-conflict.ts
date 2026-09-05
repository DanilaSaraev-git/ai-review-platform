import { http } from 'msw';
import type { RequestHandler } from 'msw';
import { API, problem } from './base';
import { happyPath } from './happy-path';

/**
 * Сохранение решения поверх устаревшей ревизии: 409 revision_conflict.
 * Интерфейс обязан показать актуальное значение и сохранить введённый текст
 * (FR-027, SC-005).
 */
export function decisionConflict(): RequestHandler[] {
  return [
    http.put(`${API}/workspaces/:workspaceId/review-runs/:runId/findings/:findingId/decision`, () =>
      problem(409, 'revision_conflict', 'Версия решения изменилась', 'Обновите замечание и повторите действие.'),
    ),
    ...happyPath(),
  ];
}
