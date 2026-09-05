import { useInfiniteQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { listReviewRuns } from '@/api/generated/endpoints';
import type { ReviewRun } from '@/api/generated/model';
import { Button, Callout, Spinner, StatusBadge } from '@/components/ui';
import { RUN_STATE_TEXT } from '@/lib/error-messages';
import { formatDateTime } from '@/lib/format';

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
      <Callout title="Проверок пока нет">
        Загрузите готовое ТЗ и запустите первую проверку, чтобы увидеть замечания до передачи в разработку.
      </Callout>
    );
  }

  return (
    <div>
      <ul className="overflow-hidden rounded-[6px] border border-line bg-surface">
        {runs.map((run) => (
          <li key={run.id} className="border-b border-line p-3.5 last:border-b-0 hover:bg-surface-muted">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Link className="text-[13px] font-semibold text-ink hover:text-accent" to={`/runs/${run.id}`}>
              Проверка от {formatDateTime(run.created_at)}
            </Link>
              <StatusBadge tone={TONE[run.state]}>{RUN_STATE_TEXT[run.state].label}</StatusBadge>
            </div>
            <p className="mt-1 text-xs leading-5 text-ink-muted">{run.created_by.display_name}</p>
          </li>
        ))}
      </ul>
      {query.hasNextPage ? (
        <Button className="mt-3" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>
          {query.isFetchingNextPage ? 'Загружаем…' : 'Показать ещё'}
        </Button>
      ) : null}
    </div>
  );
}
