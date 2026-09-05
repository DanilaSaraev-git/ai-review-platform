import type { FindingDialogue, ReviewRun } from '@/api/generated/model';

/**
 * Правила наблюдения за фоновой работой (решение R-02).
 *
 * Интервал 2000 мс обеспечивает SC-012: изменение состояния запуска или
 * завершение хода диалога видны аналитику не позднее 2 секунд. Опрос включён
 * только в нетерминальных состояниях и выключается при переходе в терминальное.
 */
export const POLL_INTERVAL_MS = 2000;

/** Порог, после которого запуск считается идущим дольше обычного (FR-039). */
export const STALL_THRESHOLD_MS = 15 * 60 * 1000;

const TERMINAL_RUN_STATES: ReadonlySet<ReviewRun['state']> = new Set(['completed', 'failed', 'cancelled']);

export function isTerminalRunState(state: ReviewRun['state']): boolean {
  return TERMINAL_RUN_STATES.has(state);
}

/** Интервал опроса запуска: false выключает опрос на терминальном состоянии. */
export function runPollInterval(run: ReviewRun | undefined): number | false {
  if (!run) {
    return POLL_INTERVAL_MS;
  }
  return isTerminalRunState(run.state) ? false : POLL_INTERVAL_MS;
}

/**
 * Диалог опрашивается, пока идёт генерация: состояние диалога generating либо
 * есть ход в состоянии queued или generating (FR-033).
 */
export function isDialogueGenerating(dialogue: FindingDialogue | undefined): boolean {
  if (!dialogue) {
    return false;
  }
  if (dialogue.state === 'generating') {
    return true;
  }
  return dialogue.turns.some((turn) => turn.state === 'queued' || turn.state === 'generating');
}

export function dialoguePollInterval(dialogue: FindingDialogue | undefined): number | false {
  return isDialogueGenerating(dialogue) ? POLL_INTERVAL_MS : false;
}
