import { useRef, useState } from 'react';
import { useUploadDocument } from '@/api/generated/endpoints';
import type { Document, PublicLimits } from '@/api/generated/model';
import { isPayloadTooLarge, isProblem } from '@/api/errors';
import { Button, Callout, Field, StatusBadge } from '@/components/ui';
import { EXTRACTION_STATE_TEXT } from '@/lib/error-messages';
import { formatBytes, formatMediaType } from '@/lib/format';
import { SUPPORTED_EXTENSIONS, SUPPORTED_FORMATS_TEXT, validateUpload } from '../lib/validate-upload';
import { isDemoMode } from '@/app/demo-mode';

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
  const [selectedFilename, setSelectedFilename] = useState<string | null>(null);
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
      // Demo only uses the selection as a trigger. The file bytes stay in the browser.
      const uploadFile = isDemoMode ? new File([], file.name, { type: file.type }) : file;
      const uploaded = await upload.mutateAsync({ workspaceId, data: { file: uploadFile } });
      setSelectedFilename(file.name);
      onUploaded(uploaded);
    } catch {
      // Причина показывается в поле формы из состояния мутации.
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <Field label={label} hint={hint} error={localError ?? serverError}>
        {(id, describedBy) => (
          <div>
            <input
              id={id}
              ref={inputRef}
              aria-describedby={describedBy}
              type="file"
              accept={SUPPORTED_EXTENSIONS.join(',')}
              className="sr-only"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) {
                  void handleFile(file);
                }
              }}
            />
            {!document ? (
              <label
                htmlFor={id}
                className="inline-flex min-h-9 cursor-pointer items-center rounded-[5px] border border-line-strong bg-surface px-3 py-1.5 text-[13px] font-semibold text-ink shadow-sm transition-[background-color,border-color,transform] duration-100 hover:border-ink-subtle hover:bg-surface-muted active:scale-[0.96]"
              >
                Выбрать документ
              </label>
            ) : null}
          </div>
        )}
      </Field>

      {hint !== 'PDF, Markdown или TXT.' ? (
        <p className="text-xs text-ink-muted">Поддерживаются {SUPPORTED_FORMATS_TEXT}.</p>
      ) : null}

      {upload.isPending ? <Callout title="Загружаем документ…" tone="progress" /> : null}

      {isDemoMode && selectedFilename ? (
        <p className="text-xs leading-relaxed text-ink-muted">
          Выбран файл «{selectedFilename}». Он запускает демосценарий; его содержимое не отправляется и не анализируется.
          Ниже — документ подготовленного примера.
        </p>
      ) : null}

      {document ? (
        <div className="flex flex-wrap items-center gap-3 rounded-[5px] border border-line bg-surface-muted p-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-semibold text-ink" title={document.filename}>{document.filename}</p>
            <p className="mt-0.5 text-xs text-ink-muted">
              {formatMediaType(document.media_type)} · {formatBytes(document.size_bytes)}
            </p>
          </div>
          <div>
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
            className="min-h-8"
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
