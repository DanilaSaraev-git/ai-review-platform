import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { useGetDocument } from '@/api/generated/endpoints';
import { Callout, Spinner } from '@/components/ui';
import { DocumentViewer } from '@/components/document-viewer';
import { NotFoundPage } from '@/app/NotFoundPage';
import { useBootstrap } from '@/features/new-review/api/use-bootstrap';
import { DecisionForm } from '@/features/finding-decision/components/DecisionForm';
import { DecisionProgress } from '@/features/finding-decision/components/DecisionProgress';
import { DecisionSummary } from '@/features/finding-decision/components/DecisionSummary';
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
  const { workspaceId } = useBootstrap();
  const { report, isLoading, isUnavailable, isNotFound } = useReviewReport(workspaceId, runId);
  const { byFindingId, reviewedCount } = useFindingStates(workspaceId, runId);

  // Перенос предложенной резолюции — отдельное действие: текст только
  // подставляется в форму, сохранение остаётся за аналитиком (FR-029).
  const [prefilledResolution, setPrefilledResolution] = useState<string | null>(null);

  const finding = report?.findings.find((item) => item.id === findingId);
  const anchorDocumentId = finding?.anchors[0]?.document_id ?? report?.provenance.sources[0]?.document_id ?? '';
  const documentQuery = useGetDocument(workspaceId, anchorDocumentId, {
    query: { enabled: Boolean(workspaceId && anchorDocumentId) },
  });

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
            <h1 className="truncate text-[15px] font-semibold text-ink">{finding.title}</h1>
            <p className="text-xs text-ink-subtle">Замечание {finding.ordinal}</p>
          </div>
          <div className="ml-auto">
            <DecisionProgress reviewed={reviewedCount} total={report.findings.length} />
          </div>
        </>
      }
      document={<DocumentViewer workspaceId={workspaceId} document={documentQuery.data} finding={finding} />}
      panel={
        <div className="flex flex-col">
          <div className="border-b border-line p-4">
            <FindingCard finding={finding} state={state} runId={runId} isSelected />
          </div>
          <div className="border-b border-line px-4 py-3">
            <h3 className="mb-2 text-xs font-semibold text-ink">Текущее решение</h3>
            <DecisionSummary decision={state?.decision} />
          </div>
          <DecisionForm
            workspaceId={workspaceId}
            runId={runId}
            findingId={finding.id}
            decision={state?.decision}
            prefilledResolution={prefilledResolution}
          />
          <DialoguePanel
            workspaceId={workspaceId}
            runId={runId}
            findingId={finding.id}
            onUseResolution={setPrefilledResolution}
          />
        </div>
      }
    />
  );
}

export default FindingPage;
