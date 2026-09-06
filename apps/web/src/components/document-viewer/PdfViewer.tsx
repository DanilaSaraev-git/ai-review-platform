import { useEffect, useRef, useState } from 'react';
import type { PDFDocumentProxy } from 'pdfjs-dist';
import { Button, Callout, Spinner } from '@/components/ui';
import type { AnchorMatch } from './use-anchor-highlight';

type PdfMatch = Extract<AnchorMatch, { kind: 'pdf' }>;

function PdfPage({ document, pageNumber, match }: { document: PDFDocumentProxy; pageNumber: number; match: PdfMatch | null }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [error, setError] = useState(false);
  const [isRendering, setIsRendering] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let cancelRender: (() => void) | undefined;
    async function render() {
      setIsRendering(true);
      setError(false);
      try {
        const page = await document.getPage(pageNumber);
        const canvas = canvasRef.current;
        const context = canvas?.getContext('2d');
        if (cancelled || !canvas || !context) return;
        const viewport = page.getViewport({ scale: 1.4 });
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        const task = page.render({ canvas, canvasContext: context, viewport });
        cancelRender = () => task.cancel();
        await task.promise;
      } catch {
        if (!cancelled) setError(true);
      } finally {
        if (!cancelled) setIsRendering(false);
      }
    }
    void render();
    return () => { cancelled = true; cancelRender?.(); };
  }, [document, pageNumber]);

  return <figure className="numbat-pdf-page" data-pdf-page={pageNumber}>
    <figcaption>Страница {pageNumber}</figcaption>
    {isRendering ? <Spinner label={`Отрисовываем страницу ${pageNumber}…`} /> : null}
    {error ? <Callout tone="warn" title={`Не удалось отобразить страницу ${pageNumber}`} /> : null}
    <div className="numbat-pdf-canvas">
      <canvas ref={canvasRef} aria-label={`Страница ${pageNumber} исходного документа`} />
      {match?.rects.map(([x0 = 0, y0 = 0, x1 = 0, y1 = 0], index) => <span key={index} className="numbat-pdf-highlight"
        style={{ left: `${x0 * 100}%`, top: `${y0 * 100}%`, width: `${(x1 - x0) * 100}%`, height: `${(y1 - y0) * 100}%` }} />)}
    </div>
  </figure>;
}

/** All PDF pages remain mounted; an anchor changes only the highlight and local scroll. */
export function PdfViewer({ source, match }: { source: Blob | undefined; match: AnchorMatch | null }) {
  const [document, setDocument] = useState<PDFDocumentProxy | null>(null);
  const [error, setError] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const pdfMatch = match?.kind === 'pdf' ? match : null;
  const page = pdfMatch?.page;
  const firstRect = pdfMatch?.rects[0];
  const anchorTop = firstRect?.[1] ?? 0;

  useEffect(() => {
    if (!source) return;
    let cancelled = false;
    let destroy: (() => void) | undefined;
    async function load() {
      setError(false);
      try {
        const pdfjs = await import('pdfjs-dist');
        if (cancelled) return;
        pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url).toString();
        const buffer = await source!.arrayBuffer();
        if (cancelled) return;
        const task = pdfjs.getDocument({ data: new Uint8Array(buffer) });
        destroy = () => { void task.destroy(); };
        const result = await task.promise;
        if (!cancelled) setDocument(result);
      } catch {
        if (!cancelled) setError(true);
      }
    }
    void load();
    return () => { cancelled = true; destroy?.(); };
  }, [source, reloadKey]);

  useEffect(() => {
    const container = scrollRef.current;
    const target = container?.querySelector<HTMLElement>(`[data-pdf-page="${page}"]`);
    if (!container || !target || !page) return;
    // Page canvas dimensions settle asynchronously. Observe them only for a new selection.
    const scrollToAnchor = () => {
      const pageOffset = target.getBoundingClientRect().top - container.getBoundingClientRect().top;
      container.scrollTop += pageOffset + target.clientHeight * anchorTop - container.clientHeight / 3;
    };
    scrollToAnchor();
    const observer = new ResizeObserver(scrollToAnchor);
    container.querySelectorAll('[data-pdf-page]').forEach((element) => observer.observe(element));
    const stopTracking = () => observer.disconnect();
    container.addEventListener('wheel', stopTracking, { once: true });
    container.addEventListener('touchstart', stopTracking, { once: true });
    container.addEventListener('keydown', stopTracking, { once: true });
    return () => {
      observer.disconnect();
      container.removeEventListener('wheel', stopTracking);
      container.removeEventListener('touchstart', stopTracking);
      container.removeEventListener('keydown', stopTracking);
    };
  }, [document, page, anchorTop]);

  if (error) return <Callout tone="warn" title="Не удалось отобразить PDF"><Button className="mt-2" onClick={() => setReloadKey((value) => value + 1)}>Повторить</Button></Callout>;
  if (!document) return <Spinner label="Загружаем документ…" />;

  return <div ref={scrollRef} className="numbat-document-scroll" data-testid="document-scroll" tabIndex={0} aria-label="Страницы исходного документа">
    {Array.from({ length: document.numPages }, (_, index) => <PdfPage key={index + 1} document={document} pageNumber={index + 1} match={page === index + 1 ? pdfMatch : null} />)}
  </div>;
}
