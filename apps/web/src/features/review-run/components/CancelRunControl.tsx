import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useCancelReviewRun } from '@/api/generated/endpoints';
import type { ReviewRun } from '@/api/generated/model';
import { isProblem } from '@/api/errors';
import { isTerminalRunState } from '@/api/polling';
import { runKey } from '@/api/query-keys';
import { Button } from '@/components/ui';

export function CancelRunControl({ workspaceId, run, isOffline }: {
  workspaceId: string;
  run: ReviewRun;
  isOffline: boolean;
}) {
  const cache = useQueryClient();
  const mutation = useCancelReviewRun();
  const [message, setMessage] = useState('');
  const terminal = isTerminalRunState(run.state);
  const cancellationRequested = !terminal && Boolean(run.cancel_requested_at);

  async function cancel() {
    setMessage('');
    try {
      const result = await mutation.mutateAsync({ workspaceId, runId: run.id });
      // A poll started before cancellation must not overwrite its confirmed state.
      await cache.cancelQueries({ queryKey: runKey(workspaceId, run.id) });
      cache.setQueryData(runKey(workspaceId, run.id), result);
    } catch (error) {
      setMessage(isProblem(error) && error.code === 'run_terminal'
        ? 'Проверка уже остановлена или завершена. Обновляем состояние.'
        : 'Не удалось подтвердить отмену. Обновите состояние или повторите попытку.');
      void cache.invalidateQueries({ queryKey: runKey(workspaceId, run.id) });
    } finally {
      // The list and history use separate queries for the same run.
      for (const key of ['latest-family-run', 'family-runs']) {
        void cache.invalidateQueries({ queryKey: [key, workspaceId] });
      }
    }
  }

  return <div className="mt-4">
    {!terminal ? <Button disabled={!workspaceId || isOffline || mutation.isPending || cancellationRequested} onClick={() => void cancel()}>
      {mutation.isPending ? 'Отменяем проверку…' : cancellationRequested ? 'Отмена запрошена' : 'Отменить проверку'}
    </Button> : null}
    {message ? <p role="alert" className="mt-2 text-sm text-ink-muted">{message}
      <Button className="ml-2" onClick={() => void cache.invalidateQueries({ queryKey: runKey(workspaceId, run.id) })}>Обновить состояние</Button>
    </p> : null}
  </div>;
}
