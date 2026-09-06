import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ReviewHistory } from '@/features/document-cycle/ReviewHistory';
import { NewVersionDialog } from '@/features/document-cycle/NewVersionDialog';
import { DownloadPdfButton } from './DownloadPdfButton';
import '@/styles/unified-review.css';
import { Link, Outlet, useLocation, useOutletContext, useParams } from 'react-router';
import { listDocumentFamilyRuns, useGetDocument, useGetDocumentVersionFamily } from '@/api/generated/endpoints';
import { formatDateTime } from '@/lib/format';
import { isDemoMode } from '@/app/demo-mode';
import { isNotFound } from '@/api/errors';
import { NotFoundPage } from '@/app/NotFoundPage';
import { DocumentViewer } from '@/components/document-viewer';
import { Button, Callout, Spinner } from '@/components/ui';
import { useBootstrap } from '@/features/new-review/api/use-bootstrap';
import { useReviewRun, type ReviewRunState } from '@/features/review-run/api/use-review-run';
import { useReviewReport } from '../api/use-review-report';
import { ReviewWorkspace } from './ReviewWorkspace';

interface WorkspaceContext {
  workspaceId: string;
  runState: ReviewRunState;
  openVersion: () => void;
  historical: boolean;
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
  const [historyOpen, setHistoryOpen] = useState(false);
  const [versionOpen, setVersionOpen] = useState(false);
  const documentId = runState.run?.document_id ?? '';
  const documentQuery = useGetDocument(workspaceId, documentId, {
    query: { enabled: Boolean(workspaceId && documentId), staleTime: Infinity },
  });
  const membership = useGetDocumentVersionFamily(workspaceId, documentId, { query: { enabled: Boolean(workspaceId && documentId && !isDemoMode), staleTime: Infinity } });
  const familyId = membership.data?.family_id ?? '';
  const familyRuns = useQuery({ queryKey: ['latest-family-run', workspaceId, familyId], queryFn: () => listDocumentFamilyRuns(workspaceId, familyId, { limit: 1 }), enabled: Boolean(familyId) });
  const latestRun = familyRuns.data?.items[0];
  const historical = !isDemoMode && (!latestRun || latestRun.id !== runId);
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
    <>
    <ReviewWorkspace
      toolbar={<>
        <nav aria-label="Навигация" className="numbat-workspace-breadcrumb">
          <Link to="/">Проверки</Link>
          <span aria-hidden="true">/</span>
        </nav>
        <h1 className="numbat-workspace-filename">{documentQuery.data?.filename ?? 'Проверка документа'}</h1>
        {membership.data ? <span className="text-xs text-ink-muted">Версия {membership.data.version_number}</span> : null}
        {runState.run ? <><time className="text-xs text-ink-muted" dateTime={runState.run.created_at}>{formatDateTime(runState.run.created_at)}</time></> : null}
        {!isDemoMode && familyId ? <div className="ml-auto flex gap-2"><Button onClick={() => setHistoryOpen(true)}>История</Button>{report ? <DownloadPdfButton workspaceId={workspaceId} runId={runId} /> : null}<Button onClick={() => setVersionOpen(true)}>Загрузить новую версию</Button></div> : null}
        {historical && latestRun ? <div className="review-archive">Вы смотрите предыдущий результат. <Link to={`/runs/${latestRun.id}${latestRun.report_available ? '/report' : ''}`}>К текущему результату</Link></div> : null}
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
      panel={<Outlet context={{ workspaceId, runState, openVersion: () => setVersionOpen(true), historical } satisfies WorkspaceContext} />}
    />
    {familyId ? <ReviewHistory workspaceId={workspaceId} familyId={familyId} runId={runId} open={historyOpen} onClose={() => setHistoryOpen(false)} /> : null}
    {versionOpen && familyId && (latestRun ?? runState.run) ? <NewVersionDialog workspaceId={workspaceId} familyId={familyId} prior={(latestRun ?? runState.run)!} onClose={() => { setVersionOpen(false); void familyRuns.refetch(); }} /> : null}
    </>
  );
}
