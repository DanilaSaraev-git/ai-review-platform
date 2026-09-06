import { Link } from 'react-router';
import { useEffect, useState } from 'react';
import type { HumanDecision } from '@/api/generated/model';
import { isProblem, isRevisionConflict } from '@/api/errors';
import { Button, Callout, Field, RadioCards, TextArea } from '@/components/ui';
import { DECISION_STATUS_TEXT } from '@/lib/error-messages';
import { formatDateTime } from '@/lib/format';
import { usePutDecision } from '../api/use-put-decision';
import { decisionConflictState } from '../lib/conflict';
import {
  REASON_REQUIRED_MESSAGE,
  decisionSchema,
  toFormValues,
  toPutFindingDecision,
  type DecisionFormValues,
} from '../lib/decision-schema';
import { RevisionConflictNotice } from './RevisionConflictNotice';

/**
 * Форма решения человека (FR-024 — FR-027).
 *
 * Введённый текст живёт в состоянии формы и не сбрасывается при конфликте
 * ревизии: перезагрузка актуального решения не трогает поля, поэтому повтор
 * не требует вводить обоснование заново (SC-005).
 */
export function DecisionForm({
  workspaceId,
  runId,
  findingId,
  decision,
  expectedRevision,
  prefilledResolution,
  nextHref,
  nextLabel = 'Следующее замечание',
}: {
  workspaceId: string;
  runId: string;
  findingId: string;
  decision: HumanDecision | undefined;
  expectedRevision?: number;
  prefilledResolution?: string | null;
  nextHref?: string;
  nextLabel?: string;
}) {
  const [values, setValues] = useState<DecisionFormValues>(() => toFormValues(decision));
  const [hasLocalEdits, setHasLocalEdits] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const { save, isPending, error, reset } = usePutDecision(workspaceId, runId, findingId);
  const conflict = decisionConflictState(error);

  // Перенос предложенной резолюции — отдельное действие аналитика: текст лишь
  // подставляется в поле, сохранение остаётся вторым шагом (FR-029).
  useEffect(() => {
    if (prefilledResolution) {
      setHasLocalEdits(true);
      setSavedAt(null);
      setValues((current) => ({ ...current, resolution: prefilledResolution }));
    }
  }, [prefilledResolution]);

  // Состояние замечания часто приходит после отчёта. До первого ввода форма
  // принимает серверное решение; после ввода обновления ревизии не стирают draft.
  useEffect(() => {
    if (!hasLocalEdits && decision) {
      setValues(toFormValues(decision));
    }
  }, [decision, hasLocalEdits]);

  async function submit(nextValues: DecisionFormValues = values): Promise<void> {
    const parsed = decisionSchema.safeParse(nextValues);
    if (!parsed.success) {
      setValidationError(REASON_REQUIRED_MESSAGE);
      return;
    }
    setValidationError(null);
    reset();
    const body = toPutFindingDecision(nextValues, expectedRevision ?? decision?.revision ?? 0);
    try {
      const result = await save(body);
      setValues(toFormValues(result));
      setSavedAt(result.decided_at);
    } catch {
      // Ошибка уже отражена в состоянии мутации: конфликт ревизии показывается
      // отдельным блоком, остальные — сообщением. Повторный выброс здесь
      // оставил бы необработанное отклонение промиса.
    }
  }

  const otherError = error && !isRevisionConflict(error) ? error : null;

  return (
    <section aria-labelledby="decision-title" className="flex min-w-0 flex-col gap-4 border-b border-line bg-surface p-5">
      <h2 id="decision-title" className="text-sm font-medium text-ink">
        Ваше решение
      </h2>

      <RadioCards
        legend="Статус замечания"
        name="decision-status"
        compact
        value={values.status}
        onValueChange={(next) => {
          setHasLocalEdits(true);
          setSavedAt(null);
          setValues((current) => ({ ...current, status: next as DecisionFormValues['status'] }));
        }}
        options={[
          { value: 'confirmed', label: DECISION_STATUS_TEXT.confirmed },
          { value: 'rejected', label: DECISION_STATUS_TEXT.rejected },
          {
            value: 'needs_context',
            label: DECISION_STATUS_TEXT.needs_context,
          },
        ]}
      />

      {values.status !== 'unreviewed' || (values.resolution?.trim().length ?? 0) > 0 ? (
        <>
          <Field label="Обоснование" hint="Обязательно для сохранения." error={validationError}>
            {(id, describedBy) => (
              <TextArea
                id={id}
                aria-describedby={describedBy}
                rows={3}
                value={values.reason}
                onChange={(event) => {
                  setHasLocalEdits(true);
                  setSavedAt(null);
                  setValues((current) => ({ ...current, reason: event.target.value }));
                }}
              />
            )}
          </Field>


        </>
      ) : null}

      <RevisionConflictNotice
        conflict={conflict}
        current={decision}
        onRetry={() => void submit()}
        isRetrying={isPending}
      />

      {otherError ? (
        <Callout tone="danger" title="Решение не сохранено">
          {isProblem(otherError) ? otherError.problem.title : 'Повторите попытку.'}
        </Callout>
      ) : null}

      {savedAt && !conflict.isConflict ? <div className="flex flex-wrap items-center gap-3"><p role="status" className="text-xs font-medium text-ok">✓ Решение сохранено</p>{nextHref ? <Link className="review-primary-link" to={nextHref}>{nextLabel} →</Link> : null}</div> : null}

      <div className="sticky bottom-0 flex flex-wrap items-center gap-2 border-t border-line bg-surface pt-4 pb-1">
        {values.status !== 'unreviewed' ? (
          <Button variant="primary" disabled={isPending} onClick={() => void submit()}>
            {isPending ? 'Сохраняем…' : 'Сохранить решение'}
          </Button>
        ) : null}
        {decision && decision.status !== 'unreviewed' ? (
          <Button
            variant="ghost"
            disabled={isPending}
            onClick={() => {
              const cleared: DecisionFormValues = { status: 'unreviewed', reason: '', resolution: '' };
              setHasLocalEdits(true);
              setSavedAt(null);
              setValues(cleared);
              void submit(cleared);
            }}
          >
            Сбросить решение
          </Button>
        ) : null}
        {decision?.actor ? (
          <span className="basis-full break-words text-xs leading-5 text-ink-subtle">{decision.actor.display_name} · {formatDateTime(decision.decided_at)}</span>
        ) : null}
      </div>
    </section>
  );
}
