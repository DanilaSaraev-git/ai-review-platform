import type { HumanDecision } from '@/api/generated/model';
import { StatusBadge } from '@/components/ui';
import { DECISION_STATUS_TEXT } from '@/lib/error-messages';
import { formatDateTime } from '@/lib/format';

/**
 * Сохранённое решение с автором и временем (FR-028).
 * Хранится и показывается отдельно от отчёта: отчёт от решений не меняется.
 */
export function DecisionSummary({ decision }: { decision: HumanDecision | undefined }) {
  if (!decision || decision.status === 'unreviewed') {
    return (
      <p className="text-xs text-ink-muted">
        <StatusBadge>Не рассмотрено</StatusBadge>
      </p>
    );
  }

  return (
    <dl className="text-xs">
      <div className="mb-1">
        <dt className="sr-only">Статус</dt>
        <dd>
          <StatusBadge tone="ok">{DECISION_STATUS_TEXT[decision.status]}</StatusBadge>
        </dd>
      </div>
      {decision.reason ? (
        <div>
          <dt className="font-medium text-ink">Обоснование</dt>
          <dd className="text-ink-muted">{decision.reason}</dd>
        </div>
      ) : null}
      {decision.resolution ? (
        <div className="mt-1">
          <dt className="font-medium text-ink">Резолюция</dt>
          <dd className="text-ink-muted">{decision.resolution}</dd>
        </div>
      ) : null}
      {decision.actor ? (
        <div className="mt-1">
          <dt className="font-medium text-ink">Сохранил</dt>
          <dd className="text-ink-muted">
            {decision.actor.display_name}, {formatDateTime(decision.decided_at)}
          </dd>
        </div>
      ) : null}
    </dl>
  );
}
