import { Link } from 'react-router';
import { Button, Callout } from '@/components/ui';
import { Icon } from '@/components/ui/Icon';
import '@/styles/review-entry.css';
import { useBootstrap } from '@/features/new-review/api/use-bootstrap';
import { WorkspaceSummary } from '@/features/new-review/components/WorkspaceSummary';
import { RunList } from './components/RunList';

/** Точка входа: рабочее пространство, лимиты и список запусков (US1). */
export function HomePage() {
  const { workspace, actor, limits, workspaceId, isLoading, error, retry } = useBootstrap();

  if (error && !workspaceId) {
    return (
      <main className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
        <Callout tone="danger" title="Не удалось загрузить рабочее пространство">
          <Button className="mt-2" onClick={() => void retry()}>Повторить</Button>
        </Callout>
      </main>
    );
  }

  return (
    <main className="history-page">
      <header className="history-page-header">
        <div>
          <h1>История проверок</h1>
          <WorkspaceSummary workspace={workspace} actor={actor} limits={limits} isLoading={isLoading} />
        </div>
        <Link
          to="/new"
          className="history-new-link"
        >
          <Icon name="plus" />
          Новая проверка
        </Link>
      </header>

      <section aria-labelledby="runs-title" className="flex flex-col gap-3">
        <h2 id="runs-title" className="sr-only">
          Последние проверки
        </h2>
        {workspaceId ? <RunList workspaceId={workspaceId} /> : null}
      </section>
    </main>
  );
}

export default HomePage;
