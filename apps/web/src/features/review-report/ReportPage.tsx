import { Link, useParams } from 'react-router';
import { Button, Callout, Spinner } from '@/components/ui';
import { NotFoundPage } from '@/app/NotFoundPage';
import { useFindingStates } from './api/use-finding-states';
import { useReviewReport } from './api/use-review-report';
import { CoveragePanel } from './components/CoveragePanel';
import { FindingList } from './components/FindingList';
import { ProvenancePanel } from './components/ProvenancePanel';
import { ReviewNextStep } from '@/features/document-cycle/ReviewNextStep';
import { ReviewCyclePanel } from '@/features/document-cycle/ReviewCyclePage';
import { ReportSummary } from './components/ReportSummary';
import { SourceList } from './components/SourceList';
import { useWorkspaceRun } from './components/ReviewWorkspaceLayout';

/** Immutable report in the right panel; the source stays mounted in the parent route. */
export function ReportPage() {
  const { runId = '' } = useParams();
  const { workspaceId, historical } = useWorkspaceRun();
  const { report, isLoading, isUnavailable, isNotFound, error, retry } = useReviewReport(workspaceId, runId);
  const { byFindingId, reviewedCount, error: statesError, retry: retryStates } = useFindingStates(workspaceId, runId);

  if (isNotFound) return <NotFoundPage detail="Такой проверки нет. Возможно, ссылка устарела или идентификатор указан неверно." />;
  if (isUnavailable) return <div className="p-5">
    <Callout tone="warn" title="Отчёта пока нет">Проверка не завершилась успешно, поэтому отчёт не опубликован.</Callout>
    <Link className="mt-4 inline-block text-sm text-accent" to={`/runs/${runId}`}>К состоянию проверки</Link>
  </div>;
  if (error && !report) return <div className="p-5"><Callout tone="danger" title="Не удалось загрузить отчёт">
    <Button className="mt-2" onClick={() => void retry()}>Повторить</Button>
  </Callout></div>;
  if (isLoading || !report) return <div className="p-5"><Spinner label="Загружаем отчёт…" /></div>;

  return (
    <div className="numbat-panel-scroll">
      <ReviewNextStep />
      <div className="numbat-panel-heading">
        <h2 id="findings-title">Замечания <span className="ml-1 text-sm text-ink-subtle">{report.findings.length}</span></h2>
        <Link to={`/runs/${runId}`}>О проверке</Link>
      </div>

      {statesError ? <div className="px-5 pb-4"><Callout tone="warn" title="Статусы замечаний не обновились">
        <Button className="mt-2" onClick={() => void retryStates()}>Повторить</Button>
      </Callout></div> : null}
      <ReportSummary report={report} reviewedCount={reviewedCount} />
      <section aria-labelledby="findings-title">
        <FindingList findings={report.findings} states={byFindingId} runId={runId} />
      </section>
      <div id="review-fixes"><ReviewCyclePanel workspaceId={workspaceId} runId={runId} embedded readOnly={historical} /></div>
      <CoveragePanel coverage={report.coverage} />
      <SourceList sources={report.provenance.sources} />
      <ProvenancePanel model={report.provenance.model} />
    </div>
  );
}

export default ReportPage;
