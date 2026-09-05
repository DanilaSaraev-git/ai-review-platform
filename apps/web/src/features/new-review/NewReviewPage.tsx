import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { useListModelProfiles, useListReviewProfiles } from '@/api/generated/endpoints';
import type { Document, ModelProfile, ReviewProfile } from '@/api/generated/model';
import { isProblem } from '@/api/errors';
import { Button, Callout, Spinner } from '@/components/ui';
import { useBootstrap } from './api/use-bootstrap';
import { useCreateReviewRun } from './api/use-create-review-run';
import { ContextDocuments } from './components/ContextDocuments';
import { DocumentUpload } from './components/DocumentUpload';
import { ModelProfileSelect } from './components/ModelProfileSelect';
import { ReviewProfileSelect } from './components/ReviewProfileSelect';
import { runReadiness } from './lib/run-readiness';

/**
 * Подготовка проверки: документ, контекст, профили, запуск (US1, US5).
 * Раскладка веб-интерфейса v1:
 * панель контекста слева, параметры запуска — в карточке справа.
 */
export function NewReviewPage() {
  const navigate = useNavigate();
  const { workspaceId, limits, isLoading } = useBootstrap();
  const [document, setDocument] = useState<Document | undefined>(undefined);
  const [contextDocuments, setContextDocuments] = useState<Document[]>([]);
  const [profile, setProfile] = useState<ReviewProfile | undefined>(undefined);
  const [modelProfile, setModelProfile] = useState<ModelProfile | undefined>(undefined);
  const [isContextOpen, setIsContextOpen] = useState(true);

  const profilesQuery = useListReviewProfiles(workspaceId, { query: { enabled: Boolean(workspaceId) } });
  const modelProfilesQuery = useListModelProfiles(workspaceId, { query: { enabled: Boolean(workspaceId) } });
  const { createRun, isPending, error } = useCreateReviewRun();

  const readiness = runReadiness(document);
  const canStart = readiness.canStart && Boolean(profile && modelProfile) && !isPending;

  async function handleStart(): Promise<void> {
    if (!document || !profile || !modelProfile) {
      return;
    }
    try {
      const run = await createRun({
        workspaceId,
        documentId: document.id,
        contextDocumentIds: contextDocuments.map((item) => item.id),
        profile,
        modelProfile,
      });
      void navigate(`/runs/${run.id}`);
    } catch {
      // Причина показывается сообщением из состояния мутации.
    }
  }

  if (isLoading || !limits) {
    return (
      <main className="p-10">
        <Spinner label="Загружаем рабочее пространство…" />
      </main>
    );
  }

  return (
    <div className="flex flex-1">
      {isContextOpen ? (
        <ContextDocuments
          workspaceId={workspaceId}
          limits={limits}
          documents={contextDocuments}
          onAttach={(attached) => setContextDocuments((current) => [...current, attached])}
          onDetach={(id) => setContextDocuments((current) => current.filter((item) => item.id !== id))}
          onClose={() => setIsContextOpen(false)}
        />
      ) : null}

      <ContextPanelTab
        isOpen={isContextOpen}
        count={contextDocuments.length}
        onToggle={() => setIsContextOpen((open) => !open)}
      />

      <main className="min-w-0 flex-1 p-10">
        <nav aria-label="Хлебные крошки" className="text-xs text-ink-subtle">
          <Link to="/" className="hover:underline">
            Проверки
          </Link>
          <span aria-hidden="true"> / </span>
          <span>Новая проверка</span>
        </nav>

        <h1 className="mt-3 text-3xl font-bold text-ink">Новая проверка</h1>
        <p className="mt-2 text-sm text-ink-muted">
          Загрузите готовое ТЗ и проверьте контекст, который получит агент.
        </p>

        <p className="mt-4 flex items-start gap-2 rounded-lg border border-line bg-surface px-4 py-3 text-xs text-ink-muted">
          <span
            aria-hidden="true"
            className="mt-px flex size-4 shrink-0 items-center justify-center rounded-full border border-ink-subtle text-[10px] font-semibold text-ink-subtle"
          >
            i
          </span>
          Замечания - это кандидаты на уточнение, а не подтверждённые дефекты. Принимайте итоговые решения
          самостоятельно.
        </p>

        <section className="mt-3 rounded-lg border border-line bg-surface p-8">
          <h2 id="document-title" className="text-base font-bold text-ink">
            Документ на проверку
          </h2>
          <div className="mt-3" aria-labelledby="document-title">
            <DocumentUpload workspaceId={workspaceId} limits={limits} document={document} onUploaded={setDocument} />
          </div>

          <hr className="my-6 border-line" />

          <h2 id="settings-title" className="text-base font-bold text-ink">
            Параметры проверки
          </h2>
          <div aria-labelledby="settings-title" className="mt-4 grid gap-6 lg:grid-cols-2">
            <div className="flex flex-col gap-6">
              {profilesQuery.data ? (
                <ReviewProfileSelect
                  profiles={profilesQuery.data.items}
                  selectedId={profile?.id}
                  onSelect={setProfile}
                />
              ) : (
                <Spinner label="Загружаем профили проверки…" />
              )}
              {modelProfilesQuery.data ? (
                <ModelProfileSelect
                  profiles={modelProfilesQuery.data.items}
                  selectedId={modelProfile?.id}
                  onSelect={setModelProfile}
                />
              ) : (
                <Spinner label="Загружаем профили модели…" />
              )}
            </div>

            <div className="flex flex-col gap-1">
              <p className="text-xs font-bold text-ink-muted">Контекст агента</p>
              <button
                type="button"
                onClick={() => setIsContextOpen((open) => !open)}
                className="flex cursor-pointer items-center justify-between gap-3 rounded border border-accent bg-accent-tint px-3 py-2.5 text-sm text-ink"
              >
                <span className="font-medium">
                  Подключено материалов: {contextDocuments.length} из {limits.max_context_documents}
                </span>
                <span className="font-medium text-accent">{isContextOpen ? 'Панель открыта' : 'Открыть панель'}</span>
              </button>
              <p className="text-xs text-ink-subtle">Правила команды, шаблон и материалы текущего запуска.</p>
            </div>
          </div>

          {readiness.blockedReason ? (
            <div className="mt-6">
              <Callout tone="danger" title={readiness.blockedReason}>
                {readiness.nextStep}
              </Callout>
            </div>
          ) : null}

          {readiness.warning ? (
            <div className="mt-3">
              <Callout tone="warn" title={readiness.warning} />
            </div>
          ) : null}

          {error ? (
            <div className="mt-3">
              <Callout tone="danger" title="Не удалось создать проверку">
                {isProblem(error) ? error.problem.title : 'Повторите попытку.'}
              </Callout>
            </div>
          ) : null}

          <hr className="my-6 border-line" />

          <div className="flex flex-wrap items-center justify-between gap-4">
            <p className="max-w-md text-xs text-ink-muted">
              Проверка идёт в фоне: можно закрыть страницу и вернуться к запуску позже.
            </p>
            <div className="flex items-center gap-3">
              <Button onClick={() => void navigate('/')}>Отмена</Button>
              <Button variant="primary" disabled={!canStart} onClick={() => void handleStart()}>
                {isPending ? 'Запускаем…' : 'Запустить проверку'}
              </Button>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

/**
 * Язычок панели контекста на её внешнем крае.
 *
 * Открытие и закрытие живут в одном месте: контрол не переезжает при смене
 * состояния, поэтому свёрнутую панель не приходится искать в другом блоке.
 */
function ContextPanelTab({
  isOpen,
  count,
  onToggle,
}: {
  isOpen: boolean;
  count: number;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={isOpen}
      aria-controls="context-panel"
      title={isOpen ? 'Свернуть контекст проверки' : 'Развернуть контекст проверки'}
      className="flex w-7 shrink-0 cursor-pointer flex-col items-center gap-3 border-r border-line bg-surface pt-6 text-ink-muted hover:bg-surface-muted hover:text-ink"
    >
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
        <path d={isOpen ? 'M9 2L4 7l5 5' : 'M5 2l5 5-5 5'} strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="text-xs font-medium [writing-mode:vertical-rl]">Контекст · {count}</span>
    </button>
  );
}

export default NewReviewPage;
