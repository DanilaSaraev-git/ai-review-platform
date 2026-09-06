import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { listDocumentFamilies, listDocumentFamilyRuns, useGetDocumentVersionFamily, useGetReviewCycle } from '@/api/generated/endpoints';
import type { DocumentFamily } from '@/api/generated/model';
import { Button, Callout, Spinner } from '@/components/ui';
import { useBootstrap } from '@/features/new-review/api/use-bootstrap';
import { useReviewReport } from '@/features/review-report/api/use-review-report';
import { useFindingStates } from '@/features/review-report/api/use-finding-states';
import { formatDateTime } from '@/lib/format';
import { RUN_STATE_TEXT } from '@/lib/error-messages';
import { nextStep } from './ReviewNextStep';
import '@/styles/review-entry.css';

export function DocumentsPage() {
  const { workspaceId, error, retry } = useBootstrap();
  const query = useInfiniteQuery({
    queryKey: ['document-families', workspaceId],
    queryFn: ({ pageParam }) => listDocumentFamilies(workspaceId, { cursor: pageParam, limit: 20 }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: page => page.next_cursor ?? undefined,
    enabled: Boolean(workspaceId),
  });
  const families = query.data?.pages.flatMap(page => page.items) ?? [];
  return <main className="history-page">
    <header className="history-page-header"><h1>Проверки</h1><Link to="/new" className="history-new-link">Новая проверка</Link></header>
    {error || query.isError ? <Callout tone="danger" title="Не удалось загрузить проверки"><Button onClick={() => void (error ? retry() : query.refetch())}>Повторить</Button></Callout>
      : query.isPending ? <Spinner label="Загружаем проверки…" /> : <div className="history-table-wrap"><table className="history-table"><thead><tr><th>Проверка</th><th>Версия</th><th>Следующий шаг</th><th>Обновлено</th></tr></thead><tbody>{families.map(f => <ReviewRow key={f.id} workspaceId={workspaceId} family={f} />)}</tbody></table>{families.length === 0 ? <p>Проверок пока нет.</p> : null}</div>}
    {query.hasNextPage ? <Button className="mt-3" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>Показать ещё</Button> : null}
  </main>;
}

function ReviewRow({ workspaceId, family }: { workspaceId: string; family: DocumentFamily }) {
  const runs = useQuery({ queryKey: ['latest-family-run', workspaceId, family.id], queryFn: () => listDocumentFamilyRuns(workspaceId, family.id, { limit: 1 }) });
  const run = runs.data?.items[0];
  const membership = useGetDocumentVersionFamily(workspaceId, run?.document_id ?? '', { query: { enabled: Boolean(run), staleTime: Infinity } });
  const { report } = useReviewReport(workspaceId, run?.id ?? '', Boolean(run?.report_available));
  const states = useFindingStates(workspaceId, run?.id ?? '', Boolean(run?.report_available));
  const cycle = useGetReviewCycle(workspaceId, run?.id ?? '', { query: { enabled: Boolean(run?.report_available) } });
  if (runs.isSuccess && !run) return null;
  const updatedAt = [run?.finished_at, run?.created_at, family.created_at, cycle.data?.completion?.completed_at, ...states.items.map(s => s.decision.decided_at)].filter((value): value is string => Boolean(value)).sort().at(-1);
  const title = report && cycle.data && !states.isLoading && !states.error ? nextStep(report, states.byFindingId, cycle.data).title : run?.report_available ? (states.error || cycle.isError ? 'Статус разбора недоступен' : 'Загружаем статус разбора…') : run ? RUN_STATE_TEXT[run.state].label : 'Загружаем состояние…';
  return <tr><th scope="row"><Link to={run ? `/runs/${run.id}${run.report_available ? '/report' : ''}` : `/documents/${family.id}`}>{family.name}</Link></th><td>{membership.data?.version_number ?? family.latest_version_number}</td><td>{runs.isError ? 'Состояние недоступно' : title}</td><td>{formatDateTime(updatedAt)}</td></tr>;
}
