import { useRef } from 'react';
import { idempotencyKeyFor } from '@/api/idempotency';
import { useCreateReviewRun as useGeneratedCreateReviewRun } from '@/api/generated/endpoints';
import type { ModelProfile, ReviewProfile, ReviewRun } from '@/api/generated/model';

/**
 * Создание фонового запуска (FR-011, FR-012).
 *
 * Каждое открытие формы — отдельное намерение. Сетевой повтор с прежними
 * параметрами сохраняет ключ; новая намеренная проверка получает новый ключ.
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
  const intentId = useRef(crypto.randomUUID());
  const headers = useRef(new Headers());
  const mutation = useGeneratedCreateReviewRun({ request: { headers: headers.current } });

  async function createRun(input: CreateRunInput): Promise<ReviewRun> {
    headers.current.set('Idempotency-Key', idempotencyKeyFor(`${intentId.current}:${JSON.stringify(input)}`));
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
