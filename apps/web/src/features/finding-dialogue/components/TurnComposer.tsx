import { useState } from 'react';
import { useQueries } from '@tanstack/react-query';
import { getGetDocumentQueryOptions } from '@/api/generated/endpoints';
import { DialogueAttachments } from './DialogueAttachments';
import type { Document, FindingDialogue } from '@/api/generated/model';
import { isProblem, isRevisionConflict } from '@/api/errors';
import { Button, Callout, Field, TextArea } from '@/components/ui';
import { blockedReasonText } from '@/lib/error-messages';
import { dialogueConflictState } from '../lib/conflict';
import { useCreateTurn } from '../api/use-create-turn';
import { DEMO_REPLY_NOTICE, isDemoMode } from '@/app/demo-mode';

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
  const [attachments, setAttachments] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const documents = useQueries({ queries: attachments.map(d => getGetDocumentQueryOptions(workspaceId, d.id, { query: { refetchInterval: q => q.state.data?.extraction_state === 'pending' ? 1000 : false } })) });
  const attachmentsReady = !uploading && documents.every(q => q.data && ['completed', 'partial'].includes(q.data.extraction_state));
  const { send, isPending, error, reset } = useCreateTurn(workspaceId, runId, findingId);
  const conflict = dialogueConflictState(error);
  const blocked = blockedReasonText(dialogue.blocked_reason);
  const canSend = dialogue.can_send_message && (message.trim().length > 0 || attachments.length > 0) && !isPending && attachmentsReady;

  async function submit(): Promise<void> {
    if (!canSend) {
      return;
    }
    reset();
    try {
      await send(message.trim() || 'Прикреплены материалы для уточнения замечания.', dialogue.revision, attachments.map(d => d.id));
      setAttachments([]);
      setMessage('');
    } catch {
      // Состояние ошибки хранит мутация; введённый вопрос намеренно остаётся
      // в поле, чтобы повтор не требовал набирать его заново (SC-005).
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <Field label="Ответ или уточняющий вопрос по замечанию" hint={isDemoMode ? DEMO_REPLY_NOTICE : undefined}>
        {(id, describedBy) => (
          <TextArea
            id={id}
            aria-describedby={describedBy}
            rows={3}
            placeholder="Введите сообщение…"
            value={message}
            disabled={!dialogue.can_send_message}
            onChange={(event) => setMessage(event.target.value)}
          />
        )}
      </Field>

      <DialogueAttachments workspaceId={workspaceId} documents={attachments} onChange={setAttachments} onBusy={setUploading} disabled={!dialogue.can_send_message || isPending} />
      {!attachmentsReady && attachments.length > 0 ? <p className="text-xs text-ink-muted">Дождитесь извлечения текста. Если обработка не удалась, удалите файл и выберите другой.</p> : null}
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

      <div className="flex justify-end">
        <Button variant="primary" disabled={!canSend} onClick={() => void submit()}>
          {isPending ? 'Отправляем…' : 'Отправить'}
        </Button>
      </div>
    </div>
  );
}
