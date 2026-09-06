import type { DialogueTurn } from '@/api/generated/model';
import { formatDateTime } from '@/lib/format';
import { AssistantResponseCard } from './AssistantResponseCard';

/** История ходов в порядке отправки (FR-030). */
export function TurnList({
  turns,
  onRetry,
  isRetrying,
  onUseResolution,
}: {
  turns: readonly DialogueTurn[];
  onRetry: (turnId: string) => void;
  isRetrying: boolean;
  onUseResolution?: (text: string) => void;
}) {
  if (turns.length === 0) {
    return <p className="py-2 text-sm leading-6 text-ink-muted">Диалога по этому замечанию ещё не было.</p>;
  }

  const ordered = [...turns].sort((left, right) => left.ordinal - right.ordinal);

  return (
    <ol className="flex min-w-0 flex-col gap-7">
      {ordered.map((turn) => (
        <li key={turn.id} className="flex min-w-0 flex-col gap-4">
          <div className="ml-5 rounded-lg bg-surface-muted px-4 py-3">
            <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xs">
              <span className="font-medium text-ink">{turn.actor.display_name}</span>
              <span className="text-ink-subtle">{formatDateTime(turn.created_at)}</span>
            </p>
            <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-ink">{turn.member_message}</p>
          </div>
          <AssistantResponseCard
            turn={turn}
            onRetry={onRetry}
            isRetrying={isRetrying}
            onUseResolution={onUseResolution}
          />
        </li>
      ))}
    </ol>
  );
}
