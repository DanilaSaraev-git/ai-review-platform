import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { useListModelProfiles, useListReviewProfiles } from '@/api/generated/endpoints';
import type { Document, ModelProfile, ReviewProfile } from '@/api/generated/model';
import { isProblem } from '@/api/errors';
import { Button, Callout, Spinner } from '@/components/ui';
import { Icon } from '@/components/ui/Icon';
import { DocumentViewer } from '@/components/document-viewer';
import '@/styles/review-entry.css';
import { useBootstrap } from './api/use-bootstrap';
import { useCreateReviewRun } from './api/use-create-review-run';
import { ContextDocuments } from './components/ContextDocuments';
import { DocumentUpload } from './components/DocumentUpload';
import { ModelProfileSelect } from './components/ModelProfileSelect';
import { ReviewProfileSelect } from './components/ReviewProfileSelect';
import { runReadiness } from './lib/run-readiness';

/**
 * Подготовка проверки: документ, контекст, профили, запуск (US1, US5).
 * Основной документ остаётся рядом с параметрами и контекстом запуска.
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
    <main className={`entry-page ${document ? 'entry-page--with-document' : ''}`}>
      <div className="entry-workspace">
        {document ? (
          <div className="entry-document" data-primary-document>
            <DocumentViewer key={`${workspaceId}:${document.id}`} workspaceId={workspaceId} document={document} finding={undefined} />
          </div>
        ) : null}
        <div className="entry-setup">
          <h1>Новая проверка</h1>
          <DocumentUpload workspaceId={workspaceId} limits={limits} document={document} onUploaded={setDocument} />

          <section aria-labelledby="settings-title" className="entry-settings-section">
            <h2 id="settings-title">Параметры проверки</h2>
            <div className="entry-settings">
              {profilesQuery.data ? (
                <ReviewProfileSelect profiles={profilesQuery.data.items} selectedId={profile?.id} onSelect={setProfile} />
              ) : profilesQuery.isError ? (
                <div className="entry-settings-message">
                  <Callout tone="danger" title="Не удалось загрузить профили проверки">
                    <Button onClick={() => void profilesQuery.refetch()}>Повторить</Button>
                  </Callout>
                </div>
              ) : (
                <div className="entry-settings-message"><Spinner label="Загружаем профили проверки…" /></div>
              )}
              <div className="entry-setting-group">
                <button
                  type="button"
                  className="entry-setting entry-setting-toggle"
                  aria-expanded={isContextOpen}
                  aria-controls="context-panel"
                  onClick={() => setIsContextOpen((open) => !open)}
                >
                  <span className="entry-setting-label"><Icon name="paperclip" />Контекст</span>
                  <span className="entry-setting-value">
                    {contextDocuments.length > 0 ? `Материалов: ${contextDocuments.length}` : 'Добавить материалы'}
                    <Icon name="chevron-right" className={isContextOpen ? 'entry-chevron-open' : ''} />
                  </span>
                </button>
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
              </div>
              <details className="entry-setting-group entry-model-details">
                <summary className="entry-setting">
                  <span className="entry-setting-label"><Icon name="sliders" />Модель</span>
                  <span className="entry-setting-value">{modelProfile?.name ?? 'Не выбрана'}<Icon name="chevron-right" /></span>
                </summary>
                <div className="entry-setting-body">
                  {modelProfilesQuery.data ? (
                    <ModelProfileSelect profiles={modelProfilesQuery.data.items} selectedId={modelProfile?.id} onSelect={setModelProfile} />
                  ) : modelProfilesQuery.isError ? (
                    <Callout tone="danger" title="Не удалось загрузить профили модели">
                      <Button onClick={() => void modelProfilesQuery.refetch()}>Повторить</Button>
                    </Callout>
                  ) : <Spinner label="Загружаем профили модели…" />}
                </div>
              </details>
            </div>
          </section>

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
                Запуск станет доступен после подключения модели администратором сервиса.
              </Callout>
            </div>
          ) : null}

          <div className="entry-actions">
            <Button variant="primary" disabled={!canStart} onClick={() => void handleStart()}>
              {isPending ? 'Запускаем…' : 'Запустить проверку'}
              <Icon name="arrow-right" />
            </Button>
          </div>
        </div>
      </div>
    </main>
  );
}

export default NewReviewPage;
