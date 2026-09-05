import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router';
import { isNotFound } from '@/api/errors';
import { Spinner } from '@/components/ui';
import { NotFoundPage } from '@/app/NotFoundPage';
import { useBootstrap } from '@/features/new-review/api/use-bootstrap';
import { useReviewRun } from './api/use-review-run';
import { RunStatePanel } from './components/RunStatePanel';

/** Наблюдение за одним запуском (US1). */
export function RunPage() {
  const { runId = '' } = useParams();
  const { workspaceId } = useBootstrap();
  const { run, progress, isLoading, error } = useReviewRun(workspaceId, runId);
  const [isOffline, setIsOffline] = useState(!navigator.onLine);

  // Разрыв связи объясняется явно, а опрос возобновляется автоматически:
  // контекст экрана при этом не теряется (краевой случай спецификации).
  useEffect(() => {
    const online = () => setIsOffline(false);
    const offline = () => setIsOffline(true);
    globalThis.addEventListener('online', online);
    globalThis.addEventListener('offline', offline);
    return () => {
      globalThis.removeEventListener('online', online);
      globalThis.removeEventListener('offline', offline);
    };
  }, []);

  if (isNotFound(error)) {
    return <NotFoundPage detail="Такой проверки нет. Возможно, ссылка устарела или идентификатор указан неверно." />;
  }

  if (isLoading || !run) {
    return (
      <main className="mx-auto max-w-3xl p-6">
        <Spinner label="Загружаем состояние проверки…" />
      </main>
    );
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-4 p-6">
      <nav aria-label="Навигация">
        <Link className="text-sm text-accent underline" to="/">
          К списку проверок
        </Link>
      </nav>
      <h1 className="text-xl font-semibold text-ink">Проверка документа</h1>
      <RunStatePanel run={run} progress={progress} isOffline={isOffline} />
    </main>
  );
}

export default RunPage;
