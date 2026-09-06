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
  const highlightRef = useRef<HTMLSpanElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const highlighted = match?.kind === 'text' ? { start: match.lineStart, end: match.lineEnd } : null;
  const start = highlighted?.start;
  const end = highlighted?.end;

  useEffect(() => {
    const container = scrollRef.current;
    const highlight = highlightRef.current;
    if (!container || !highlight || start === undefined) return;
    // scrollIntoView would also scroll the page and move the neighbouring panel.
    const target = highlight.getBoundingClientRect().top - container.getBoundingClientRect().top;
    container.scrollTop += target - container.clientHeight / 3;
  }, [start, end]);

  return (
    <div ref={scrollRef} className="numbat-document-scroll" data-testid="document-scroll" tabIndex={0} aria-label="Текст исходного документа">
      <pre className="numbat-document-text">
        {lines.map((line) => {
          const isHighlighted =
            highlighted !== null && line.number >= highlighted.start && line.number <= highlighted.end;
          return (
            <span
              key={line.number}
              ref={isHighlighted && line.number === highlighted?.start ? highlightRef : undefined}
              className={`numbat-document-line ${/^#{1,3}\s/u.test(line.text) ? 'numbat-document-line-heading' : ''}`}
              data-line={line.number}
              data-highlighted={isHighlighted ? 'true' : undefined}
            >
              <span aria-hidden="true" className="numbat-document-line-number">
                {line.number}
              </span>
              <span>{line.text || ' '}</span>
            </span>
          );
        })}
      </pre>
    </div>
  );
}
