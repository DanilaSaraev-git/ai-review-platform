import { useQueryClient } from '@tanstack/react-query';
import { useCreateFindingDialogueTurn } from '@/api/generated/endpoints';
import type { FindingDialogue } from '@/api/generated/model';
import { isRevisionConflict } from '@/api/errors';
import { dialogueKey, invalidateAfterDialogueTurn } from '@/api/query-keys';

/**
 * Отправка одного хода по замечанию (FR-031, FR-036).
 *
 * expected_revision отправляется всегда: ход поверх устаревшей ревизии обязан
 * получить 409. Ключ идемпотентности привязан к намерению — конкретному
 * вопросу при конкретной ревизии, поэтому повтор отправки не создаёт второй ход.
 */
export function useCreateTurn(workspaceId: string, runId: string, findingId: string) {
  const queryClient = useQueryClient();
  const mutation = useCreateFindingDialogueTurn();

  async function send(message: string, expectedRevision: number, attachmentDocumentIds: string[] = []): Promise<FindingDialogue> {
    let dialogue: FindingDialogue;
    try {
      dialogue = await mutation.mutateAsync({
        workspaceId,
        runId,
        findingId,
        data: { message, expected_revision: expectedRevision, ...(attachmentDocumentIds.length ? { attachment_document_ids: attachmentDocumentIds } : {}) },
      });
    } catch (error) {
      if (isRevisionConflict(error)) {
        await queryClient.refetchQueries({ queryKey: dialogueKey(workspaceId, runId, findingId), exact: true });
      }
      throw error;
    }
    await invalidateAfterDialogueTurn(queryClient, workspaceId, runId, findingId);
    return dialogue;
  }

  return { send, isPending: mutation.isPending, error: mutation.error, reset: mutation.reset };
}
