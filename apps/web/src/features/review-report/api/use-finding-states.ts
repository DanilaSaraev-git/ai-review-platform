import { useListFindingStates } from '@/api/generated/endpoints';
import type { FindingState } from '@/api/generated/model';

/**
 * Изменяемые состояния замечаний: решение человека и сводка диалога.
 *
 * Отдельный ресурс и отдельный ключ кэша — именно они инвалидируются после
 * мутаций, тогда как отчёт остаётся нетронутым (FR-028, принцип V).
 */
export interface FindingStatesState {
  items: FindingState[];
  byFindingId: Map<string, FindingState>;
  reviewedCount: number;
  isLoading: boolean;
  error: unknown;
  retry: () => Promise<void>;
}

export function useFindingStates(workspaceId: string, runId: string, enabled = true): FindingStatesState {
  const query = useListFindingStates(workspaceId, runId, {
    query: { enabled: Boolean(workspaceId && runId && enabled) },
  });

  const items = query.data?.items ?? [];

  return {
    items,
    byFindingId: new Map(items.map((item) => [item.finding_id, item])),
    reviewedCount: items.filter((item) => item.decision.status !== 'unreviewed').length,
    isLoading: query.isPending,
    error: query.error,
    retry: async () => void (await query.refetch()),
  };
}
