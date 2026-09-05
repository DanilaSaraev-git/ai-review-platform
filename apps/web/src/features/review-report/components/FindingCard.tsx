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
      className={`rounded-[6px] border bg-surface p-3.5 transition-[border-color,box-shadow] duration-100 ${isSelected ? 'border-accent shadow-[inset_3px_0_0_var(--color-accent)]' : 'border-line hover:border-line-strong'}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge tone={PRIORITY_TONE[finding.priority.level]}>
          {PRIORITY_TEXT[finding.priority.level]}
        </StatusBadge>
        {decision ? (
          <StatusBadge tone={decision.status === 'unreviewed' ? 'neutral' : 'ok'}>
            {DECISION_STATUS_TEXT[decision.status]}
          </StatusBadge>
        ) : null}
      </div>

      <h3 className="mt-2.5 text-[14px] font-semibold leading-5 text-ink">
        <Link className="hover:text-accent" to={`/runs/${runId}/report/findings/${finding.id}`}>
          <span className="mr-1 text-xs font-medium text-ink-subtle">{finding.ordinal}.</span> {finding.title}
        </Link>
      </h3>

      <dl className="mt-2 flex flex-col gap-2 text-[13px] leading-5">
        <div>
          <dt className="sr-only">Проблема</dt>
          <dd className="text-ink-muted">{finding.problem}</dd>
        </div>
        <div className="rounded-[5px] bg-surface-muted px-3 py-2">
          <dt className="text-[11px] font-semibold uppercase tracking-[0.04em] text-ink-subtle">Вопрос для уточнения</dt>
          <dd className="mt-0.5 text-ink">{finding.question}</dd>
        </div>
      </dl>

      <details className="mt-2.5 text-xs text-ink-muted">
        <summary className="cursor-pointer font-semibold text-ink-muted hover:text-ink">Подробнее</summary>
        <dl className="mt-2 grid gap-2 border-t border-line pt-2 leading-5">
          <div>
            <dt className="font-semibold text-ink">Почему это важно</dt>
            <dd>{finding.reason}</dd>
          </div>
          <div>
            <dt className="font-semibold text-ink">Обоснование приоритета</dt>
            <dd>{finding.priority.rationale}</dd>
          </div>
          <div className="flex gap-1">
            <dt className="font-semibold text-ink">Тип:</dt>
            <dd>{FINDING_KIND_TEXT[finding.kind]}</dd>
          </div>
        </dl>
      </details>
    </article>
  );
}
