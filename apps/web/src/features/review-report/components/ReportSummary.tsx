import type { ReviewReport } from '@/api/generated/model';
import { formatDateTime } from '@/lib/format';

/**
 * Сводка и ограничения отчёта (FR-019).
 * Ограничения показываются рядом с результатом, а не прячутся за раскрытием:
 * это часть честности результата.
 */
export function ReportSummary({ report, reviewedCount }: { report: ReviewReport; reviewedCount: number }) {
  return (
    <section aria-labelledby="report-summary-title" className="rounded border border-line bg-surface p-4">
      <h2 id="report-summary-title" className="text-sm font-semibold text-ink">
        Результат проверки
      </h2>
      <p className="mt-2 text-sm text-ink">{report.summary}</p>
      <p className="mt-2 text-xs text-ink-muted">
        Отчёт сформирован {formatDateTime(report.created_at)} · замечаний: {report.findings.length} · разобрано{' '}
        {reviewedCount} из {report.findings.length}
      </p>

      {report.limitations.length > 0 ? (
        <div className="mt-3">
          <h3 className="text-xs font-semibold text-ink">Ограничения результата</h3>
          <ul className="mt-1 list-disc pl-5 text-xs text-ink-muted">
            {report.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <p className="mt-3 text-xs text-ink-muted">
        Замечания — кандидаты на уточнение. Решение по каждому принимает аналитик; отчёт от решений не меняется.
      </p>
    </section>
  );
}
