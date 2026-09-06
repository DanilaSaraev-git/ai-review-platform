import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router';
import { useGetDocument } from '@/api/generated/endpoints';
import { Button, Callout, Spinner } from '@/components/ui';
import { DocumentViewer } from '@/components/document-viewer';
import { NotFoundPage } from '@/app/NotFoundPage';
import { useBootstrap } from '@/features/new-review/api/use-bootstrap';
import { DecisionForm } from '@/features/finding-decision/components/DecisionForm';
import { DecisionProgress } from '@/features/finding-decision/components/DecisionProgress';
import { DialoguePanel } from '@/features/finding-dialogue/components/DialoguePanel';
import { useFindingStates } from './api/use-finding-states';
import { useReviewReport } from './api/use-review-report';
import { FindingCard } from './components/FindingCard';
import { ReviewWorkspace } from './components/ReviewWorkspace';

/**
 * Разбор одного замечания: фрагмент документа, решение человека и диалог
 * (US2, US3, US4).
 *
 * Замечание — часть URL, поэтому разбор восстанавливается по прямой ссылке и
 * после обновления страницы.
 */
export function FindingPage() {
  const { runId = '', findingId = '' } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { workspaceId, error: bootstrapError, retry: retryBootstrap } = useBootstrap();
  const { report, isLoading, isUnavailable, isNotFound, error, retry } = useReviewReport(workspaceId, runId);
  const { byFindingId, reviewedCount, error: statesError, retry: retryStates } = useFindingStates(workspaceId, runId);

  // Перенос предложенной резолюции — отдельное действие: текст только
  // подставляется в форму, сохранение остаётся за аналитиком (FR-029).
  const locationResolution = (location.state as { proposedResolution?: string } | null)?.proposedResolution ?? null;
  const [prefilledResolution, setPrefilledResolution] = useState<string | null>(locationResolution);
  const isDialogue = location.pathname.endsWith('/dialogue');

  useEffect(() => {
    setPrefilledResolution(locationResolution);
  }, [findingId, locationResolution]);

  const finding = report?.findings.find((item) => item.id === findingId);
  const anchorDocumentId = finding?.anchors[0]?.document_id ?? report?.provenance.sources[0]?.document_id ?? '';
  const documentQuery = useGetDocument(workspaceId, anchorDocumentId, {
    query: { enabled: Boolean(workspaceId && anchorDocumentId) },
  });

  if (bootstrapError && !workspaceId) {
    return (
      <main className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6">
        <Callout tone="danger" title="Не удалось загрузить рабочее пространство">
          <Button className="mt-2" onClick={() => void retryBootstrap()}>Повторить</Button>
        </Callout>
      </main>
    );
  }

  if (isNotFound) {
    return <NotFoundPage detail="Такой проверки нет. Возможно, ссылка устарела или идентификатор указан неверно." />;
  }

  if (isUnavailable) {
    return (
      <main className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6">
        <Callout tone="warn" title="Отчёта пока нет">
          Проверка не завершилась успешно, поэтому замечаний нет.
        </Callout>
      </main>
    );
  }

  if (error && !report) {
    return (
      <main className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6">
        <Callout tone="danger" title="Не удалось загрузить отчёт">
          <Button className="mt-2" onClick={() => void retry()}>Повторить</Button>
        </Callout>
      </main>
    );
  }

  if (isLoading || !report) {
    return (
      <main className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6">
        <Spinner label="Загружаем отчёт…" />
      </main>
    );
  }

  if (!finding) {
    return <NotFoundPage detail="Такого замечания нет в этом отчёте." />;
  }

  const state = byFindingId.get(finding.id);

  return (
    <ReviewWorkspace
      toolbar={
        <>
          <nav aria-label="Навигация">
            <Link aria-label="К списку замечаний" className="text-xs font-medium text-ink-muted hover:text-accent" to={`/runs/${runId}/report`}>
              ← Все замечания
            </Link>
          </nav>
          <div className="min-w-0">
            <h1 className="truncate text-[15px] font-semibold text-ink">{documentQuery.data?.filename ?? 'Исходный документ'}</h1>
            <p className="text-xs text-ink-subtle">Отчёт проверки</p>
          </div>
          <div className="ml-auto">
            <DecisionProgress reviewed={reviewedCount} total={report.findings.length} />
          </div>
        </>
      }
      document={documentQuery.isError ? (
        <Callout tone="danger" title="Не удалось загрузить сведения о документе">
          <Button className="mt-2" onClick={() => void documentQuery.refetch()}>Повторить</Button>
        </Callout>
      ) : <DocumentViewer workspaceId={workspaceId} document={documentQuery.data} finding={finding} />}
      panel={
        <div className="flex h-full min-h-0 flex-col">
          {statesError ? (
            <div className="border-b border-line p-4">
              <Callout tone="warn" title="Состояние замечания не обновилось">
                <Button className="mt-2" onClick={() => void retryStates()}>Повторить</Button>
              </Callout>
            </div>
          ) : null}
          <div className="border-b border-line p-4">
            <FindingCard finding={finding} state={state} runId={runId} isSelected />
          </div>
          <div className="flex border-b border-line px-4" role="tablist" aria-label="Работа с замечанием">
            <Link
              role="tab"
              aria-selected={!isDialogue}
              className={`relative px-3 py-3 text-[13px] font-semibold ${!isDialogue ? 'text-ink after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:bg-accent' : 'text-ink-muted hover:text-ink'}`}
              to={`/runs/${runId}/report/findings/${finding.id}`}
            >
              Решение
            </Link>
            <Link
              role="tab"
              aria-selected={isDialogue}
              className={`relative px-3 py-3 text-[13px] font-semibold ${isDialogue ? 'text-ink after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:bg-accent' : 'text-ink-muted hover:text-ink'}`}
              to={`/runs/${runId}/report/findings/${finding.id}/dialogue`}
            >
              Диалог{state?.dialogue.turn_count ? ` · ${state.dialogue.turn_count}` : ''}
            </Link>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto lg:overflow-hidden" hidden={!isDialogue}>
            <DialoguePanel
              key={`dialogue-${finding.id}`}
              workspaceId={workspaceId}
              runId={runId}
              findingId={finding.id}
              onUseResolution={(text) => {
                setPrefilledResolution(text);
                void navigate(`/runs/${runId}/report/findings/${finding.id}`, {
                  state: { proposedResolution: text },
                });
              }}
            />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto" hidden={isDialogue}>
            <DecisionForm
              key={`decision-${finding.id}`}
              workspaceId={workspaceId}
              runId={runId}
              findingId={finding.id}
              decision={state?.decision}
              prefilledResolution={prefilledResolution}
            />
          </div>
        </div>
      }
    />
  );
}

export default FindingPage;
