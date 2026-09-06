import { useEffect, useMemo, useState } from 'react';
import { downloadDocument } from '@/api/generated/endpoints';
import type { Document, Finding } from '@/api/generated/model';
import { Button, Callout, Spinner } from '@/components/ui';
import { PdfViewer } from './PdfViewer';
import { TextViewer } from './TextViewer';
import { toDocumentLines } from './sanitize';
import { matchAnchor, type AnchorMatch } from './use-anchor-highlight';
import '@/styles/review-workspace.css';

/**
 * Просмотрщик исходного документа с переходом к процитированному фрагменту.
 *
 * Представление выбирается по media_type неизменяемого основного документа.
 * Привязка к источнику контекста не подменяет основной документ. Интерфейс не
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
  const documentId = document?.id;

  useEffect(() => {
    if (!workspaceId || !documentId) {
      return;
    }
    let cancelled = false;

    async function load(): Promise<void> {
      setError(null);
      try {
        const payload = (await downloadDocument(workspaceId, documentId!)) as unknown;
        if (cancelled) {
          return;
        }
        if (typeof payload === 'string') {
          setContent(payload);
        } else if (payload instanceof Blob) {
          if (isPdf) {
            setBlob(payload);
          } else {
            const text = await payload.text();
            if (!cancelled) setContent(text);
          }
        } else {
          throw new Error('Unsupported document response');
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
  }, [workspaceId, documentId, isPdf, reloadKey]);

  const lines = useMemo(() => content ? toDocumentLines(content) : [], [content]);
  const primaryAnchors = finding?.anchors.filter((anchor) => anchor.document_id === documentId);
  const isContextAnchor = Boolean(finding?.anchors.length && !primaryAnchors?.length);
  const match: AnchorMatch | null = useMemo(() => {
    if (!finding || isContextAnchor || (!isPdf && content === null)) return null;
    return matchAnchor({ ...finding, anchors: finding.anchors.filter((anchor) => anchor.document_id === documentId) }, lines);
  }, [finding, documentId, isContextAnchor, lines, isPdf, content]);

  return (
    <section aria-labelledby="document-viewer-title" className="numbat-document-viewer">
      <div className="numbat-document-header">
        <h2 id="document-viewer-title">Исходный документ</h2>
        <span>{isPdf ? 'PDF' : document?.media_type === 'text/markdown' ? 'Markdown' : 'Текст'}</span>
      </div>

      {isContextAnchor ? <Callout tone="neutral" title="Цитата из источника контекста">
        Основной документ остаётся открыт. Цитата показана в замечании.
      </Callout> : null}

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
