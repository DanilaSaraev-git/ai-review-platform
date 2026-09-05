import { useQueryClient } from '@tanstack/react-query';
import { usePutFindingDecision as useGeneratedPutDecision } from '@/api/generated/endpoints';
import type { HumanDecision, PutFindingDecision } from '@/api/generated/model';
import { invalidateAfterDecision } from '@/api/query-keys';

/**
 * Сохранение решения человека (FR-027, FR-028).
 *
 * expected_revision отправляется всегда: устаревшая ревизия обязана получить
 * 409, а не молча затереть чужое решение. После успеха инвалидируются только
 * состояния замечаний и диалог — ключ отчёта не трогается (принцип V).
 */
export function usePutDecision(workspaceId: string, runId: string, findingId: string) {
  const queryClient = useQueryClient();
  const mutation = useGeneratedPutDecision();

  async function save(body: PutFindingDecision): Promise<HumanDecision> {
    const decision = await mutation.mutateAsync({ workspaceId, runId, findingId, data: body });
    await invalidateAfterDecision(queryClient, workspaceId, runId, findingId);
    return decision;
  }

  return {
    save,
    isPending: mutation.isPending,
    error: mutation.error,
    reset: mutation.reset,
  };
}
