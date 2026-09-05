import { Link } from 'react-router';
import { useListReviewRuns } from '@/api/generated/endpoints';
import type { ReviewRun } from '@/api/generated/model';
import { Callout, Spinner, StatusBadge } from '@/components/ui';
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
  const query = useListReviewRuns(workspaceId, undefined, {
    query: { enabled: Boolean(workspaceId) },
  });

  if (query.isPending) {
    return <Spinner label="Загружаем список проверок…" />;
  }

  const runs = query.data?.items ?? [];

  if (runs.length === 0) {
    return (
      <Callout title="Проверок пока нет">
        Загрузите готовое ТЗ и запустите первую проверку, чтобы увидеть замечания до передачи в разработку.
      </Callout>
    );
  }

  return (
    <ul className="flex flex-col gap-2">
      {runs.map((run) => (
        <li key={run.id} className="rounded border border-line bg-surface p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Link className="text-sm font-medium text-accent underline" to={`/runs/${run.id}`}>
              Проверка от {formatDateTime(run.created_at)}
            </Link>
            <StatusBadge tone={TONE[run.state]}>{RUN_STATE_TEXT[run.state].label}</StatusBadge>
          </div>
          <p className="mt-1 text-xs text-ink-muted">
            {run.progress?.message || RUN_STATE_TEXT[run.state].hint} · создал {run.created_by.display_name}
          </p>
        </li>
      ))}
    </ul>
  );
}
