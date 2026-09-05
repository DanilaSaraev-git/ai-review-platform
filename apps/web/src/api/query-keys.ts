import type { QueryClient } from '@tanstack/react-query';
import {
  getGetFindingDialogueQueryKey,
  getGetReviewReportQueryKey,
  getGetReviewRunQueryKey,
  getListFindingStatesQueryKey,
} from '@/api/generated/endpoints';

/**
 * Разделение неизменяемого отчёта и изменяемых состояний замечаний
 * (решение R-06, принцип V).
 *
 * Ключ отчёта существует отдельно и не инвалидируется ни одной мутацией.
 * Функции инвалидации ниже — единственный способ сбросить серверное состояние
 * после решения или хода диалога, и отчёт в них не входит.
 */
export const reportKey = getGetReviewReportQueryKey;
export const findingStatesKey = getListFindingStatesQueryKey;
export const dialogueKey = getGetFindingDialogueQueryKey;
export const runKey = getGetReviewRunQueryKey;

/** Отчёт неизменяем: держим его в кэше без устаревания. */
export const IMMUTABLE_REPORT_OPTIONS = {
  staleTime: Number.POSITIVE_INFINITY,
  gcTime: Number.POSITIVE_INFINITY,
  refetchOnMount: false,
  refetchOnWindowFocus: false,
  refetchOnReconnect: false,
} as const;

/**
 * После сохранения решения обновляются только состояния замечаний и диалог
 * этого замечания: сохранение решения может закрыть диалог с
 * blocked_reason = human_decision_recorded (FR-028, FR-037).
 */
export async function invalidateAfterDecision(
  queryClient: QueryClient,
  workspaceId: string,
  runId: string,
  findingId: string,
): Promise<void> {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: findingStatesKey(workspaceId, runId) }),
    queryClient.invalidateQueries({ queryKey: dialogueKey(workspaceId, runId, findingId) }),
  ]);
}

/** После хода диалога обновляются диалог и сводка состояний, но не отчёт. */
export async function invalidateAfterDialogueTurn(
  queryClient: QueryClient,
  workspaceId: string,
  runId: string,
  findingId: string,
): Promise<void> {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: dialogueKey(workspaceId, runId, findingId) }),
    queryClient.invalidateQueries({ queryKey: findingStatesKey(workspaceId, runId) }),
  ]);
}
