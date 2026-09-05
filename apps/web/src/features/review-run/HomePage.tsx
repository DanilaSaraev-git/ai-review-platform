import { Link } from 'react-router';
import { useBootstrap } from '@/features/new-review/api/use-bootstrap';
import { WorkspaceSummary } from '@/features/new-review/components/WorkspaceSummary';
import { RunList } from './components/RunList';

/** Точка входа: рабочее пространство, лимиты и список запусков (US1). */
export function HomePage() {
  const { workspace, actor, limits, workspaceId, isLoading } = useBootstrap();

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-5 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-ink">Проверки ТЗ</h1>
        <Link
          to="/new"
          className="inline-flex items-center rounded border border-accent bg-accent px-3 py-1.5 text-sm font-medium text-white"
        >
          Новая проверка
        </Link>
      </div>

      <WorkspaceSummary workspace={workspace} actor={actor} limits={limits} isLoading={isLoading} />

      <section aria-labelledby="runs-title" className="flex flex-col gap-3">
        <h2 id="runs-title" className="text-sm font-semibold text-ink">
          Последние проверки
        </h2>
        {workspaceId ? <RunList workspaceId={workspaceId} /> : null}
      </section>
    </main>
  );
}

export default HomePage;
