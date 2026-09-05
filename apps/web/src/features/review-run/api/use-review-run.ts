import { useEffect, useRef, useState } from 'react';
import { useGetReviewRun } from '@/api/generated/endpoints';
import type { ReviewRun } from '@/api/generated/model';
import { isTerminalRunState, runPollInterval } from '@/api/polling';
import { runProgressState, runStateFingerprint, type RunProgressState } from '../lib/stall-detector';

/**
 * Наблюдение за фоновым запуском (FR-014, SC-012).
 *
 * Опрос идёт с интервалом 2000 мс и выключается при переходе в терминальное
 * состояние. Момент последней смены состояния запоминается, чтобы вычислить
 * признак «идёт дольше обычного» (FR-039).
 */
export interface ReviewRunState {
  run: ReviewRun | undefined;
  progress: RunProgressState;
  isTerminal: boolean;
  isLoading: boolean;
  error: unknown;
}

export function useReviewRun(workspaceId: string, runId: string): ReviewRunState {
  const query = useGetReviewRun(workspaceId, runId, {
    query: {
      enabled: Boolean(workspaceId && runId),
      refetchInterval: (q) => runPollInterval(q.state.data),
      refetchIntervalInBackground: false,
    },
  });

  const run = query.data;
  const fingerprint = run ? runStateFingerprint(run) : null;
  const lastFingerprint = useRef<string | null>(null);
  const [lastChangeAt, setLastChangeAt] = useState<number | null>(null);

  useEffect(() => {
    if (!fingerprint || fingerprint === lastFingerprint.current) {
      return;
    }
    const isFirstObservation = lastFingerprint.current === null;
    lastFingerprint.current = fingerprint;
    // Первое наблюдение не является сменой состояния: иначе давно идущий
    // запуск, открытый только что, никогда не показал бы предупреждение.
    // В этом случае отсчёт ведётся от начала запуска (FR-039).
    if (!isFirstObservation) {
      setLastChangeAt(Date.now());
    }
  }, [fingerprint]);

  return {
    run,
    progress: runProgressState(run, lastChangeAt),
    isTerminal: run ? isTerminalRunState(run.state) : false,
    isLoading: query.isPending,
    error: query.error,
  };
}
