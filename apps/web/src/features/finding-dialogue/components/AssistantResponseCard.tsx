import type { DialogueTurn } from '@/api/generated/model';
import { Button, Callout, StatusBadge } from '@/components/ui';
import { ASSISTANT_ACTION_TEXT, DIALOGUE_ERROR_TEXT } from '@/lib/error-messages';
import { ProposedResolutionCard } from './ProposedResolutionCard';

/**
 * Ответ на ход: текст, вид ответа, привязки и предложенная резолюция (FR-034).
 * Ход с ошибкой показывает причину и, если повтор допустим, предлагает его
 * без повторного ввода вопроса (FR-035).
 */
export function AssistantResponseCard({
  turn,
  onRetry,
  isRetrying,
  onUseResolution,
}: {
  turn: DialogueTurn;
  onRetry: (turnId: string) => void;
  isRetrying: boolean;
  onUseResolution?: (text: string) => void;
}) {
  if (turn.state === 'queued' || turn.state === 'generating') {
    return (
      <p role="status" className="text-sm text-ink-muted">
        <span aria-hidden="true" className="mr-1.5">
          ⟳
        </span>
        Ответ готовится…
      </p>
    );
  }

  if (turn.state === 'failed') {
    return (
      <Callout tone="danger" title="Ответ не получен">
        <p>{turn.error ? DIALOGUE_ERROR_TEXT[turn.error.code] : 'Ход завершился ошибкой.'}</p>
        {turn.error?.retryable ? (
          <Button className="mt-2" onClick={() => onRetry(turn.id)} disabled={isRetrying}>
            {isRetrying ? 'Повторяем…' : 'Повторить ход'}
          </Button>
        ) : (
          <p className="mt-1">Повтор не поможет: попробуйте другой вопрос.</p>
        )}
      </Callout>
    );
  }

  const response = turn.assistant_response;
  if (!response) {
    return null;
  }

  return (
    <div className="rounded border border-line bg-surface p-3">
      <StatusBadge>{ASSISTANT_ACTION_TEXT[response.action]}</StatusBadge>
      <p className="mt-2 text-sm text-ink">{response.content}</p>

      {response.anchors.length > 0 ? (
        <ul className="mt-2 flex flex-col gap-1">
          {response.anchors.map((anchor) => (
            <li key={`${anchor.fragment_id}-${anchor.quote_start}`} className="text-xs text-ink-muted">
              <span className="font-medium text-ink">{anchor.source_name}: </span>
              «{anchor.quote}»
            </li>
          ))}
        </ul>
      ) : null}

      {response.proposed_resolution ? (
        <div className="mt-3">
          <ProposedResolutionCard proposal={response.proposed_resolution} onUse={onUseResolution} />
        </div>
      ) : null}
    </div>
  );
}
