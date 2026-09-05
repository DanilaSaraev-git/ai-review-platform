import { Link } from 'react-router';
import type { Finding, FindingState } from '@/api/generated/model';
import { StatusBadge } from '@/components/ui';
import { DECISION_STATUS_TEXT, FINDING_KIND_TEXT, PRIORITY_TEXT } from '@/lib/error-messages';

/**
 * Карточка замечания (FR-020).
 * Все поля — только чтение: интерфейс не предлагает править результат модели.
 * Решение человека приходит отдельным ресурсом и показывается рядом (FR-028).
 */
const PRIORITY_TONE = { high: 'danger', medium: 'warn', low: 'neutral' } as const;

export function FindingCard({
  finding,
  state,
  runId,
  isSelected = false,
}: {
  finding: Finding;
  state: FindingState | undefined;
  runId: string;
  isSelected?: boolean;
}) {
  const decision = state?.decision;

  return (
    <article
      aria-current={isSelected ? 'true' : undefined}
      className={`rounded border p-3 ${isSelected ? 'border-accent bg-surface' : 'border-line bg-surface'}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge tone={PRIORITY_TONE[finding.priority.level]}>
          {PRIORITY_TEXT[finding.priority.level]} приоритет
        </StatusBadge>
        <StatusBadge>{FINDING_KIND_TEXT[finding.kind]}</StatusBadge>
        {decision ? (
          <StatusBadge tone={decision.status === 'unreviewed' ? 'neutral' : 'ok'}>
            {DECISION_STATUS_TEXT[decision.status]}
          </StatusBadge>
        ) : null}
      </div>

      <h3 className="mt-2 text-sm font-semibold text-ink">
        <Link className="underline" to={`/runs/${runId}/report/findings/${finding.id}`}>
          {finding.ordinal}. {finding.title}
        </Link>
      </h3>

      <dl className="mt-2 flex flex-col gap-2 text-xs">
        <div>
          <dt className="font-medium text-ink">Проблема</dt>
          <dd className="text-ink-muted">{finding.problem}</dd>
        </div>
        <div>
          <dt className="font-medium text-ink">Почему это важно</dt>
          <dd className="text-ink-muted">{finding.reason}</dd>
        </div>
        <div>
          <dt className="font-medium text-ink">Вопрос для уточнения</dt>
          <dd className="text-ink-muted">{finding.question}</dd>
        </div>
        <div>
          <dt className="font-medium text-ink">Обоснование приоритета</dt>
          <dd className="text-ink-muted">{finding.priority.rationale}</dd>
        </div>
      </dl>
    </article>
  );
}
