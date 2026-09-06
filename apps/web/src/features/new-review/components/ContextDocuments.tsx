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
 * Боковая панель контекста веб-интерфейса v1.
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
    <aside
      id="context-panel"
      data-side-panel
      aria-labelledby="context-documents-title"
      className="fixed inset-x-0 bottom-14 top-13 z-20 flex flex-col border-r border-line bg-surface shadow-[8px_0_24px_rgba(23,32,51,0.08)] sm:static sm:w-80 sm:shrink-0 sm:shadow-none"
    >
      <div className="flex items-start justify-between gap-3 border-b border-line px-4 py-3.5">
        <div>
          <h2 id="context-documents-title" className="text-[15px] font-semibold text-ink">
            Контекстные материалы
          </h2>
          <p className="mt-0.5 text-xs text-ink-subtle">{limitState.used} из {limitState.max}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Свернуть панель контекста"
          className="flex size-8 cursor-pointer items-center justify-center rounded-[5px] border border-transparent text-ink-muted transition-[background-color,color,transform] duration-100 hover:bg-surface-muted hover:text-ink active:scale-[0.96]"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
            <path d="M3 3l8 8M11 3l-8 8" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
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

      <div className="flex items-center justify-end border-t border-line px-4 py-3 sm:hidden">
        <Button onClick={onClose}>Готово</Button>
      </div>
    </aside>
  );
}
