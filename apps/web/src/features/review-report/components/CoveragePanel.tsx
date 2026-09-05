import type { Coverage } from '@/api/generated/model';
import { Callout, StatusBadge } from '@/components/ui';
import { COVERAGE_GAP_TEXT } from '@/lib/error-messages';

/**
 * Охват проверки (FR-022).
 *
 * Частичный результат показывается заметным признаком, а не мелкой пометкой,
 * и каждый пропуск сопровождается причиной: аналитик должен понимать, что
 * именно осталось непроверенным.
 */
export function CoveragePanel({ coverage }: { coverage: Coverage }) {
  const isPartial = coverage.status === 'partial';

  return (
    <section aria-labelledby="coverage-title" className="rounded border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="coverage-title" className="text-sm font-semibold text-ink">
          Охват проверки
        </h2>
        <StatusBadge tone={isPartial ? 'warn' : 'ok'}>{isPartial ? 'Неполный охват' : 'Полный охват'}</StatusBadge>
      </div>

      <p className="mt-2 text-xs text-ink-muted">
        Проверено {coverage.reviewed_fragment_ids.length} из {coverage.target_fragment_ids.length} фрагментов.
      </p>

      {isPartial ? (
        <div className="mt-3">
          <Callout tone="warn" title="Результат неполный">
            Часть материалов не была учтена. Выводы могли не принять во внимание перечисленное ниже.
          </Callout>
        </div>
      ) : null}

      {coverage.gaps.length > 0 ? (
        <ul className="mt-3 flex flex-col gap-2">
          {coverage.gaps.map((gap, index) => (
            <li key={`${gap.source_id}-${gap.fragment_id ?? index}`} className="rounded border border-line p-2">
              <p className="text-xs font-medium text-ink">
                {COVERAGE_GAP_TEXT[gap.code]} · источник {gap.source_id}
                {gap.fragment_id ? ` · фрагмент ${gap.fragment_id}` : ''}
              </p>
              <p className="mt-1 text-xs text-ink-muted">{gap.reason}</p>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
