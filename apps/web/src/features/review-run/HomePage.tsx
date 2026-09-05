import { Link } from 'react-router';
import { Button, Callout } from '@/components/ui';
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
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-[-0.025em] text-ink">Проверки</h1>
          <WorkspaceSummary workspace={workspace} actor={actor} limits={limits} isLoading={isLoading} />
        </div>
        <Link
          to="/new"
          className="inline-flex min-h-9 items-center rounded-[5px] border border-accent bg-accent px-3 py-1.5 text-[13px] font-semibold text-white shadow-sm transition-[background-color,border-color,transform] duration-100 hover:border-accent-strong hover:bg-accent-strong active:scale-[0.96]"
        >
          Новая проверка
        </Link>
      </div>

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
