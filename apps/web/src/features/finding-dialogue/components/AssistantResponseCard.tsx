import type { DialogueTurn } from '@/api/generated/model';
import { Button, Callout } from '@/components/ui';
import { ASSISTANT_ACTION_TEXT, DIALOGUE_ERROR_TEXT } from '@/lib/error-messages';

/**
 * Ответ на ход: текст, вид ответа, привязки и предложенная резолюция (FR-034).
 * Ход с ошибкой показывает причину и, если повтор допустим, предлагает его
 * без повторного ввода вопроса (FR-035).
 */
export function AssistantResponseCard({
  turn,
  onRetry,
  isRetrying,
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
    <div className="min-w-0 py-1">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xs">
        <span className="font-medium text-ink">Numbat</span>
        <span className="text-ink-subtle">{ASSISTANT_ACTION_TEXT[response.action]}</span>
      </div>
      <p className="mt-2 max-w-[72ch] whitespace-pre-wrap break-words text-sm leading-6 text-ink">{response.content}</p>

      {response.anchors.length > 0 ? (
        <ul className="mt-3 flex flex-col gap-3 border-l-2 border-line pl-3">
          {response.anchors.map((anchor) => (
            <li key={`${anchor.fragment_id}-${anchor.quote_start}`} className="break-words text-xs leading-6 text-ink-muted">
              <span className="block font-medium text-ink">{anchor.source_name}</span>
              <blockquote className="whitespace-pre-wrap">«{anchor.quote}»</blockquote>
            </li>
          ))}
        </ul>
      ) : null}


    </div>
  );
}
