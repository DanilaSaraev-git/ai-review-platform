import { Link, Outlet, useLocation, useOutletContext, useParams } from 'react-router';
import { useGetDocument } from '@/api/generated/endpoints';
import { isNotFound } from '@/api/errors';
import { NotFoundPage } from '@/app/NotFoundPage';
import { DocumentViewer } from '@/components/document-viewer';
import { Button, Callout, Spinner } from '@/components/ui';
import { DecisionProgress } from '@/features/finding-decision/components/DecisionProgress';
import { useBootstrap } from '@/features/new-review/api/use-bootstrap';
import { useReviewRun, type ReviewRunState } from '@/features/review-run/api/use-review-run';
import { useFindingStates } from '../api/use-finding-states';
import { useReviewReport } from '../api/use-review-report';
import { ReviewWorkspace } from './ReviewWorkspace';

interface WorkspaceContext {
  workspaceId: string;
  runState: ReviewRunState;
}

export function useWorkspaceRun() {
  return useOutletContext<WorkspaceContext>();
}

/** The primary document belongs to the run, so nested route changes never replace its viewer. */
export function ReviewWorkspaceLayout() {
  const { runId = '', findingId } = useParams();
  const location = useLocation();
  const isReport = location.pathname.includes('/report');
  const { workspaceId, error: bootstrapError, retry: retryBootstrap } = useBootstrap();
  const runState = useReviewRun(workspaceId, runId);
  const { report } = useReviewReport(workspaceId, runId, isReport);
  const { reviewedCount } = useFindingStates(workspaceId, runId, isReport);
  const documentId = runState.run?.document_id ?? '';
  const documentQuery = useGetDocument(workspaceId, documentId, {
    query: { enabled: Boolean(workspaceId && documentId), staleTime: Infinity },
  });
  const finding = report?.findings.find((item) => item.id === findingId);

  if (bootstrapError && !workspaceId) {
    return <div className="p-6"><Callout tone="danger" title="Не удалось загрузить рабочее пространство">
      <Button className="mt-2" onClick={() => void retryBootstrap()}>Повторить</Button>
    </Callout></div>;
  }
  if (isNotFound(runState.error)) {
    return <NotFoundPage detail="Такой проверки нет. Возможно, ссылка устарела или идентификатор указан неверно." />;
  }

  return (
    <ReviewWorkspace
      toolbar={<>
        <nav aria-label="Навигация" className="numbat-workspace-breadcrumb">
          <Link to="/">Проверки</Link>
          <span aria-hidden="true">/</span>
        </nav>
        <h1 className="numbat-workspace-filename">{documentQuery.data?.filename ?? 'Проверка документа'}</h1>
        {isReport && report ? <div className="numbat-workspace-progress">
          <DecisionProgress reviewed={reviewedCount} total={report.findings.length} />
        </div> : null}
      </>}
      document={documentQuery.isError ? (
        <Callout tone="danger" title="Не удалось загрузить сведения о документе">
          <Button className="mt-2" onClick={() => void documentQuery.refetch()}>Повторить</Button>
        </Callout>
      ) : runState.error && !runState.run ? (
        <Callout tone="danger" title="Не удалось загрузить состояние проверки">
          <Button className="mt-2" onClick={() => void runState.retry()}>Повторить</Button>
        </Callout>
      ) : documentQuery.data ? (
        <DocumentViewer key={`${workspaceId}:${documentId}`} workspaceId={workspaceId} document={documentQuery.data} finding={finding} />
      ) : <Spinner label="Загружаем документ…" />}
      panel={<Outlet context={{ workspaceId, runState } satisfies WorkspaceContext} />}
    />
  );
}
