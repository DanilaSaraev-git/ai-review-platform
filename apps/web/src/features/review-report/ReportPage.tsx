import { Link, useParams } from 'react-router';
import { useGetDocument } from '@/api/generated/endpoints';
import { Callout, Spinner } from '@/components/ui';
import { DocumentViewer } from '@/components/document-viewer';
import { NotFoundPage } from '@/app/NotFoundPage';
import { DecisionProgress } from '@/features/finding-decision/components/DecisionProgress';
import { useBootstrap } from '@/features/new-review/api/use-bootstrap';
import { useFindingStates } from './api/use-finding-states';
import { useReviewReport } from './api/use-review-report';
import { CoveragePanel } from './components/CoveragePanel';
import { FindingList } from './components/FindingList';
import { ProvenancePanel } from './components/ProvenancePanel';
import { ReportSummary } from './components/ReportSummary';
import { ReviewWorkspace } from './components/ReviewWorkspace';
import { SourceList } from './components/SourceList';

/** Неизменяемый отчёт и разбор замечаний (US2). */
export function ReportPage() {
  const { runId = '' } = useParams();
  const { workspaceId } = useBootstrap();
  const { report, isLoading, isUnavailable, isNotFound } = useReviewReport(workspaceId, runId);
  const { byFindingId, reviewedCount } = useFindingStates(workspaceId, runId);
  const primarySource = report?.provenance.sources.find((source) => source.role === 'document');
  const documentQuery = useGetDocument(workspaceId, primarySource?.document_id ?? '', {
    query: { enabled: Boolean(workspaceId && primarySource?.document_id) },
  });

  if (isNotFound) {
    return <NotFoundPage detail="Такой проверки нет. Возможно, ссылка устарела или идентификатор указан неверно." />;
  }

  // Незавершённый или неуспешный запуск не показывает пустой отчёт (FR-018, US2-7).
  if (isUnavailable) {
    return (
      <main className="mx-auto flex w-full max-w-4xl flex-col gap-4 px-4 py-6 sm:px-6">
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
      <main className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6">
        <Spinner label="Загружаем отчёт…" />
      </main>
    );
  }

  return (
    <ReviewWorkspace
      toolbar={
        <>
          <nav aria-label="Навигация">
            <Link className="text-xs font-medium text-ink-muted hover:text-accent" to={`/runs/${runId}`}>← Проверка</Link>
          </nav>
          <div className="min-w-0">
            <h1 className="truncate text-[15px] font-semibold text-ink">Отчёт проверки</h1>
            <p className="truncate text-xs text-ink-subtle">{primarySource?.filename ?? 'Основной документ'}</p>
          </div>
          <div className="ml-auto">
            <DecisionProgress reviewed={reviewedCount} total={report.findings.length} />
          </div>
        </>
      }
      document={<DocumentViewer workspaceId={workspaceId} document={documentQuery.data} finding={undefined} />}
      panel={
        <>
          <ReportSummary report={report} reviewedCount={reviewedCount} />
          <section aria-labelledby="findings-title" className="px-4 py-4">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h2 id="findings-title" className="text-[15px] font-semibold text-ink">Замечания</h2>
              <span className="text-xs font-medium text-ink-subtle">{report.findings.length}</span>
            </div>
            <FindingList findings={report.findings} states={byFindingId} runId={runId} />
          </section>
          <CoveragePanel coverage={report.coverage} />
          <SourceList sources={report.provenance.sources} />
          <ProvenancePanel model={report.provenance.model} />
        </>
      }
    />
  );
}

export default ReportPage;
