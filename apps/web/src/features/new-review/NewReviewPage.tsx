import { useEffect, useState } from 'react';
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
  const { workspaceId, limits, isLoading, error: bootstrapError, retry: retryBootstrap } = useBootstrap();
  const [document, setDocument] = useState<Document | undefined>(undefined);
  const [contextDocuments, setContextDocuments] = useState<Document[]>([]);
  const [profile, setProfile] = useState<ReviewProfile | undefined>(undefined);
  const [modelProfile, setModelProfile] = useState<ModelProfile | undefined>(undefined);
  const [isContextOpen, setIsContextOpen] = useState(false);

  const profilesQuery = useListReviewProfiles(workspaceId, { query: { enabled: Boolean(workspaceId) } });
  const modelProfilesQuery = useListModelProfiles(workspaceId, { query: { enabled: Boolean(workspaceId) } });
  const { createRun, isPending, error } = useCreateReviewRun();

  const readiness = runReadiness(document);
  const canStart = readiness.canStart && Boolean(profile && modelProfile) && !isPending;
  const modelProfiles = modelProfilesQuery.data?.items ?? [];
  const hasNoAvailableModel = modelProfilesQuery.isSuccess && !modelProfiles.some((item) => item.availability === 'available');
  const modelWasNotConfigured = modelProfiles.some((item) => /unconfigured|не подключ/iu.test(`${item.id} ${item.name}`));

  useEffect(() => {
    if (!profile && profilesQuery.data?.items[0]) {
      setProfile(profilesQuery.data.items[0]);
    }
  }, [profile, profilesQuery.data]);

  useEffect(() => {
    if (!modelProfile) {
      const available = modelProfilesQuery.data?.items.find((item) => item.availability === 'available');
      if (available) {
        setModelProfile(available);
      }
    }
  }, [modelProfile, modelProfilesQuery.data]);

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

  if (bootstrapError && !limits) {
    return (
      <main className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6">
        <Callout tone="danger" title="Не удалось загрузить рабочее пространство">
          <Button className="mt-2" onClick={() => void retryBootstrap()}>Повторить</Button>
        </Callout>
      </main>
    );
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

      <main className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
        <div className="mx-auto max-w-5xl">
        <nav aria-label="Хлебные крошки" className="text-xs text-ink-subtle">
          <Link to="/" className="hover:underline">
            Проверки
          </Link>
          <span aria-hidden="true"> / </span>
          <span>Новая проверка</span>
        </nav>

        <h1 className="mt-2 text-2xl font-semibold tracking-[-0.025em] text-ink">Новая проверка</h1>
        <p className="mt-1 max-w-2xl text-sm text-ink-muted">Документ, профиль и контекст одного запуска.</p>

        <section className="mt-5 rounded-[7px] border border-line bg-surface p-5 shadow-[0_1px_2px_rgba(23,32,51,0.04),0_8px_24px_rgba(23,32,51,0.03)] sm:p-6">
          <h2 id="document-title" className="text-[15px] font-semibold text-ink">
            Документ на проверку
          </h2>
          <div className="mt-3" aria-labelledby="document-title">
            <DocumentUpload workspaceId={workspaceId} limits={limits} document={document} onUploaded={setDocument} />
          </div>

          <button
            type="button"
            className="mt-3 flex min-h-9 w-full cursor-pointer items-center justify-between rounded-[5px] border border-line-strong bg-surface px-3 text-[13px] font-semibold text-ink sm:hidden"
            aria-expanded={isContextOpen}
            aria-controls="context-panel"
            onClick={() => setIsContextOpen(true)}
          >
            Контекст
            {contextDocuments.length > 0 ? <span className="text-ink-subtle">{contextDocuments.length}</span> : null}
          </button>

          <hr className="my-5 border-line" />

          <details className="group/settings">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-[13px] font-semibold text-ink [&::-webkit-details-marker]:hidden">
              <span id="settings-title">Параметры проверки</span>
              <span className="font-medium text-ink-subtle group-open/settings:hidden">
                {profile?.name ?? 'Профиль'} · {modelProfile?.name ?? 'Исполнение'}
              </span>
              <span className="hidden text-accent group-open/settings:inline">Свернуть</span>
            </summary>
            <div aria-labelledby="settings-title" className="mt-3 grid gap-5 lg:grid-cols-2">
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
          </details>

          {document && readiness.blockedReason ? (
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

          {hasNoAvailableModel ? (
            <div className="mt-3">
              <Callout
                tone="warn"
                title={modelWasNotConfigured ? 'Модель ещё не подключена' : 'Нет доступной модели'}
              >
                Подключите модель в конфигурации сервиса, чтобы запускать новые проверки.
              </Callout>
            </div>
          ) : null}

          <div className="sticky bottom-0 z-10 -mx-5 mt-5 flex justify-end border-t border-line bg-surface px-5 pb-1 pt-4 sm:-mx-6 sm:px-6">
            <Button variant="primary" disabled={!canStart} onClick={() => void handleStart()}>
              {isPending ? 'Запускаем…' : 'Запустить проверку'}
            </Button>
          </div>
        </section>
        </div>
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
  if (isOpen) {
    return null;
  }

  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={isOpen}
      aria-controls="context-panel"
      title={isOpen ? 'Свернуть контекст проверки' : 'Развернуть контекст проверки'}
      className="hidden w-8 shrink-0 cursor-pointer flex-col items-center gap-3 border-r border-line bg-surface pt-5 text-ink-muted transition-[background-color,color] duration-100 hover:bg-surface-muted hover:text-ink sm:flex"
    >
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
        <path d={isOpen ? 'M9 2L4 7l5 5' : 'M5 2l5 5-5 5'} strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="text-xs font-semibold [writing-mode:vertical-rl]">Контекст {count > 0 ? `· ${count}` : ''}</span>
    </button>
  );
}

export default NewReviewPage;
