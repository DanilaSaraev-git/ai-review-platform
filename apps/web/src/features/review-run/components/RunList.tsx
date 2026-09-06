import { useInfiniteQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { listReviewRuns, useGetDocument } from '@/api/generated/endpoints';
import type { ReviewRun } from '@/api/generated/model';
import { Button, Callout, Spinner, StatusBadge } from '@/components/ui';
import { Icon } from '@/components/ui/Icon';
import { RUN_STATE_TEXT } from '@/lib/error-messages';
import { formatDateTime, formatMediaType } from '@/lib/format';

/**
 * Список запусков рабочего пространства в обратном хронологическом порядке
 * (FR-016, US1-8): аналитик уходит со страницы во время работы и возвращается
 * к запуску позже.
 */
const TONE: Record<ReviewRun['state'], 'progress' | 'ok' | 'danger' | 'neutral'> = {
  queued: 'progress',
  preparing: 'progress',
  reviewing: 'progress',
  validating: 'progress',
  completed: 'ok',
  failed: 'danger',
  cancelled: 'neutral',
};

export function RunList({ workspaceId }: { workspaceId: string }) {
  const query = useInfiniteQuery({
    queryKey: ['review-runs', workspaceId],
    queryFn: ({ pageParam }) => listReviewRuns(workspaceId, { cursor: pageParam, limit: 20 }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled: Boolean(workspaceId),
  });

  if (query.isPending) {
    return <Spinner label="Загружаем список проверок…" />;
  }

  if (query.isError) {
    return (
      <Callout tone="danger" title="Не удалось загрузить историю">
        <Button className="mt-2" onClick={() => void query.refetch()}>Повторить</Button>
      </Callout>
    );
  }

  const runs = query.data?.pages.flatMap((page) => page.items) ?? [];

  if (runs.length === 0) {
    return (
      <div className="history-empty">
        <span className="entry-file-icon"><Icon name="history" /></span>
        <h3>Проверок пока нет</h3>
        <Link to="/new" className="text-sm text-accent hover:underline">Создать проверку</Link>
      </div>
    );
  }

  return (
    <div>
      <div className="history-table-wrap">
        <table className="history-table">
          <thead>
            <tr>
              <th scope="col">Техническое задание</th>
              <th scope="col">Состояние</th>
              <th scope="col" className="history-date">Дата проверки</th>
              <th scope="col" className="history-author">Создал</th>
            </tr>
          </thead>
          <tbody>{runs.map((run) => <RunRow key={run.id} run={run} workspaceId={workspaceId} />)}</tbody>
        </table>
      </div>
      {query.hasNextPage ? (
        <Button className="mt-3" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>
          {query.isFetchingNextPage ? 'Загружаем…' : 'Показать ещё'}
        </Button>
      ) : null}
    </div>
  );
}

function RunRow({ run, workspaceId }: { run: ReviewRun; workspaceId: string }) {
  const documentQuery = useGetDocument(workspaceId, run.document_id, {
    query: { staleTime: 5 * 60 * 1000 },
  });
  const document = documentQuery.data;
  const date = formatDateTime(run.created_at);

  return (
    <tr>
      <th scope="row">
        <div className="history-document-cell">
          <span className="entry-file-icon"><Icon name="file-text" /></span>
          <div className="min-w-0">
            <Link to={`/runs/${run.id}`} aria-label={`Проверка от ${date}${document ? ` — ${document.filename}` : ''}`}>
              {document?.filename ?? `Проверка от ${date}`}
            </Link>
            <p className="history-document-meta">
              {document ? formatMediaType(document.media_type) : documentQuery.isError ? 'Название документа недоступно' : 'Загружаем документ…'}
              <span className="history-mobile-date"> · {date}</span>
            </p>
          </div>
        </div>
      </th>
      <td><StatusBadge tone={TONE[run.state]}>{run.state === 'completed' ? 'Готово к разбору' : RUN_STATE_TEXT[run.state].label}</StatusBadge></td>
      <td className="history-date"><time dateTime={run.created_at}>{date}</time></td>
      <td className="history-author">{run.created_by.display_name}</td>
    </tr>
  );
}
