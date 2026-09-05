import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router';
import { isNotFound } from '@/api/errors';
import { Button, Callout, Spinner } from '@/components/ui';
import { NotFoundPage } from '@/app/NotFoundPage';
import { useBootstrap } from '@/features/new-review/api/use-bootstrap';
import { useReviewRun } from './api/use-review-run';
import { RunStatePanel } from './components/RunStatePanel';

/** Наблюдение за одним запуском (US1). */
export function RunPage() {
  const { runId = '' } = useParams();
  const { workspaceId, error: bootstrapError, retry: retryBootstrap } = useBootstrap();
  const { run, progress, isLoading, error, retry } = useReviewRun(workspaceId, runId);
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

  if (bootstrapError && !workspaceId) {
    return (
      <main className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
        <Callout tone="danger" title="Не удалось загрузить рабочее пространство">
          <Button className="mt-2" onClick={() => void retryBootstrap()}>Повторить</Button>
        </Callout>
      </main>
    );
  }

  if (isNotFound(error)) {
    return <NotFoundPage detail="Такой проверки нет. Возможно, ссылка устарела или идентификатор указан неверно." />;
  }

  if (error && !run) {
    return (
      <main className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
        <Callout tone="danger" title="Не удалось загрузить состояние проверки">
          <Button className="mt-2" onClick={() => void retry()}>Повторить</Button>
        </Callout>
      </main>
    );
  }

  if (isLoading || !run) {
    return (
      <main className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
        <Spinner label="Загружаем состояние проверки…" />
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-4 px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
      <nav aria-label="Навигация">
        <Link className="text-xs font-medium text-ink-muted hover:text-accent" to="/">
          ← Проверки
        </Link>
      </nav>
      <h1 className="text-2xl font-semibold tracking-[-0.025em] text-ink">Проверка документа</h1>
      <RunStatePanel run={run} progress={progress} isOffline={isOffline} />
    </main>
  );
}

export default RunPage;
