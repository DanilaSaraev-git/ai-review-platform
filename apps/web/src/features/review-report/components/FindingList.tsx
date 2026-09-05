import type { Finding, FindingState } from '@/api/generated/model';
import { Callout } from '@/components/ui';
import { FindingCard } from './FindingCard';

/**
 * Список замечаний в устойчивом порядке ordinal (FR-019).
 *
 * Порядок задан отчётом и не зависит от решений и диалога. Пустой список —
 * содержательный результат, а не ошибка и не пустой экран (FR-023).
 */
export function FindingList({
  findings,
  states,
  runId,
  selectedFindingId,
}: {
  findings: readonly Finding[];
  states: Map<string, FindingState>;
  runId: string;
  selectedFindingId?: string;
}) {
  if (findings.length === 0) {
    return (
      <Callout tone="ok" title="Замечаний не найдено">
        Проверка завершилась без замечаний. Обратите внимание на охват проверки и ограничения результата ниже: они
        показывают, что именно было рассмотрено.
      </Callout>
    );
  }

  const ordered = [...findings].sort((left, right) => left.ordinal - right.ordinal);

  return (
    <ul className="flex flex-col gap-3">
      {ordered.map((finding) => (
        <li key={finding.id}>
          <FindingCard
            finding={finding}
            state={states.get(finding.id)}
            runId={runId}
            isSelected={finding.id === selectedFindingId}
          />
        </li>
      ))}
    </ul>
  );
}
