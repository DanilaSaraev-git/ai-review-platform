import type { ProposedResolution } from '@/api/generated/model';
import { Button } from '@/components/ui';
import { TRANSFER_HINT, TRANSFER_LABEL } from '../lib/apply-proposed-resolution';

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
    <div className="rounded border border-line bg-surface-muted p-3">
      <h4 className="text-xs font-semibold text-ink">Предложенная моделью формулировка</h4>
      <p className="mt-1 text-sm text-ink">{proposal.text}</p>
      <p className="mt-1 text-xs text-ink-muted">{proposal.rationale}</p>
      <p className="mt-2 text-xs text-ink-muted">{TRANSFER_HINT}</p>
      {onUse ? (
        <Button className="mt-2" onClick={() => onUse(proposal.text)}>
          {TRANSFER_LABEL}
        </Button>
      ) : null}
    </div>
  );
}
