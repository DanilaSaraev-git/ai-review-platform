import { useEffect, useRef, useState } from 'react';
import { Callout, Spinner } from '@/components/ui';
import type { AnchorMatch } from './use-anchor-highlight';

/**
 * Просмотр PDF на PDF.js с переходом к странице замечания и подсветкой
 * по нормализованным координатам rects (решение R-09, FR-021).
 *
 * Координаты приходят в долях [0..1] от размера страницы, поэтому пересчёт
 * не зависит от масштаба отрисовки.
 */
export function PdfViewer({ source, match }: { source: Blob | undefined; match: AnchorMatch | null }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRendering, setIsRendering] = useState(false);
  const page = match && match.kind === 'pdf' ? match.page : 1;

  useEffect(() => {
    if (!source) {
      return;
    }
    let cancelled = false;

    async function render(): Promise<void> {
      setIsRendering(true);
      setError(null);
      try {
        const pdfjs = await import('pdfjs-dist');
        pdfjs.GlobalWorkerOptions.workerSrc = new URL(
          'pdfjs-dist/build/pdf.worker.min.mjs',
          import.meta.url,
        ).toString();

        const buffer = await source!.arrayBuffer();
        const document = await pdfjs.getDocument({ data: new Uint8Array(buffer) }).promise;
        const pdfPage = await document.getPage(Math.min(page, document.numPages));
        const viewport = pdfPage.getViewport({ scale: 1.4 });
        const canvas = canvasRef.current;
        const context = canvas?.getContext('2d');
        if (cancelled || !canvas || !context) {
          return;
        }
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        await pdfPage.render({ canvas, canvasContext: context, viewport }).promise;

        if (match?.kind === 'pdf') {
          context.save();
          context.fillStyle = 'rgba(251, 191, 36, 0.35)';
          for (const rect of match.rects) {
            const [x0 = 0, y0 = 0, x1 = 0, y1 = 0] = rect;
            context.fillRect(
              x0 * viewport.width,
              y0 * viewport.height,
              (x1 - x0) * viewport.width,
              (y1 - y0) * viewport.height,
            );
          }
          context.restore();
        }
      } catch {
        if (!cancelled) {
          setError('Не удалось отобразить PDF. Замечание показано без подсветки фрагмента.');
        }
      } finally {
        if (!cancelled) {
          setIsRendering(false);
        }
      }
    }

    void render();
    return () => {
      cancelled = true;
    };
  }, [source, page, match]);

  if (!source) {
    return <Spinner label="Загружаем документ…" />;
  }

  return (
    <div className="flex flex-col gap-2">
      {isRendering ? <Spinner label={`Отрисовываем страницу ${page}…`} /> : null}
      {error ? <Callout tone="warn" title={error} /> : null}
      <p className="text-xs text-ink-muted">Страница {page}</p>
      <div className="max-h-[32rem] overflow-auto rounded border border-line bg-surface p-2">
        <canvas ref={canvasRef} className="mx-auto block" />
      </div>
    </div>
  );
}
