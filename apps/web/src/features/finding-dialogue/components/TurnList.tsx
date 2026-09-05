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
    return <p className="text-sm text-ink-muted">Диалога по этому замечанию ещё не было.</p>;
  }

  const ordered = [...turns].sort((left, right) => left.ordinal - right.ordinal);

  return (
    <ol className="flex flex-col gap-4">
      {ordered.map((turn) => (
        <li key={turn.id} className="flex flex-col gap-2">
          <div className="rounded border border-line bg-surface-muted p-3">
            <p className="text-xs font-medium text-ink">
              {turn.actor.display_name} · {formatDateTime(turn.created_at)}
            </p>
            <p className="mt-1 text-sm text-ink">{turn.member_message}</p>
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
