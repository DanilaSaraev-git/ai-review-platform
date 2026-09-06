import { StatusBadge } from '@/components/ui';

/**
 * Счётчик разобранных замечаний (US3-6).
 * Показывает ход разбора, при этом текст отчёта остаётся неизменным.
 */
export function DecisionProgress({ reviewed, total }: { reviewed: number; total: number }) {
  return (
    <span role="status" className="tabular-nums">
      <StatusBadge>
        Рассмотрено {reviewed} из {total}
      </StatusBadge>
    </span>
  );
}
