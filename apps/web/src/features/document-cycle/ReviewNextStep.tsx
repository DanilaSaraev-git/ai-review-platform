import { useState } from 'react';
import { Link } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { getGetReviewCycleQueryKey, useCompleteReviewCycle, useGetReviewCycle } from '@/api/generated/endpoints';
import type { FindingState, ReviewCycle, ReviewReport } from '@/api/generated/model';
import { Button, Callout } from '@/components/ui';
import { useFindingStates } from '@/features/review-report/api/use-finding-states';
import { useReviewReport } from '@/features/review-report/api/use-review-report';
import { useWorkspaceRun } from '@/features/review-report/components/ReviewWorkspaceLayout';

export function nextStep(report: ReviewReport, states: Map<string, FindingState>, cycle: ReviewCycle) {
  const pending = report.findings.filter(f => !states.has(f.id) || states.get(f.id)?.decision.status === 'unreviewed');
  const context = report.findings.filter(f => states.get(f.id)?.decision.status === 'needs_context');
  if (pending.length) return { title: `Осталось рассмотреть: ${pending.length}`, text: 'Примите замечания к доработке, отклоните их или запросите уточнение.', action: 'Продолжить разбор', finding: pending[0]!.id };
  if (context.length) return { title: `Нужны уточнения: ${context.length}`, text: 'Добавьте недостающие сведения или файл в диалог по замечанию.', action: 'Перейти к уточнениям', finding: context[0]!.id, dialogue: true };
  if (cycle.status !== 'ready' || cycle.entries.some(e => e.status === 'uncertain' || e.status === 'not_checked') || cycle.limitations.length || report.coverage.status !== 'complete')
    return { title: 'Проверка требует внимания', text: 'Анализ или сопоставление неполны. Отсутствие замечаний не подтверждает исправление.', action: 'Проверить ограничения', fixes: true };
  const fixes = cycle.entries.filter(e => !e.current_finding_id && e.resolution.status !== 'resolved' && e.previous_decision?.status !== 'rejected');
  if (fixes.length) return { title: `Подтвердите исправления: ${fixes.length}`, text: 'В этой версии замечания больше не обнаружены. Проверьте изменения в исходнике.', action: 'Проверить исправления', fixes: true };
  if (report.findings.some(f => states.get(f.id)?.decision.status === 'confirmed' && !cycle.entries.some(e => e.current_finding_id === f.id && e.resolution.status === 'resolved')))
    return { title: 'Все замечания рассмотрены', text: 'Внесите согласованные правки и загрузите новую версию.', action: 'Загрузить новую версию', upload: true };
  if (cycle.completion) return { title: 'Проверка завершена', text: 'Решения сохранены. Новая версия продолжит цикл проверки.', action: 'Загрузить новую версию', upload: true };
  return { title: 'Замечания разобраны', text: 'Открытых вопросов нет. Проверку можно завершить.', action: 'Завершить проверку', complete: true };
}

export function ReviewNextStep() {
  const { workspaceId, runState: { run }, openVersion, historical } = useWorkspaceRun();
  const id = run?.id ?? '';
  const { report } = useReviewReport(workspaceId, id);
  const states = useFindingStates(workspaceId, id);
  const cycle = useGetReviewCycle(workspaceId, id, { query: { enabled: Boolean(id) } });
  const mutation = useCompleteReviewCycle();
  const cache = useQueryClient();
  const [error, setError] = useState('');
  if (historical || !report) return null;
  if (states.error || cycle.isError) return <div className="p-5"><Callout tone="warn" title="Состояние разбора недоступно"><Button onClick={() => { void states.retry(); void cycle.refetch(); }}>Обновить состояние</Button></Callout></div>;
  if (states.isLoading || !cycle.data) return null;
  const step = nextStep(report, states.byFindingId, cycle.data);
  return <section className="review-next-step" aria-label="Следующий шаг">
    <h2>{step.title}</h2><p>{step.text}</p>
    {step.finding ? <Link className="review-primary-link" to={`/runs/${id}/report/findings/${step.finding}${step.dialogue ? '/dialogue' : ''}`}>{step.action}</Link>
      : <Button variant="primary" disabled={mutation.isPending} onClick={async () => {
        if (step.upload) { openVersion(); return; }
        if (step.fixes) { document.getElementById('review-fixes')?.scrollIntoView({ behavior: 'smooth' }); return; }
        try {
          const result = await mutation.mutateAsync({ workspaceId, runId: id, data: { expected_revision: cycle.data!.revision } });
          cache.setQueryData(getGetReviewCycleQueryKey(workspaceId, id), result); setError('');
        } catch { setError('Не удалось завершить проверку. Обновите состояние и проверьте открытые вопросы.'); void states.retry(); void cycle.refetch(); }
      }}>{step.action}</Button>}
    {error ? <p role="alert">{error}</p> : null}
  </section>;
}
