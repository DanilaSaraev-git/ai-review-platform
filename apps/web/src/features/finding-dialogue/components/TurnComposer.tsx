import { useState } from 'react';
import type { FindingDialogue } from '@/api/generated/model';
import { isProblem, isRevisionConflict } from '@/api/errors';
import { Button, Callout, Field, TextArea } from '@/components/ui';
import { blockedReasonText } from '@/lib/error-messages';
import { dialogueConflictState } from '../lib/conflict';
import { useCreateTurn } from '../api/use-create-turn';

/**
 * Отправка одного хода (FR-031, FR-032, FR-036).
 *
 * Доступность берётся строго из серверного can_send_message: клиент её не
 * вычисляет. Неактивная кнопка всегда сопровождается причиной из
 * blocked_reason — молчаливо отключённого элемента управления быть не должно.
 *
 * При конфликте ревизии введённый вопрос остаётся в поле, и повтор доступен
 * одним действием (SC-005).
 */
export function TurnComposer({
  workspaceId,
  runId,
  findingId,
  dialogue,
}: {
  workspaceId: string;
  runId: string;
  findingId: string;
  dialogue: FindingDialogue;
}) {
  const [message, setMessage] = useState('');
  const { send, isPending, error, reset } = useCreateTurn(workspaceId, runId, findingId);
  const conflict = dialogueConflictState(error);
  const blocked = blockedReasonText(dialogue.blocked_reason);
  const canSend = dialogue.can_send_message && message.trim().length > 0 && !isPending;

  async function submit(): Promise<void> {
    if (message.trim().length === 0) {
      return;
    }
    reset();
    try {
      await send(message.trim(), dialogue.revision);
      setMessage('');
    } catch {
      // Состояние ошибки хранит мутация; введённый вопрос намеренно остаётся
      // в поле, чтобы повтор не требовал набирать его заново (SC-005).
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <Field label="Уточняющий вопрос по замечанию" hint="Один вопрос за раз: следующий станет доступен после ответа.">
        {(id, describedBy) => (
          <TextArea
            id={id}
            aria-describedby={describedBy}
            value={message}
            disabled={!dialogue.can_send_message}
            onChange={(event) => setMessage(event.target.value)}
          />
        )}
      </Field>

      {/* Причина недоступности называется всегда (FR-032). */}
      {!dialogue.can_send_message && blocked ? <Callout tone="warn" title="Отправка недоступна">{blocked}</Callout> : null}

      {conflict.isConflict ? (
        <div role="alert">
          <Callout tone="warn" title={conflict.title}>
            <p>{conflict.hint}</p>
            <Button className="mt-2" onClick={() => void submit()} disabled={isPending}>
              Повторить отправку
            </Button>
          </Callout>
        </div>
      ) : null}

      {error && !isRevisionConflict(error) ? (
        <Callout tone="danger" title="Ход не отправлен">
          {isProblem(error) ? error.problem.title : 'Повторите попытку.'}
        </Callout>
      ) : null}

      <div>
        <Button variant="primary" disabled={!canSend} onClick={() => void submit()}>
          {isPending ? 'Отправляем…' : 'Отправить вопрос'}
        </Button>
      </div>
    </div>
  );
}
