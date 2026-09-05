import type { Document, PublicLimits } from '@/api/generated/model';
import { Button, Callout } from '@/components/ui';
import { EXTRACTION_STATE_TEXT } from '@/lib/error-messages';
import { formatBytes, formatMediaType } from '@/lib/format';
import { contextLimitState } from '../lib/context-limit';
import { DocumentUpload } from './DocumentUpload';

/**
 * Контекстные материалы запуска (FR-008, US5-1, US5-2).
 *
 * Показываются отдельно от основного документа; интерфейс называет остаток
 * лимита и отказывает в подключении сверх него, называя действующее значение.
 */
export function ContextDocuments({
  workspaceId,
  limits,
  documents,
  onAttach,
  onDetach,
}: {
  workspaceId: string;
  limits: PublicLimits;
  documents: readonly Document[];
  onAttach: (document: Document) => void;
  onDetach: (documentId: string) => void;
}) {
  const limitState = contextLimitState(documents.length, limits);

  return (
    <section aria-labelledby="context-documents-title" className="rounded border border-line bg-surface p-4">
      <h2 id="context-documents-title" className="text-sm font-semibold text-ink">
        Контекстные материалы
      </h2>
      <p className="mt-1 text-xs text-ink-muted">
        Правила команды, модель данных, регламент. Подключено {limitState.used} из {limitState.max}; можно добавить ещё{' '}
        {limitState.remaining}.
      </p>

      {documents.length > 0 ? (
        <ul className="mt-3 flex flex-col gap-2">
          {documents.map((document) => (
            <li
              key={document.id}
              className="flex items-center justify-between gap-3 rounded border border-line px-3 py-2"
            >
              <span className="text-sm text-ink">
                {document.filename}
                <span className="block text-xs text-ink-muted">
                  {formatMediaType(document.media_type)} · {formatBytes(document.size_bytes)} ·{' '}
                  {EXTRACTION_STATE_TEXT[document.extraction_state]}
                </span>
              </span>
              <Button variant="ghost" onClick={() => onDetach(document.id)}>
                Отключить
              </Button>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="mt-3">
        {limitState.canAttachMore ? (
          <DocumentUpload
            workspaceId={workspaceId}
            limits={limits}
            document={undefined}
            onUploaded={onAttach}
            label="Файл контекстного материала"
            hint="Материал попадёт в проверку как дополнительный источник, а не как проверяемый документ."
          />
        ) : (
          <Callout tone="warn" title="Лимит контекстных материалов достигнут">
            {limitState.limitReachedReason}
          </Callout>
        )}
      </div>
    </section>
  );
}
