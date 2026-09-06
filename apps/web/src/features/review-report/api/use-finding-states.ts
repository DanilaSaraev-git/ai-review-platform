import { useGetReviewCycle, useListFindingStates } from '@/api/generated/endpoints';
import type { CycleEntry, FindingState } from '@/api/generated/model';
import { effectiveDecision } from '@/features/document-cycle/effective-decision';

/**
 * Изменяемые состояния замечаний: решение человека и сводка диалога.
 *
 * Отдельный ресурс и отдельный ключ кэша — именно они инвалидируются после
 * мутаций, тогда как отчёт остаётся нетронутым (FR-028, принцип V).
 */
export interface FindingStatesState {
  items: FindingState[];
  byFindingId: Map<string, FindingState>;
  rawByFindingId: Map<string, FindingState>;
  carriedByFindingId: Map<string, CycleEntry>;
  reviewedCount: number;
  isLoading: boolean;
  error: unknown;
  retry: () => Promise<void>;
}

export function useFindingStates(workspaceId: string, runId: string, enabled = true): FindingStatesState {
  const query = useListFindingStates(workspaceId, runId, {
    query: { enabled: Boolean(workspaceId && runId && enabled) },
  });
  const cycle = useGetReviewCycle(workspaceId, runId, { query: { enabled: Boolean(workspaceId && runId && enabled) } });

  const items = query.data?.items ?? [];
  const cycleEntries = new Map(cycle.data?.entries.filter((entry) => entry.current_finding_id).map((entry) => [entry.current_finding_id!, entry]) ?? []);
  const effectiveItems = items.map((item) => ({ ...item, decision: effectiveDecision(item.decision, cycleEntries.get(item.finding_id)) }));
  const carriedByFindingId = new Map(items.flatMap((item): [string, CycleEntry][] => {
    const entry = cycleEntries.get(item.finding_id);
    return item.decision.revision === 0 && entry?.decision_carried && entry.previous_decision ? [[item.finding_id, entry]] : [];
  }));

  return {
    items,
    byFindingId: new Map(effectiveItems.map((item) => [item.finding_id, item])),
    rawByFindingId: new Map(items.map((item) => [item.finding_id, item])),
    carriedByFindingId,
    reviewedCount: effectiveItems.filter((item) => item.decision.status !== 'unreviewed').length,
    isLoading: query.isPending,
    error: query.error ?? cycle.error,
    retry: async () => { await query.refetch(); await cycle.refetch(); },
  };
}
