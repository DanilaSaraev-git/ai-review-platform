import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import * as fixtures from '@/mocks/fixtures';
import { API } from './base';
import { happyPath } from './happy-path';

/**
 * Ход завершился ошибкой: причина показана, повтор доступен без повторного
 * ввода вопроса (FR-035).
 *
 * После успешного повтора диалог отдаёт завершённый ход: иначе проверка
 * повтора была бы неотличима от бездействия.
 */
export function dialogueFailed(): RequestHandler[] {
  let retried = false;

  return [
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/findings/:findingId/dialogue`, () =>
      HttpResponse.json(retried ? fixtures.dialogueOpen : fixtures.dialogueFailed, { status: 200 }),
    ),
    http.post(
      `${API}/workspaces/:workspaceId/review-runs/:runId/findings/:findingId/dialogue/turns/:turnId/retry`,
      () => {
        retried = true;
        return HttpResponse.json(fixtures.dialogueOpen, { status: 202 });
      },
    ),
    ...happyPath(),
  ];
}
