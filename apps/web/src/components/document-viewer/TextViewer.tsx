import { useEffect, useRef } from 'react';
import { toDocumentLines } from './sanitize';
import type { AnchorMatch } from './use-anchor-highlight';

/**
 * Текстовое представление документа с адресацией по строкам TextLocation.
 *
 * Содержимое выводится текстовыми узлами React: innerHTML не используется,
 * поэтому разметка и скрипты внутри документа остаются видимым текстом и не
 * исполняются (FR-043). Представление только для чтения: исходный документ не
 * редактируется и новая версия не создаётся (FR-007).
 */
export function TextViewer({ content, match }: { content: string; match: AnchorMatch | null }) {
  const lines = toDocumentLines(content);
  const highlightRef = useRef<HTMLElement>(null);

  useEffect(() => {
    highlightRef.current?.scrollIntoView({ block: 'center' });
  }, [match]);

  const highlighted =
    match && match.kind === 'text' ? { start: match.lineStart, end: match.lineEnd } : null;

  return (
    <div className="max-h-[32rem] overflow-auto rounded border border-line bg-surface">
      <pre className="m-0 whitespace-pre-wrap p-3 font-mono text-xs leading-relaxed text-ink">
        {lines.map((line) => {
          const isHighlighted =
            highlighted !== null && line.number >= highlighted.start && line.number <= highlighted.end;
          return (
            <code
              key={line.number}
              ref={isHighlighted && line.number === highlighted?.start ? highlightRef : undefined}
              className={`block ${isHighlighted ? 'bg-amber-100 font-semibold' : ''}`}
              data-line={line.number}
            >
              <span aria-hidden="true" className="mr-3 inline-block w-8 select-none text-right text-ink-muted">
                {line.number}
              </span>
              {line.text || ' '}
            </code>
          );
        })}
      </pre>
    </div>
  );
}
