import { useCreateReviewRun as useGeneratedCreateReviewRun } from '@/api/generated/endpoints';
import type { ModelProfile, ReviewProfile, ReviewRun } from '@/api/generated/model';

/**
 * Создание фонового запуска (FR-011, FR-012).
 *
 * Ключ идемпотентности вырабатывается по намерению — набору входов формы, —
 * поэтому повторное нажатие или повтор после разрыва связи возвращают исходный
 * запуск, а не создают второй (решение R-05, SC-009).
 */
export interface CreateRunInput {
  workspaceId: string;
  documentId: string;
  contextDocumentIds: readonly string[];
  profile: ReviewProfile;
  modelProfile: ModelProfile;
  locale?: string;
}

export function useCreateReviewRun() {
  const mutation = useGeneratedCreateReviewRun();

  async function createRun(input: CreateRunInput): Promise<ReviewRun> {
    // Ключ идемпотентности вырабатывается в mutator по телу запроса, поэтому
    // одинаковый набор входов даёт один и тот же ключ (решение R-05).
    return mutation.mutateAsync({
      workspaceId: input.workspaceId,
      data: {
        document_id: input.documentId,
        context_document_ids: [...input.contextDocumentIds],
        profile: { id: input.profile.id, version: input.profile.version },
        model_profile: { id: input.modelProfile.id, version: input.modelProfile.version },
        locale: input.locale ?? 'ru-RU',
      },
    });
  }

  return {
    createRun,
    isPending: mutation.isPending,
    error: mutation.error,
  };
}
