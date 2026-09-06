import type { CycleEntry, HumanDecision } from '@/api/generated/model';

/** A reset is an explicit decision too. Only untouched current state may inherit. */
export function effectiveDecision(current: HumanDecision, entry: CycleEntry | undefined): HumanDecision {
  return current.revision === 0 && entry?.decision_carried && entry.previous_decision
    ? entry.previous_decision
    : current;
}
