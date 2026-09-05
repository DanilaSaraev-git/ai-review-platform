/**
 * Счётчик разобранных замечаний (US3-6).
 * Показывает ход разбора, при этом текст отчёта остаётся неизменным.
 */
export function DecisionProgress({ reviewed, total }: { reviewed: number; total: number }) {
  return (
    <p className="text-xs text-ink-muted" role="status">
      Разобрано {reviewed} из {total}; осталось {Math.max(0, total - reviewed)}.
    </p>
  );
}
