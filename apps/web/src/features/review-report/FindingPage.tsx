import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router';
import { Button, Callout, Spinner } from '@/components/ui';
import { NotFoundPage } from '@/app/NotFoundPage';
import { DecisionForm } from '@/features/finding-decision/components/DecisionForm';
import { DialoguePanel } from '@/features/finding-dialogue/components/DialoguePanel';
import { useFindingStates } from './api/use-finding-states';
import { useReviewReport } from './api/use-review-report';
import { FindingCard } from './components/FindingCard';
import { useWorkspaceRun } from './components/ReviewWorkspaceLayout';

/** Finding, dialogue and human decision share the persistent primary document. */
export function FindingPage() {
  const { runId = '', findingId = '' } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { workspaceId } = useWorkspaceRun();
  const { report, isLoading, isUnavailable, isNotFound, error, retry } = useReviewReport(workspaceId, runId);
  const { byFindingId, rawByFindingId, carriedByFindingId, error: statesError, retry: retryStates } = useFindingStates(workspaceId, runId);
  const [prefilledResolution, setPrefilledResolution] = useState<string | null>(null);
  const isDialogue = location.pathname.endsWith('/dialogue');

  useEffect(() => { setPrefilledResolution(null); }, [findingId]);

  if (isNotFound) return <NotFoundPage detail="Такой проверки нет. Возможно, ссылка устарела или идентификатор указан неверно." />;
  if (isUnavailable) return <div className="p-5"><Callout tone="warn" title="Отчёта пока нет">Проверка не завершилась успешно, поэтому замечаний нет.</Callout></div>;
  if (error && !report) return <div className="p-5"><Callout tone="danger" title="Не удалось загрузить отчёт">
    <Button className="mt-2" onClick={() => void retry()}>Повторить</Button>
  </Callout></div>;
  if (isLoading || !report) return <div className="p-5"><Spinner label="Загружаем отчёт…" /></div>;
  const finding = report.findings.find((item) => item.id === findingId);
  if (!finding) return <NotFoundPage detail="Такого замечания нет в этом отчёте." />;
  const state = byFindingId.get(finding.id);
  const ordered = [...report.findings].sort((left, right) => left.ordinal - right.ordinal);
  const index = ordered.findIndex((item) => item.id === findingId);
  const next = ordered[index + 1];

  return (
    <div className="numbat-panel-scroll">
      <nav className="numbat-finding-navigation" aria-label="Замечания">
        <Link aria-label="К списку замечаний" to={`/runs/${runId}/report`}>← Все замечания</Link>
        <div className="flex items-center gap-4">
          <span>{index + 1} из {ordered.length}</span>
          {next ? <Link to={`/runs/${runId}/report/findings/${next.id}`}>Следующее →</Link> : null}
        </div>
      </nav>
      {statesError ? <div className="p-4"><Callout tone="warn" title="Состояние замечания не обновилось">
        <Button className="mt-2" onClick={() => void retryStates()}>Повторить</Button>
      </Callout></div> : null}
      <FindingCard finding={finding} state={state} runId={runId} isSelected />
      {carriedByFindingId.has(finding.id) ? <p className="px-5 py-3 text-xs text-ink-muted">Оценка перенесена из предыдущей проверки с исходным автором и датой. <Link to={`/runs/${runId}/report/changes`} className="text-accent">Посмотреть происхождение</Link></p> : null}
      <div className="numbat-finding-tabs" role="tablist" aria-label="Работа с замечанием" aria-orientation="horizontal"
        onKeyDown={(event) => {
          const keys = ['ArrowLeft', 'ArrowRight', 'Home', 'End'];
          if (!keys.includes(event.key)) return;
          event.preventDefault();
          const tabs = event.currentTarget.querySelectorAll<HTMLAnchorElement>('[role="tab"]');
          const focusedDialogue = event.target === tabs[1];
          const nextDialogue = event.key === 'Home' ? false : event.key === 'End' ? true : !focusedDialogue;
          tabs[nextDialogue ? 1 : 0]?.focus();
          void navigate(`/runs/${runId}/report/findings/${finding.id}${nextDialogue ? '/dialogue' : ''}`);
        }}>
        <Link id={`decision-tab-${finding.id}`} role="tab" aria-selected={!isDialogue} aria-controls={`decision-panel-${finding.id}`} tabIndex={isDialogue ? -1 : 0} to={`/runs/${runId}/report/findings/${finding.id}`}>Решение</Link>
        <Link id={`dialogue-tab-${finding.id}`} role="tab" aria-selected={isDialogue} aria-controls={`dialogue-panel-${finding.id}`} tabIndex={isDialogue ? 0 : -1} to={`/runs/${runId}/report/findings/${finding.id}/dialogue`}>
          Диалог{state?.dialogue.turn_count ? ` · ${state.dialogue.turn_count}` : ''}
        </Link>
      </div>
      <div id={`dialogue-panel-${finding.id}`} role="tabpanel" aria-labelledby={`dialogue-tab-${finding.id}`} tabIndex={0} hidden={!isDialogue}>
        <DialoguePanel key={`dialogue-${finding.id}`} workspaceId={workspaceId} runId={runId} findingId={finding.id}
          onUseResolution={(text) => {
            // Both tabs stay mounted. Keep the transfer local so a reload cannot
            // replay it from browser history over the saved human decision.
            setPrefilledResolution(text);
            void navigate(`/runs/${runId}/report/findings/${finding.id}`);
          }} />
      </div>
      <div id={`decision-panel-${finding.id}`} role="tabpanel" aria-labelledby={`decision-tab-${finding.id}`} tabIndex={0} hidden={isDialogue}>
        <DecisionForm key={`decision-${finding.id}`} workspaceId={workspaceId} runId={runId} findingId={finding.id}
          decision={state?.decision} expectedRevision={rawByFindingId.get(finding.id)?.decision.revision ?? 0} prefilledResolution={prefilledResolution} />
      </div>
    </div>
  );
}

export default FindingPage;
