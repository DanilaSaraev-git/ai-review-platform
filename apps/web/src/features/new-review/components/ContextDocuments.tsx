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
      className="flex w-90 shrink-0 flex-col bg-surface"
    >
      <div className="flex items-start justify-between gap-3 px-5 py-4">
        <div>
          <h2 id="context-documents-title" className="text-lg font-bold text-ink">
            Контекстные материалы
          </h2>
          <p className="mt-0.5 text-xs text-ink-subtle">Материалы, доступные агенту</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Свернуть панель контекста"
          className="flex size-8 cursor-pointer items-center justify-center rounded border border-line text-ink-muted hover:bg-surface-muted"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
            <path d="M3 3l8 8M11 3l-8 8" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 pb-4">
        <p className="text-xs text-ink-muted">
          Правила команды, модель данных, регламент. Подключено {limitState.used} из {limitState.max}; можно добавить
          ещё {limitState.remaining}.
        </p>

        {documents.length > 0 ? (
          <ul className="mt-4 flex flex-col gap-2">
            {documents.map((document) => (
              <li key={document.id} className="rounded border border-line bg-surface-muted p-3">
                <p className="text-sm font-medium text-ink">{document.filename}</p>
                <p className="mt-0.5 text-xs text-ink-subtle">
                  {formatMediaType(document.media_type)} · {formatBytes(document.size_bytes)} ·{' '}
                  {EXTRACTION_STATE_TEXT[document.extraction_state]}
                </p>
                <Button variant="ghost" className="mt-2" onClick={() => onDetach(document.id)}>
                  Отключить
                </Button>
              </li>
            ))}
          </ul>
        ) : null}

        <div className="mt-4">
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
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-line px-5 py-3">
        <p className="text-sm text-ink-muted">Подключено: {limitState.used}</p>
        <Button onClick={onClose}>Закрыть</Button>
      </div>
    </aside>
  );
}
