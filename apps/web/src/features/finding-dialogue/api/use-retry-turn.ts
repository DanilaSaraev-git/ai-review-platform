import { useQueryClient } from '@tanstack/react-query';
import { useRetryFindingDialogueTurn } from '@/api/generated/endpoints';
import type { FindingDialogue } from '@/api/generated/model';
import { invalidateAfterDialogueTurn } from '@/api/query-keys';

/**
 * Повтор генерации неудавшегося хода (FR-035).
 * Вопрос вводить заново не нужно: повторяется существующий ход.
 */
export function useRetryTurn(workspaceId: string, runId: string, findingId: string) {
  const queryClient = useQueryClient();
  const mutation = useRetryFindingDialogueTurn();

  async function retry(turnId: string, expectedRevision: number): Promise<FindingDialogue> {
    const dialogue = await mutation.mutateAsync({
      workspaceId,
      runId,
      findingId,
      turnId,
      data: { expected_revision: expectedRevision },
    });
    await invalidateAfterDialogueTurn(queryClient, workspaceId, runId, findingId);
    return dialogue;
  }

  return { retry, isPending: mutation.isPending, error: mutation.error };
}
