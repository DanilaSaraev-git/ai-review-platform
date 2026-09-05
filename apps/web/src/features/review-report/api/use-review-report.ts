import { useGetReviewReport } from '@/api/generated/endpoints';
import type { ReviewReport } from '@/api/generated/model';
import { isNotFound, isReportUnavailable } from '@/api/errors';
import { IMMUTABLE_REPORT_OPTIONS } from '@/api/query-keys';

/**
 * Неизменяемый отчёт (FR-018, принцип V).
 *
 * Ключ отчёта лежит отдельно от ключей finding-states и dialogue и не
 * инвалидируется ни одной мутацией: решения и диалог не могут изменить отчёт
 * не по дисциплине разработчика, а по устройству кэша (решение R-06).
 * Поэтому staleTime бесконечен, а автоматические перезапросы выключены.
 */
export interface ReviewReportState {
  report: ReviewReport | undefined;
  isLoading: boolean;
  /** Запуск не завершился успешно: отчёта нет и он не показывается частично. */
  isUnavailable: boolean;
  isNotFound: boolean;
  error: unknown;
}

export function useReviewReport(workspaceId: string, runId: string): ReviewReportState {
  const query = useGetReviewReport(workspaceId, runId, {
    query: {
      enabled: Boolean(workspaceId && runId),
      ...IMMUTABLE_REPORT_OPTIONS,
    },
  });

  return {
    report: query.data,
    isLoading: query.isPending,
    isUnavailable: isReportUnavailable(query.error),
    isNotFound: isNotFound(query.error),
    error: query.error,
  };
}
