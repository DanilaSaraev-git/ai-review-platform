import type { SourceProvenance } from '@/api/generated/model';
import { StatusBadge } from '@/components/ui';
import { SOURCE_ROLE_TEXT, SOURCE_STATUS_TEXT } from '@/lib/error-messages';

/**
 * Перечень источников с ролью и статусом (FR-022, US5-3).
 * Показываются все переданные источники: ни один не исчезает из списка молча,
 * даже если он оказался недоступным.
 */
export function SourceList({ sources }: { sources: readonly SourceProvenance[] }) {
  return (
    <section aria-labelledby="sources-title" className="rounded border border-line bg-surface p-4">
      <h2 id="sources-title" className="text-sm font-semibold text-ink">
        Источники проверки
      </h2>
      <ul className="mt-3 flex flex-col gap-2">
        {sources.map((source) => (
          <li key={source.source_id} className="rounded border border-line p-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm text-ink">{source.filename}</span>
              <StatusBadge
                tone={source.status === 'available' ? 'ok' : source.status === 'partial' ? 'warn' : 'danger'}
              >
                {SOURCE_STATUS_TEXT[source.status]}
              </StatusBadge>
            </div>
            <p className="mt-1 text-xs text-ink-muted">{SOURCE_ROLE_TEXT[source.role]}</p>
            {source.diagnostics.length > 0 ? (
              <ul className="mt-1 list-disc pl-5 text-xs text-ink-muted">
                {source.diagnostics.map((diagnostic) => (
                  <li key={diagnostic.code}>{diagnostic.message}</li>
                ))}
              </ul>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
