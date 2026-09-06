import { Button, Callout, Spinner } from '@/components/ui';
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
  const { dialogue, isLoading, error, retry: retryDialogue } = useFindingDialogue(workspaceId, runId, findingId);
  const { retry, isPending: isRetrying } = useRetryTurn(workspaceId, runId, findingId);

  if (isLoading && !dialogue) {
    return <Spinner label="Загружаем диалог…" />;
  }

  if (!dialogue) {
    return (
      <div className="p-4">
        <Callout tone="danger" title="Не удалось загрузить диалог">
          <Button className="mt-2" onClick={() => void retryDialogue()}>Повторить</Button>
        </Callout>
      </div>
    );
  }

  return (
    <section aria-labelledby="dialogue-title" className="flex min-h-full flex-col gap-4 bg-surface p-4">
      <h2 id="dialogue-title" className="text-[15px] font-semibold text-ink">
        Диалог по замечанию
      </h2>

      {error ? (
        <Callout tone="warn" title="Не удалось обновить диалог">
          Черновик и загруженная история сохранены.
          <Button className="ml-2" onClick={() => void retryDialogue()}>Повторить</Button>
        </Callout>
      ) : null}

      <div className="min-h-0 lg:flex-1 lg:overflow-y-auto">
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
      </div>

      <div className="mt-auto shrink-0 border-t border-line bg-surface pt-3">
        <TurnComposer workspaceId={workspaceId} runId={runId} findingId={findingId} dialogue={dialogue} />
      </div>
    </section>
  );
}
