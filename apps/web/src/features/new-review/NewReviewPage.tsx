import { useState } from 'react';
import { useNavigate } from 'react-router';
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
import { WorkspaceSummary } from './components/WorkspaceSummary';
import { runReadiness } from './lib/run-readiness';

/** Подготовка проверки: документ, контекст, профили, запуск (US1, US5). */
export function NewReviewPage() {
  const navigate = useNavigate();
  const { workspace, actor, limits, workspaceId, isLoading } = useBootstrap();
  const [document, setDocument] = useState<Document | undefined>(undefined);
  const [contextDocuments, setContextDocuments] = useState<Document[]>([]);
  const [profile, setProfile] = useState<ReviewProfile | undefined>(undefined);
  const [modelProfile, setModelProfile] = useState<ModelProfile | undefined>(undefined);

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
      <main className="mx-auto max-w-4xl p-6">
        <Spinner label="Загружаем рабочее пространство…" />
      </main>
    );
  }

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-5 p-6">
      <h1 className="text-xl font-semibold text-ink">Новая проверка</h1>

      <WorkspaceSummary workspace={workspace} actor={actor} limits={limits} isLoading={isLoading} />

      <section aria-labelledby="document-title" className="rounded border border-line bg-surface p-4">
        <h2 id="document-title" className="mb-3 text-sm font-semibold text-ink">
          Документ на проверку
        </h2>
        <DocumentUpload workspaceId={workspaceId} limits={limits} document={document} onUploaded={setDocument} />
      </section>

      <ContextDocuments
        workspaceId={workspaceId}
        limits={limits}
        documents={contextDocuments}
        onAttach={(attached) => setContextDocuments((current) => [...current, attached])}
        onDetach={(id) => setContextDocuments((current) => current.filter((item) => item.id !== id))}
      />

      <section aria-labelledby="settings-title" className="flex flex-col gap-4 rounded border border-line bg-surface p-4">
        <h2 id="settings-title" className="text-sm font-semibold text-ink">
          Параметры проверки
        </h2>
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
      </section>

      {readiness.blockedReason ? (
        <Callout tone="danger" title={readiness.blockedReason}>
          {readiness.nextStep}
        </Callout>
      ) : null}

      {readiness.warning ? <Callout tone="warn" title={readiness.warning} /> : null}

      {error ? (
        <Callout tone="danger" title="Не удалось создать проверку">
          {isProblem(error) ? error.problem.title : 'Повторите попытку.'}
        </Callout>
      ) : null}

      <div className="flex items-center gap-3">
        <Button variant="primary" disabled={!canStart} onClick={() => void handleStart()}>
          {isPending ? 'Запускаем…' : 'Запустить проверку'}
        </Button>
        <p className="text-xs text-ink-muted">
          Проверка идёт в фоне: можно закрыть страницу и вернуться к запуску позже.
        </p>
      </div>
    </main>
  );
}

export default NewReviewPage;
