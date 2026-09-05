import { useEffect, useState } from 'react';
import type { HumanDecision } from '@/api/generated/model';
import { isProblem, isRevisionConflict } from '@/api/errors';
import { Button, Callout, Field, RadioCards, TextArea } from '@/components/ui';
import { DECISION_STATUS_TEXT } from '@/lib/error-messages';
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
  prefilledResolution,
}: {
  workspaceId: string;
  runId: string;
  findingId: string;
  decision: HumanDecision | undefined;
  prefilledResolution?: string | null;
}) {
  const [values, setValues] = useState<DecisionFormValues>(() => toFormValues(decision));
  const [validationError, setValidationError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const { save, isPending, error, reset } = usePutDecision(workspaceId, runId, findingId);
  const conflict = decisionConflictState(error);

  // Перенос предложенной резолюции — отдельное действие аналитика: текст лишь
  // подставляется в поле, сохранение остаётся вторым шагом (FR-029).
  useEffect(() => {
    if (prefilledResolution) {
      setValues((current) => ({ ...current, resolution: prefilledResolution }));
    }
  }, [prefilledResolution]);

  async function submit(): Promise<void> {
    const parsed = decisionSchema.safeParse(values);
    if (!parsed.success) {
      setValidationError(REASON_REQUIRED_MESSAGE);
      return;
    }
    setValidationError(null);
    reset();
    const body = toPutFindingDecision(values, decision?.revision ?? 0);
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
    <section aria-labelledby="decision-title" className="flex flex-col gap-3 rounded border border-line bg-surface p-4">
      <h2 id="decision-title" className="text-sm font-semibold text-ink">
        Ваше решение
      </h2>

      <RadioCards
        legend="Статус замечания"
        name="decision-status"
        value={values.status}
        onValueChange={(next) => setValues((current) => ({ ...current, status: next as DecisionFormValues['status'] }))}
        options={[
          { value: 'confirmed', label: DECISION_STATUS_TEXT.confirmed, description: 'Замечание принято в работу.' },
          { value: 'rejected', label: DECISION_STATUS_TEXT.rejected, description: 'Замечание не относится к делу.' },
          {
            value: 'needs_context',
            label: DECISION_STATUS_TEXT.needs_context,
            description: 'Нужны дополнительные материалы, чтобы решить.',
          },
          {
            value: 'unreviewed',
            label: DECISION_STATUS_TEXT.unreviewed,
            description: 'Вернуть замечание в работу: обоснование и резолюция будут очищены.',
          },
        ]}
      />

      <Field
        label="Обоснование"
        hint={values.status === 'unreviewed' ? 'При сбросе обоснование очищается.' : 'Обязательно для сохранения.'}
        error={validationError}
      >
        {(id, describedBy) => (
          <TextArea
            id={id}
            aria-describedby={describedBy}
            value={values.reason}
            disabled={values.status === 'unreviewed'}
            onChange={(event) => setValues((current) => ({ ...current, reason: event.target.value }))}
          />
        )}
      </Field>

      <Field label="Формулировка резолюции" hint="Необязательно: как именно поправить ТЗ.">
        {(id, describedBy) => (
          <TextArea
            id={id}
            aria-describedby={describedBy}
            value={values.resolution}
            disabled={values.status === 'unreviewed'}
            onChange={(event) => setValues((current) => ({ ...current, resolution: event.target.value }))}
          />
        )}
      </Field>

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

      {savedAt && !conflict.isConflict ? <Callout tone="ok" title="Решение сохранено" /> : null}

      <div>
        <Button variant="primary" disabled={isPending} onClick={() => void submit()}>
          {isPending ? 'Сохраняем…' : 'Сохранить решение'}
        </Button>
      </div>
    </section>
  );
}
