import { listFindingStates, getReviewCycle, getReviewReport } from '@/api/generated/endpoints';

/** Browser PDF export for the demo, using the same tab-local API snapshot. */
export async function printDemoReport(workspaceId: string, runId: string) {
  const popup = window.open('', '_blank');
  if (!popup) throw new Error('Разрешите открытие окна для сохранения PDF');
  try {
    const [report, states, cycle] = await Promise.all([getReviewReport(workspaceId, runId), listFindingStates(workspaceId, runId), getReviewCycle(workspaceId, runId)]);
    const doc = popup.document;
    doc.title = 'Numbat — демонстрационный отчёт';
    doc.documentElement.lang = 'ru';
    const style = doc.createElement('style');
    style.textContent = 'body{font:16px/1.5 sans-serif;max-width:850px;margin:32px auto;padding:24px}h2{font-size:20px;margin-top:28px}@media print{button{display:none}}';
    doc.head.append(style);
    const add = (tag: string, text: string) => { const node = doc.createElement(tag); node.textContent = text; doc.body.append(node); };
    add('h1', 'Numbat · демонстрационный отчёт');
    add('p', `Версия ${cycle.version_number} · ${new Date().toLocaleString('ru-RU')}`);
    add('p', 'Синтетический сценарий. Модель не вызывалась.');
    add('p', cycle.completion ? 'Проверка завершена' : 'Проверка не завершена');
    add('p', report.summary);
    const labels = { unreviewed: 'Не рассмотрено', confirmed: 'Принято к доработке', rejected: 'Отклонено', needs_context: 'Нужен контекст' };
    for (const finding of report.findings) {
      const decision = states.items.find(s => s.finding_id === finding.id)?.decision;
      add('h2', finding.title); add('p', finding.problem); add('p', finding.question);
      add('p', labels[decision?.status ?? 'unreviewed']);
      if (decision?.reason) add('p', decision.reason);
    }
    for (const entry of cycle.entries.filter(e => !e.current_finding_id)) {
      const prior = await getReviewReport(workspaceId, entry.origin_run_id);
      add('h2', prior.findings.find(f => f.id === entry.origin_finding_id)?.title ?? 'Прежнее замечание');
      add('p', entry.resolution.status === 'resolved' ? 'Исправление подтверждено' : 'Исправление требует подтверждения');
      if (entry.resolution.reason) add('p', entry.resolution.reason);
    }
    const button = doc.createElement('button'); button.textContent = 'Печать / Сохранить PDF'; button.onclick = () => popup.print(); doc.body.append(button);
    popup.focus(); popup.print();
  } catch (error) { popup.close(); throw error; }
}
