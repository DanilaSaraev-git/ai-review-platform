import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router';
import { getGetReviewCycleQueryKey, useCompareReviewCycle, useGetReviewCycle, useGetReviewReport, usePutIssueResolution, usePutReviewCycleLink } from '@/api/generated/endpoints';
import type { ReviewCycle, CycleEntry } from '@/api/generated/model';
import { isProblem } from '@/api/errors';
import { Button, Callout, Field, Spinner, StatusBadge, TextArea } from '@/components/ui';
import { DecisionSummary } from '@/features/finding-decision/components/DecisionSummary';
import { useWorkspaceRun } from '@/features/review-report/components/ReviewWorkspaceLayout';
import { useReviewReport } from '@/features/review-report/api/use-review-report';
import { formatDateTime } from '@/lib/format';
import { comparisonText } from './comparison-text';

const STATUS: Record<CycleEntry['status'], string> = {
  new: 'Новое', persisting: 'Повторилось', not_detected: 'Больше не обнаружено',
  uncertain: 'Связь требует проверки', not_checked: 'Не проверено', reappeared: 'Обнаружено снова',
};

export function ReviewCyclePage() {
  const { workspaceId, runState: { run } } = useWorkspaceRun();
  if (!run) return <div className="p-5"><Spinner label="Загружаем проверку…" /></div>;
  return <ReviewCyclePanel key={run.id} workspaceId={workspaceId} runId={run.id} />;
}

export function ReviewCyclePanel({ workspaceId, runId }: { workspaceId: string; runId: string }) {
  const query = useGetReviewCycle(workspaceId, runId);
  const compare = useCompareReviewCycle();
  const cache = useQueryClient();
  const [error, setError] = useState<string>();
  async function retryComparison() {
    if (!query.data) return;
    setError(undefined);
    try {
      const cycle = await compare.mutateAsync({ workspaceId, runId, data: { expected_revision: query.data.revision } });
      cache.setQueryData(getGetReviewCycleQueryKey(workspaceId, runId), cycle);
    } catch (cause) { setError(isProblem(cause) && cause.status === 409 ? 'Сравнение изменилось. Обновите состояние перед повтором.' : 'Не удалось повторить сравнение.'); }
  }
  if (query.isPending) return <div className="p-5"><Spinner label="Загружаем сравнение…" /></div>;
  if (query.isError) return <div className="p-5"><Callout tone="danger" title="Не удалось загрузить сравнение"><Button onClick={() => void query.refetch()}>Повторить загрузку</Button></Callout><Link to={`/runs/${runId}/report`} className="mt-3 inline-block text-sm text-accent">К замечаниям</Link></div>;
  const cycle = query.data;
  return <div className="numbat-panel-scroll p-5">
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-medium">Изменения замечаний</h2><Link className="text-xs text-accent" to={`/runs/${runId}/report`}>К замечаниям</Link></div>
    {cycle.baseline_run_id ? <Link className="text-xs text-accent" to={`/runs/${cycle.baseline_run_id}/report`}>Базовая проверка для сравнения</Link> : <p className="text-xs text-ink-muted">Первая проверка документа: базы для сравнения нет.</p>}
    {cycle.compared_at ? <p className="my-2 text-xs text-ink-muted">Сравнение от {formatDateTime(cycle.compared_at)}</p> : null}
    {cycle.status === 'unavailable' ? <div className="my-3"><Callout tone="warn" title="Сравнение не завершено">Основной отчёт доступен. Отсутствие замечания не подтверждает исправление.</Callout></div> : null}
    {cycle.limitations.length ? <ul aria-label="Ограничения сравнения" className="my-3 list-disc space-y-1 pl-5 text-xs text-ink-muted">{cycle.limitations.map((item, index) => <li key={index}>{comparisonText(item)}</li>)}</ul> : null}
    {error ? <div className="my-3"><Callout tone="warn" title={error}><Button onClick={() => { setError(undefined); void query.refetch(); }}>Обновить состояние</Button></Callout></div> : null}
    <Button className="my-3" disabled={compare.isPending} onClick={() => void retryComparison()}>{compare.isPending ? 'Сравниваем…' : 'Повторить сравнение'}</Button>
    <p className="mb-4 text-xs text-ink-muted">«Больше не обнаружено» не означает «Исправлено». Исправление подтверждает аналитик.</p>
    <div className="space-y-4">{cycle.entries.map((entry) => <CycleEntryCard key={entry.issue_id} workspaceId={workspaceId} runId={runId} cycle={cycle} entry={entry} />)}</div>
    {cycle.entries.length === 0 ? <p className="text-sm text-ink-muted">Замечаний в истории пока нет.</p> : null}
  </div>;
}

function CycleEntryCard({ workspaceId, runId, cycle, entry }: { workspaceId: string; runId: string; cycle: ReviewCycle; entry: CycleEntry }) {
  const cache = useQueryClient();
  const resolution = usePutIssueResolution();
  const link = usePutReviewCycleLink();
  const [reason, setReason] = useState('');
  const [previousIssue, setPreviousIssue] = useState('');
  const [error, setError] = useState<string>();
  const [conflict, setConflict] = useState(false);
  const previousRunId = entry.previous_run_id ?? entry.origin_run_id;
  const previousFindingId = entry.previous_finding_id ?? entry.origin_finding_id;
  const { report } = useReviewReport(workspaceId, runId);
  const priorReport = useGetReviewReport(workspaceId, previousRunId, { query: { enabled: Boolean(previousRunId && previousRunId !== runId) } });
  const currentFinding = report?.findings.find((finding) => finding.id === entry.current_finding_id);
  const priorFinding = priorReport.data?.findings.find((finding) => finding.id === previousFindingId);
  const options = cycle.entries.filter((candidate) => candidate.issue_id !== entry.issue_id && !candidate.current_finding_id);
  const hasPrevious = entry.origin_run_id !== runId;
  const pending = resolution.isPending || link.isPending;
  async function save(action: 'resolution' | 'link' | 'unlink') {
    setError(undefined);
    setConflict(false);
    try {
      const updated = action === 'resolution'
        ? await resolution.mutateAsync({ workspaceId, runId, issueId: entry.issue_id, data: { status: entry.resolution.status === 'resolved' ? 'open' : 'resolved', reason: reason.trim(), expected_revision: entry.resolution.revision } })
        : await link.mutateAsync({ workspaceId, runId, findingId: entry.current_finding_id!, data: { previous_issue_id: action === 'unlink' ? null : previousIssue, expected_revision: cycle.revision } });
      cache.setQueryData(getGetReviewCycleQueryKey(workspaceId, runId), updated);
      setReason('');
      setPreviousIssue('');
    } catch (cause) {
      const stale = isProblem(cause) && cause.status === 409;
      setConflict(stale);
      setError(stale ? 'Состояние изменилось или связь уже занята. Обновите данные и проверьте выбор; пояснение сохранено в форме.' : isProblem(cause) ? cause.problem.title : 'Изменение не сохранено. Повторите попытку.');
    }
  }
  return <article aria-label={currentFinding?.title ?? priorFinding?.title ?? 'Замечание из истории'} className="rounded-[6px] border border-line p-4">
    <StatusBadge tone={['uncertain', 'not_checked', 'reappeared'].includes(entry.status) ? 'warn' : 'neutral'}>{STATUS[entry.status]}</StatusBadge>
    <h3 className="my-3 break-words text-sm font-medium">{currentFinding?.title ?? priorFinding?.title ?? 'Замечание из предыдущей проверки'}</h3>
    <p className="mb-3 text-xs leading-5 text-ink-muted">{comparisonText(entry.match_basis)}</p>
    {entry.current_finding_id ? <Link to={`/runs/${runId}/report/findings/${entry.current_finding_id}`} className="text-xs text-accent">Открыть текущее замечание</Link> : null}
    {hasPrevious ? <Link to={`/runs/${previousRunId}/report/findings/${previousFindingId}/dialogue`} className="mt-2 block text-xs text-accent">Предыдущее замечание и обсуждение</Link> : null}
    {entry.status === 'reappeared' || (entry.previous_decision && !entry.decision_carried) ? <p className="my-3 text-xs font-medium text-warn">Требуется новая оценка замечания.</p> : null}
    {entry.previous_decision ? <section className="my-3 border-t border-line pt-3" aria-label="Прежнее решение">
      <h4 className="mb-2 text-xs font-medium">{entry.decision_carried ? 'Оценка перенесена из предыдущей проверки' : 'Прежнее решение — для справки'}</h4>
      <DecisionSummary decision={entry.previous_decision} />
    </section> : null}
    {entry.current_finding_id ? <details className="my-3 border-t border-line pt-3"><summary className="cursor-pointer text-xs font-medium">Исправить связь замечаний</summary>
      <label className="mt-3 block text-xs" htmlFor={`link-${entry.issue_id}`}>Предыдущая проблема</label>
      <select id={`link-${entry.issue_id}`} className="my-2 w-full rounded border border-line bg-surface p-2 text-xs" value={previousIssue} onChange={(event) => setPreviousIssue(event.target.value)} disabled={pending || conflict}>
        <option value="">Выберите несвязанную проблему</option>
        {options.map((candidate) => <PreviousIssueOption key={candidate.issue_id} workspaceId={workspaceId} entry={candidate} />)}
      </select>
      <div className="flex flex-wrap gap-2"><Button disabled={!previousIssue || pending || conflict} onClick={() => void save('link')}>Связать</Button>{hasPrevious ? <Button disabled={pending || conflict} onClick={() => void save('unlink')}>Разъединить</Button> : null}</div>
    </details> : null}
    <section className="mt-3 border-t border-line pt-3" aria-label="Исправление">
      <p className="mb-2 text-xs font-medium">{entry.resolution.status === 'resolved' ? 'Исправление подтверждено аналитиком' : 'Исправление не подтверждено'}</p>
      {entry.resolution.reason ? <p className="mb-2 whitespace-pre-wrap break-words text-xs text-ink-muted">{entry.resolution.reason}</p> : null}
      {entry.resolution.actor ? <p className="mb-3 text-xs text-ink-muted">{entry.resolution.actor.display_name} · {formatDateTime(entry.resolution.decided_at)}</p> : null}
      <Field label="Пояснение к исправлению">{(id) => <TextArea id={id} value={reason} onChange={(event) => setReason(event.target.value)} disabled={pending} />}</Field>
      <Button className="mt-2" disabled={!reason.trim() || pending || conflict} onClick={() => void save('resolution')}>{entry.resolution.status === 'resolved' ? 'Вернуть в работу' : 'Подтвердить исправление'}</Button>
    </section>
    {error ? <div role="alert" className="mt-3 text-xs text-accent"><p>{error}</p>{conflict ? <Button className="mt-2" onClick={async () => { await cache.invalidateQueries({ queryKey: getGetReviewCycleQueryKey(workspaceId, runId) }); setConflict(false); setError(undefined); }}>Обновить состояние</Button> : null}</div> : null}
  </article>;
}

function PreviousIssueOption({ workspaceId, entry }: { workspaceId: string; entry: CycleEntry }) {
  const report = useGetReviewReport(workspaceId, entry.previous_run_id ?? entry.origin_run_id);
  const finding = report.data?.findings.find((item) => item.id === (entry.previous_finding_id ?? entry.origin_finding_id));
  return <option value={entry.issue_id}>{finding?.title ?? 'Предыдущее замечание'} · {STATUS[entry.status]}</option>;
}
