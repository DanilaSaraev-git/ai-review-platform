import { useRef, useState } from 'react';
import { useUploadDocument } from '@/api/generated/endpoints';
import type { Document, PublicLimits } from '@/api/generated/model';
import { isPayloadTooLarge, isProblem } from '@/api/errors';
import { Button, Callout, Field, StatusBadge } from '@/components/ui';
import { EXTRACTION_STATE_TEXT } from '@/lib/error-messages';
import { formatBytes, formatMediaType } from '@/lib/format';
import { SUPPORTED_EXTENSIONS, SUPPORTED_FORMATS_TEXT, validateUpload } from '../lib/validate-upload';

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
  hint = 'Один документ — один запуск. Исходный файл остаётся без изменений.',
}: {
  workspaceId: string;
  limits: PublicLimits;
  document: Document | undefined;
  onUploaded: (uploaded: Document) => void;
  label?: string;
  hint?: string;
}) {
  const [localError, setLocalError] = useState<string | null>(null);
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
    <div className="flex flex-col gap-3">
      <Field label={label} hint={hint} error={localError ?? serverError}>
        {(id, describedBy) => (
          <input
            id={id}
            ref={inputRef}
            aria-describedby={describedBy}
            type="file"
            accept={SUPPORTED_EXTENSIONS.join(',')}
            className="text-sm text-ink file:mr-3 file:cursor-pointer file:rounded file:border file:border-line file:bg-surface file:px-3 file:py-1.5 file:text-sm file:transition hover:file:bg-surface-muted"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) {
                void handleFile(file);
              }
            }}
          />
        )}
      </Field>

      <p className="text-xs text-ink-muted">Поддерживаются {SUPPORTED_FORMATS_TEXT}.</p>

      {upload.isPending ? <Callout title="Загружаем документ…" tone="progress" /> : null}

      {document ? (
        <div className="rounded border border-line bg-surface p-3">
          <p className="text-sm font-medium text-ink">{document.filename}</p>
          <p className="mt-1 text-xs text-ink-muted">
            {formatMediaType(document.media_type)} · {formatBytes(document.size_bytes)}
          </p>
          <div className="mt-2">
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
          </div>
          <Button
            className="mt-3"
            onClick={() => {
              inputRef.current?.click();
            }}
          >
            Заменить документ
          </Button>
        </div>
      ) : null}
    </div>
  );
}
