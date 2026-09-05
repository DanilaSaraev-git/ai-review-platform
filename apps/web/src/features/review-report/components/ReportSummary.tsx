import type { ReviewReport } from '@/api/generated/model';
import { formatDateTime } from '@/lib/format';

/**
 * Сводка и ограничения отчёта (FR-019).
 * Главный вывод и ход разбора видны сразу; длинные ограничения раскрываются
 * рядом с результатом по запросу.
 */
export function ReportSummary({ report }: { report: ReviewReport; reviewedCount: number }) {
  return (
    <section aria-labelledby="report-summary-title" className="border-b border-line px-4 py-4">
      <h2 id="report-summary-title" className="text-[15px] font-semibold text-ink">
        Результат проверки
      </h2>
      <p className="mt-1.5 text-[13px] leading-5 text-ink-muted">{report.summary}</p>
      <p className="mt-2 text-xs font-medium text-ink-subtle">{report.findings.length} замечаний</p>

      {report.limitations.length > 0 ? (
        <details className="mt-3 text-xs">
          <summary className="cursor-pointer font-semibold text-ink-muted hover:text-ink">Ограничения результата</summary>
          <ul className="mt-1 list-disc pl-5 text-xs text-ink-muted">
            {report.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </details>
      ) : null}

      <details className="mt-2 text-xs text-ink-subtle">
        <summary className="cursor-pointer font-medium hover:text-ink">Сведения об отчёте</summary>
        <p className="mt-1">Сформирован {formatDateTime(report.created_at)}. Отчёт неизменяем; решения хранятся отдельно.</p>
      </details>
    </section>
  );
}
