import { useEffect, useState } from 'react';
import { Button, Callout, Spinner } from '@/components/ui';
import { useWorkspaceRun } from '@/features/review-report/components/ReviewWorkspaceLayout';
import { RunStatePanel } from './components/RunStatePanel';

/** Run state occupies the right panel while the full document remains readable. */
export function RunPage() {
  const { runState: { run, progress, isLoading, error, retry } } = useWorkspaceRun();
  const [isOffline, setIsOffline] = useState(!navigator.onLine);
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

  if (error && !run) return <div className="p-5"><Callout tone="danger" title="Не удалось загрузить состояние проверки">
    <Button className="mt-2" onClick={() => void retry()}>Повторить</Button>
  </Callout></div>;
  if (isLoading || !run) return <div className="p-5"><Spinner label="Загружаем состояние проверки…" /></div>;

  const stages = ['Подготовка', 'Анализ документа', 'Проверка результата'];
  const stage = ['queued', 'preparing'].includes(run.state) ? 0 : run.state === 'reviewing' ? 1 : 2;
  return <div className="numbat-panel-scroll">
    <div className="numbat-panel-heading"><h2>Проверка документа</h2></div>
    {!['failed', 'cancelled'].includes(run.state) ? <ol className="mx-5 mb-5 flex flex-col gap-4 border-b border-line pb-5 text-[13px]" aria-label="Этапы проверки">
      {stages.map((label, index) => <li key={label} className="flex items-center gap-3" aria-current={index === stage && run.state !== 'completed' ? 'step' : undefined}>
        <span className={`flex h-6 w-6 items-center justify-center rounded-full border text-[11px] ${index < stage || run.state === 'completed' ? 'border-line bg-surface-muted text-ink-muted' : index === stage ? 'border-accent bg-accent-tint text-accent' : 'border-line text-ink-subtle'}`} aria-hidden="true">{index < stage || run.state === 'completed' ? '✓' : index + 1}</span>
        <span className={index === stage ? 'font-medium text-ink' : 'text-ink-muted'}>{label}</span>
      </li>)}
    </ol> : null}
    <div className="px-5 pb-5"><RunStatePanel run={run} progress={progress} isOffline={isOffline} /></div>
  </div>;
}

export default RunPage;
