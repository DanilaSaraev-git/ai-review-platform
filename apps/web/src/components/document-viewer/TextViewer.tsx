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
    <div className="min-h-[28rem] flex-1 overflow-auto rounded-[6px] border border-line bg-surface shadow-[0_1px_2px_rgba(23,32,51,0.05),0_12px_32px_rgba(23,32,51,0.06)] lg:min-h-full">
      <pre className="m-0 whitespace-pre-wrap p-5 font-mono text-[13px] leading-6 text-ink sm:p-7">
        {lines.map((line) => {
          const isHighlighted =
            highlighted !== null && line.number >= highlighted.start && line.number <= highlighted.end;
          return (
            <code
              key={line.number}
              ref={isHighlighted && line.number === highlighted?.start ? highlightRef : undefined}
              className={`block border-l-2 px-2 ${isHighlighted ? 'border-accent bg-accent-tint font-semibold' : 'border-transparent'}`}
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
