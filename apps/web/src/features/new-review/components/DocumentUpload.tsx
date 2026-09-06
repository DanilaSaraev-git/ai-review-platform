import { useId, useRef, useState } from 'react';
import { useUploadDocument } from '@/api/generated/endpoints';
import type { Document, PublicLimits } from '@/api/generated/model';
import { isPayloadTooLarge, isProblem } from '@/api/errors';
import { Button, StatusBadge } from '@/components/ui';
import { Icon } from '@/components/ui/Icon';
import { EXTRACTION_STATE_TEXT } from '@/lib/error-messages';
import { formatBytes, formatMediaType } from '@/lib/format';
import { SUPPORTED_EXTENSIONS, validateUpload } from '../lib/validate-upload';

/**
 * Загрузка одного основного документа на проверку (FR-005).
 * Файл проверяется до отправки: неподходящий не доходит до сервиса (FR-006).
 * Документ остаётся неизменяемой версией — интерфейс его не редактирует (FR-007).
 */
export function DocumentUpload({
  workspaceId,
  limits,
  document,
  onUploaded,
  label = 'Файл документа',
  hint = 'PDF, Markdown или TXT.',
}: {
  workspaceId: string;
  limits: PublicLimits;
  document: Document | undefined;
  onUploaded: (uploaded: Document) => void;
  label?: string;
  hint?: string;
}) {
  const [localError, setLocalError] = useState<string | null>(null);
  const id = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const upload = useUploadDocument();

  const serverError = upload.error
    ? isPayloadTooLarge(upload.error)
      ? `Файл больше лимита ${formatBytes(limits.document_upload_max_bytes)}.`
      : isProblem(upload.error)
        ? upload.error.problem.title
        : 'Не удалось загрузить документ.'
    : null;

  async function handleFile(file: File): Promise<void> {
    setLocalError(null);
    const validation = validateUpload({ name: file.name, size: file.size, type: file.type }, limits);
    if (!validation.ok) {
      setLocalError(validation.reason);
      return;
    }
    try {
      const uploaded = await upload.mutateAsync({ workspaceId, data: { file } });
      onUploaded(uploaded);
    } catch {
      // Причина показывается в поле формы из состояния мутации.
    }
  }

  return (
    <div className="entry-upload-field">
      <div className="entry-upload" aria-busy={upload.isPending}>
        <input
          id={id}
          ref={inputRef}
          aria-label={label}
          aria-describedby={`${id}-hint${localError || serverError ? ` ${id}-error` : ''}`}
          type="file"
          accept={SUPPORTED_EXTENSIONS.join(',')}
          className="sr-only"
          disabled={upload.isPending}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) {
              void handleFile(file);
              event.target.value = '';
            }
          }}
        />
        <span className="entry-file-icon"><Icon name="file-text" /></span>
        <div className="entry-upload-copy">
          <p className="entry-upload-title" title={document?.filename}>
            {document?.filename ?? (label === 'Файл документа' ? 'Техническое задание' : 'Контекстный материал')}
          </p>
          <p id={`${id}-hint`} className="entry-upload-hint">
            {document ? `${formatMediaType(document.media_type)} · ${formatBytes(document.size_bytes)}` : hint}
          </p>
          {upload.isPending ? <p role="status" className="entry-upload-hint">Загружаем документ…</p> : null}
          {document ? (
            <StatusBadge
              tone={
                document.extraction_state === 'completed'
                  ? 'ok'
                  : document.extraction_state === 'failed'
                    ? 'danger'
                    : 'warn'
              }
            >
              {EXTRACTION_STATE_TEXT[document.extraction_state]}
            </StatusBadge>
          ) : null}
        </div>
        <Button disabled={upload.isPending} onClick={() => inputRef.current?.click()}>
          {document ? 'Заменить документ' : 'Выбрать документ'}
        </Button>
      </div>
      {localError ?? serverError ? (
        <p id={`${id}-error`} role="alert" className="mt-2 text-xs text-accent">
          {localError ?? serverError}
        </p>
      ) : null}
    </div>
  );
}
