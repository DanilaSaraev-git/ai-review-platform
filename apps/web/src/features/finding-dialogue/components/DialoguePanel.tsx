import { Spinner } from '@/components/ui';
import { useFindingDialogue } from '../api/use-finding-dialogue';
import { useRetryTurn } from '../api/use-retry-turn';
import { TurnComposer } from './TurnComposer';
import { TurnList } from './TurnList';

/**
 * Диалог, привязанный к одному замечанию (FR-030).
 * Панель не превращается в отдельный чат: она всегда открыта из конкретного
 * замечания и показывает только его ходы.
 */
export function DialoguePanel({
  workspaceId,
  runId,
  findingId,
  onUseResolution,
}: {
  workspaceId: string;
  runId: string;
  findingId: string;
  onUseResolution?: (text: string) => void;
}) {
  const { dialogue, isLoading } = useFindingDialogue(workspaceId, runId, findingId);
  const { retry, isPending: isRetrying } = useRetryTurn(workspaceId, runId, findingId);

  if (isLoading || !dialogue) {
    return <Spinner label="Загружаем диалог…" />;
  }

  return (
    <section aria-labelledby="dialogue-title" className="flex flex-col gap-4 rounded border border-line bg-surface p-4">
      <h2 id="dialogue-title" className="text-sm font-semibold text-ink">
        Диалог по замечанию
      </h2>

      <TurnList
        turns={dialogue.turns}
        onRetry={(turnId) => {
          retry(turnId, dialogue.revision).catch(() => {
            // Причина повторной неудачи показывается в карточке хода.
          });
        }}
        isRetrying={isRetrying}
        onUseResolution={onUseResolution}
      />

      <TurnComposer workspaceId={workspaceId} runId={runId} findingId={findingId} dialogue={dialogue} />
    </section>
  );
}
