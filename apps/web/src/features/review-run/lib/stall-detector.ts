import type { ReviewRun } from '@/api/generated/model';
import { STALL_THRESHOLD_MS, isTerminalRunState } from '@/api/polling';

/**
 * Признак «идёт дольше обычного» (FR-039, SC-013).
 *
 * Контракт не содержит поля таймаута, поэтому признак вычисляется на клиенте
 * как отсутствие смены состояния дольше порога (решение R-03). Он не подменяет
 * состояние запуска и не прекращает опрос — только объясняет ожидание.
 */
export const STALL_WARNING =
  'Проверка идёт дольше обычного. Можно закрыть страницу и вернуться к запуску позже — работа продолжится.';

export interface RunProgressState {
  /** Сколько идёт запуск от старта или создания. */
  durationMs: number;
  isStalled: boolean;
  warning: string | null;
}

/** Отпечаток наблюдаемого состояния: его смена сбрасывает отсчёт застревания. */
export function runStateFingerprint(run: ReviewRun): string {
  return `${run.state}|${run.progress?.percent ?? ''}|${run.progress?.message ?? ''}`;
}

export function runProgressState(
  run: ReviewRun | undefined,
  lastChangeAt: number | null,
  now: number = Date.now(),
): RunProgressState {
  if (!run) {
    return { durationMs: 0, isStalled: false, warning: null };
  }

  const startedAt = run.started_at ?? run.created_at;
  const startMs = new Date(startedAt).valueOf();
  const finishedMs = run.finished_at ? new Date(run.finished_at).valueOf() : now;
  const durationMs = Number.isNaN(startMs) ? 0 : Math.max(0, finishedMs - startMs);

  if (isTerminalRunState(run.state)) {
    return { durationMs, isStalled: false, warning: null };
  }

  // Отсчёт идёт от последней замеченной смены состояния; если интерфейс
  // открыт только что, отсчёт ведётся от начала запуска.
  const unchangedSince = lastChangeAt ?? (Number.isNaN(startMs) ? now : startMs);
  const isStalled = now - unchangedSince >= STALL_THRESHOLD_MS;

  return {
    durationMs,
    isStalled,
    warning: isStalled ? STALL_WARNING : null,
  };
}
