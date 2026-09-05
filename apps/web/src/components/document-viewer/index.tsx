import { useEffect, useState } from 'react';
import { downloadDocument } from '@/api/generated/endpoints';
import type { Document, Finding } from '@/api/generated/model';
import { Button, Callout, Spinner } from '@/components/ui';
import { PdfViewer } from './PdfViewer';
import { TextViewer } from './TextViewer';
import { toDocumentLines } from './sanitize';
import { matchAnchor, type AnchorMatch } from './use-anchor-highlight';

/**
 * Просмотрщик исходного документа с переходом к процитированному фрагменту.
 *
 * Представление выбирается по location.kind привязки, а не по расширению
 * файла (решение R-09). Представление только для чтения: интерфейс не
 * редактирует исходный документ и не создаёт его новую версию (FR-007).
 */
export function DocumentViewer({
  workspaceId,
  document,
  finding,
}: {
  workspaceId: string;
  document: Document | undefined;
  finding: Finding | undefined;
}) {
  const [content, setContent] = useState<string | null>(null);
  const [blob, setBlob] = useState<Blob | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const isPdf = document?.media_type === 'application/pdf';

  useEffect(() => {
    if (!workspaceId || !document) {
      return;
    }
    let cancelled = false;

    async function load(): Promise<void> {
      setError(null);
      try {
        const payload = (await downloadDocument(workspaceId, document!.id)) as unknown;
        if (cancelled) {
          return;
        }
        if (typeof payload === 'string') {
          setContent(payload);
        } else if (payload instanceof Blob) {
          if (isPdf) {
            setBlob(payload);
          } else {
            setContent(await payload.text());
          }
        }
      } catch {
        if (!cancelled) {
          setError('Не удалось загрузить исходный документ.');
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [workspaceId, document, isPdf, reloadKey]);

  const lines = content ? toDocumentLines(content) : [];
  const match: AnchorMatch | null = finding ? matchAnchor(finding, lines) : null;

  return (
    <section aria-labelledby="document-viewer-title" className="mx-auto flex h-full w-full max-w-4xl flex-col gap-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="document-viewer-title" className="text-[13px] font-semibold text-ink">Исходный документ</h2>
        {document ? (
          <p className="max-w-full truncate text-xs text-ink-subtle" title={document.filename}>{document.filename}</p>
        ) : null}
      </div>

      {/* Несопоставленный фрагмент называется прямо: произвольное место
          документа не подсвечивается (SC-003). */}
      {match && !match.matched ? (
        <Callout tone="warn" title={match.kind === 'no-anchor' ? 'Замечание без цитаты' : 'Фрагмент не сопоставлен'}>
          <p>{match.reason}</p>
          {match.kind === 'no-anchor' && match.scope.length > 0 ? (
            <p className="mt-1">Проверенная область: {match.scope.join(', ')}</p>
          ) : null}
        </Callout>
      ) : null}

      {error ? (
        <Callout tone="danger" title={error}>
          <Button className="mt-2" onClick={() => setReloadKey((current) => current + 1)}>Повторить</Button>
        </Callout>
      ) : null}

      {error ? null : isPdf ? (
        <PdfViewer source={blob} match={match} />
      ) : content !== null ? (
        <TextViewer content={content} match={match} />
      ) : (
        <Spinner label="Загружаем документ…" />
      )}
    </section>
  );
}

export { matchAnchor } from './use-anchor-highlight';
