import type { Document, PublicLimits } from '@/api/generated/model';
import { Button, Callout } from '@/components/ui';
import { Icon } from '@/components/ui/Icon';
import { EXTRACTION_STATE_TEXT } from '@/lib/error-messages';
import { formatBytes, formatMediaType } from '@/lib/format';
import { contextLimitState } from '../lib/context-limit';
import { DocumentUpload } from './DocumentUpload';

/**
 * Контекстные материалы запуска (FR-008, US5-1, US5-2).
 *
 * Показываются отдельно от основного документа; интерфейс называет остаток
 * лимита и отказывает в подключении сверх него, называя действующее значение.
 * Встроены в параметры запуска, не замещая основной документ.
 */
export function ContextDocuments({
  workspaceId,
  limits,
  documents,
  onAttach,
  onDetach,
  onClose,
}: {
  workspaceId: string;
  limits: PublicLimits;
  documents: readonly Document[];
  onAttach: (document: Document) => void;
  onDetach: (documentId: string) => void;
  onClose: () => void;
}) {
  const limitState = contextLimitState(documents.length, limits);

  return (
    <section
      id="context-panel"
      aria-labelledby="context-documents-title"
      className="entry-context"
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h3 id="context-documents-title" className="text-[13px] font-medium text-ink">
            Контекстные материалы
          </h3>
          <p className="mt-0.5 text-xs text-ink-subtle">{limitState.used} из {limitState.max}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Свернуть панель контекста"
          className="flex size-8 cursor-pointer items-center justify-center rounded-[5px] border border-transparent text-ink-muted transition-[background-color,color,transform] duration-100 hover:bg-surface-muted hover:text-ink active:scale-[0.96]"
        >
          <Icon name="x" />
        </button>
      </div>

      <div>
        {documents.length > 0 ? (
          <ul className="mb-4 flex flex-col gap-2">
            {documents.map((document) => (
              <li key={document.id} className="rounded-[5px] border border-line bg-surface-muted p-3">
                <p className="overflow-wrap-anywhere text-[13px] font-semibold text-ink">{document.filename}</p>
                <p className="mt-0.5 text-xs text-ink-subtle">
                  {formatMediaType(document.media_type)} · {formatBytes(document.size_bytes)} ·{' '}
                  {EXTRACTION_STATE_TEXT[document.extraction_state]}
                </p>
                <Button variant="ghost" className="mt-1.5 min-h-7 px-2 py-0.5 text-xs" onClick={() => onDetach(document.id)}>
                  Отключить
                </Button>
              </li>
            ))}
          </ul>
        ) : null}

        <div>
          {limitState.canAttachMore ? (
            <DocumentUpload
              workspaceId={workspaceId}
              limits={limits}
              document={undefined}
              onUploaded={onAttach}
              label="Файл контекстного материала"
              hint="Правила, шаблон или описание данных."
            />
          ) : (
            <Callout tone="warn" title="Лимит контекстных материалов достигнут">
              {limitState.limitReachedReason}
            </Callout>
          )}
        </div>
      </div>

    </section>
  );
}
