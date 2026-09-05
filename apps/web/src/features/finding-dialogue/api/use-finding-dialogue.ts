import { useGetFindingDialogue } from '@/api/generated/endpoints';
import type { FindingDialogue } from '@/api/generated/model';
import { dialoguePollInterval, isDialogueGenerating } from '@/api/polling';

/**
 * Диалог одного замечания (FR-030, FR-033).
 *
 * Опрос включён, пока идёт генерация хода, и выключается по её завершении:
 * завершение видно не позднее 2 секунд (SC-012).
 *
 * Доступность отправки берётся строго из серверного can_send_message — клиент
 * её не вычисляет, иначе разошёлся бы с правилами политики диалога (R-08).
 */
export interface FindingDialogueState {
  dialogue: FindingDialogue | undefined;
  canSendMessage: boolean;
  isGenerating: boolean;
  isLoading: boolean;
  error: unknown;
}

export function useFindingDialogue(workspaceId: string, runId: string, findingId: string): FindingDialogueState {
  const query = useGetFindingDialogue(workspaceId, runId, findingId, {
    query: {
      enabled: Boolean(workspaceId && runId && findingId),
      refetchInterval: (q) => dialoguePollInterval(q.state.data),
      refetchIntervalInBackground: false,
    },
  });

  const dialogue = query.data;

  return {
    dialogue,
    canSendMessage: dialogue?.can_send_message ?? false,
    isGenerating: isDialogueGenerating(dialogue),
    isLoading: query.isPending,
    error: query.error,
  };
}
