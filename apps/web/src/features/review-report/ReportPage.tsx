import { Link, useParams } from 'react-router';
import { Callout, Spinner } from '@/components/ui';
import { NotFoundPage } from '@/app/NotFoundPage';
import { useBootstrap } from '@/features/new-review/api/use-bootstrap';
import { useFindingStates } from './api/use-finding-states';
import { useReviewReport } from './api/use-review-report';
import { CoveragePanel } from './components/CoveragePanel';
import { FindingList } from './components/FindingList';
import { ProvenancePanel } from './components/ProvenancePanel';
import { ReportSummary } from './components/ReportSummary';
import { SourceList } from './components/SourceList';

/** Неизменяемый отчёт и разбор замечаний (US2). */
export function ReportPage() {
  const { runId = '' } = useParams();
  const { workspaceId } = useBootstrap();
  const { report, isLoading, isUnavailable, isNotFound } = useReviewReport(workspaceId, runId);
  const { byFindingId, reviewedCount } = useFindingStates(workspaceId, runId);

  if (isNotFound) {
    return <NotFoundPage detail="Такой проверки нет. Возможно, ссылка устарела или идентификатор указан неверно." />;
  }

  // Незавершённый или неуспешный запуск не показывает пустой отчёт (FR-018, US2-7).
  if (isUnavailable) {
    return (
      <main className="mx-auto flex max-w-3xl flex-col gap-4 p-6">
        <Callout tone="warn" title="Отчёта пока нет">
          Проверка не завершилась успешно, поэтому отчёт не опубликован. Откройте состояние проверки, чтобы увидеть
          причину.
        </Callout>
        <Link className="text-sm text-accent underline" to={`/runs/${runId}`}>
          К состоянию проверки
        </Link>
      </main>
    );
  }

  if (isLoading || !report) {
    return (
      <main className="mx-auto max-w-3xl p-6">
        <Spinner label="Загружаем отчёт…" />
      </main>
    );
  }

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-4 p-6">
      <nav aria-label="Навигация">
        <Link className="text-sm text-accent underline" to={`/runs/${runId}`}>
          К состоянию проверки
        </Link>
      </nav>

      <h1 className="text-xl font-semibold text-ink">Отчёт проверки</h1>

      <ReportSummary report={report} reviewedCount={reviewedCount} />

      <section aria-labelledby="findings-title" className="flex flex-col gap-3">
        <h2 id="findings-title" className="text-sm font-semibold text-ink">
          Замечания
        </h2>
        <FindingList findings={report.findings} states={byFindingId} runId={runId} />
      </section>

      <CoveragePanel coverage={report.coverage} />
      <SourceList sources={report.provenance.sources} />
      <ProvenancePanel model={report.provenance.model} />
    </main>
  );
}

export default ReportPage;
