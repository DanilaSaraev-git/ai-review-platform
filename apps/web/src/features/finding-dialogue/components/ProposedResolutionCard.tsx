import type { ProposedResolution } from '@/api/generated/model';
import { Button } from '@/components/ui';
import { TRANSFER_HINT, TRANSFER_LABEL } from '../lib/apply-proposed-resolution';
import { isDemoMode } from '@/app/demo-mode';

/**
 * Предложенная моделью резолюция (FR-029, SC-007).
 *
 * Показывается отдельно от решения и решением не является: пока аналитик не
 * перенесёт текст и не сохранит решение, замечание остаётся «не рассмотрено».
 */
export function ProposedResolutionCard({
  proposal,
  onUse,
}: {
  proposal: ProposedResolution;
  onUse?: (text: string) => void;
}) {
  return (
    <div className="rounded-lg bg-surface-muted p-4">
      <h4 className="text-xs font-medium text-ink">{isDemoMode ? 'Подготовленная формулировка' : 'Предложенная моделью формулировка'}</h4>
      <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-ink">{proposal.text}</p>
      <p className="mt-2 whitespace-pre-wrap break-words text-xs leading-5 text-ink-muted">{proposal.rationale}</p>
      <p className="mt-3 text-xs leading-5 text-ink-muted">{TRANSFER_HINT}</p>
      {onUse ? (
        <Button className="mt-3" onClick={() => onUse(proposal.text)}>
          {TRANSFER_LABEL}
        </Button>
      ) : null}
    </div>
  );
}
