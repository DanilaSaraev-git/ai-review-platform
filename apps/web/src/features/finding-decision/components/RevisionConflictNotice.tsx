import type { HumanDecision } from '@/api/generated/model';
import { Button, Callout } from '@/components/ui';
import { DECISION_STATUS_TEXT } from '@/lib/error-messages';
import { formatDateTime } from '@/lib/format';
import type { ConflictState } from '../lib/conflict';

/**
 * Состояние конфликта ревизии (FR-027, SC-005).
 *
 * Показывает актуальное сохранённое значение рядом с введённым текстом,
 * который остаётся в форме, и предлагает повторить действие одним нажатием
 * уже с новой ревизией.
 */
export function RevisionConflictNotice({
  conflict,
  current,
  onRetry,
  isRetrying,
}: {
  conflict: ConflictState;
  current: HumanDecision | undefined;
  onRetry: () => void;
  isRetrying: boolean;
}) {
  if (!conflict.isConflict) {
    return null;
  }

  return (
    <div role="alert">
      <Callout tone="warn" title={conflict.title}>
        <p>{conflict.hint}</p>
        {current ? (
          <dl className="mt-2 text-xs">
            <div>
              <dt className="inline font-medium text-ink">Актуальный статус: </dt>
              <dd className="inline text-ink-muted">{DECISION_STATUS_TEXT[current.status]}</dd>
            </div>
            {current.reason ? (
              <div>
                <dt className="inline font-medium text-ink">Обоснование: </dt>
                <dd className="inline text-ink-muted">{current.reason}</dd>
              </div>
            ) : null}
            {current.actor ? (
              <div>
                <dt className="inline font-medium text-ink">Сохранил: </dt>
                <dd className="inline text-ink-muted">
                  {current.actor.display_name}, {formatDateTime(current.decided_at)}
                </dd>
              </div>
            ) : null}
          </dl>
        ) : null}
        <Button className="mt-3" variant="primary" onClick={onRetry} disabled={isRetrying}>
          {isRetrying ? 'Повторяем…' : 'Повторить с актуальной версией'}
        </Button>
      </Callout>
    </div>
  );
}
