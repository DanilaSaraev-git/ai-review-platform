/**
 * Счётчик разобранных замечаний (US3-6).
 * Показывает ход разбора, при этом текст отчёта остаётся неизменным.
 */
export function DecisionProgress({ reviewed, total }: { reviewed: number; total: number }) {
  const complete = total > 0 && reviewed === total;
  return (
    <span role="status">
      <StatusBadge tone={complete ? 'ok' : 'warn'}>
        {complete ? `Разбор завершён · ${reviewed} из ${total}` : `Есть замечания · разобрано ${reviewed} из ${total}`}
      </StatusBadge>
    </span>
  );
}
import { StatusBadge } from '@/components/ui';
