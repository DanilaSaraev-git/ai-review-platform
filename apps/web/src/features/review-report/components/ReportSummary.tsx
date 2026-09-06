import type { ReviewReport } from '@/api/generated/model';
import { StatusBadge } from '@/components/ui';
import { formatDateTime } from '@/lib/format';
import { isDemoMode } from '@/app/demo-mode';

/** Сервер прямо маркирует офлайн/примерное исполнение в provenance. */
export function isTestReport(report: ReviewReport): boolean {
  const execution = `${report.provenance.model.provider} ${report.provenance.model.model}`;
  return (
    /deterministic|fixture|example/iu.test(execution) ||
    report.coverage.gaps.some((gap) => gap.reason === 'semantic_analysis_not_performed') ||
    report.limitations.some((limitation) => /синтетическ/iu.test(limitation))
  );
}

/**
 * Сводка и ограничения отчёта (FR-019).
 * Главный вывод и ход разбора видны сразу; длинные ограничения раскрываются
 * рядом с результатом по запросу.
 */
export function ReportSummary({ report }: { report: ReviewReport; reviewedCount: number }) {
  return (
    <section aria-labelledby="report-summary-title" className="border-b border-line px-4 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="report-summary-title" className="text-[15px] font-semibold text-ink">
          Результат проверки
        </h2>
        {isDemoMode || isTestReport(report) ? <StatusBadge tone="warn">Тестовый результат</StatusBadge> : null}
      </div>
      <p className="mt-1.5 text-[13px] leading-5 text-ink-muted">{report.summary}</p>
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
