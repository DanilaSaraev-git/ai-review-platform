import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PdfViewer } from './PdfViewer';

const pdf = vi.hoisted(() => {
  const render = vi.fn(() => ({ promise: Promise.resolve(), cancel: vi.fn() }));
  const getPage = vi.fn(async () => ({ getViewport: () => ({ width: 600, height: 850 }), render }));
  const document = { numPages: 3, getPage };
  return { render, getPage, document, destroy: vi.fn() };
});
vi.mock('pdfjs-dist', () => ({
  GlobalWorkerOptions: { workerSrc: '' },
  getDocument: () => ({ promise: Promise.resolve(pdf.document), destroy: pdf.destroy }),
}));

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('постоянный PDF', () => {
  it('показывает все страницы и не перерисовывает их при смене привязки', async () => {
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({} as CanvasRenderingContext2D);
    vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} });
    const source = { arrayBuffer: async () => new ArrayBuffer(0) } as Blob;
    const { container, rerender } = render(<PdfViewer source={source} match={null} />);
    await waitFor(() => expect(pdf.render).toHaveBeenCalledTimes(3));
    expect(screen.getByText('Страница 1')).toBeInTheDocument();
    expect(screen.getByText('Страница 3')).toBeInTheDocument();
    const firstCanvas = container.querySelector('canvas');
    rerender(<PdfViewer source={source} match={{ kind: 'pdf', page: 2, rects: [[0.1, 0.2, 0.9, 0.3]], quote: 'synthetic', matched: true }} />);
    expect(container.querySelector('canvas')).toBe(firstCanvas);
    expect(container.querySelectorAll('canvas')).toHaveLength(3);
    expect(container.querySelector('[data-pdf-page="2"] .numbat-pdf-highlight')).toBeInTheDocument();
    expect(pdf.render).toHaveBeenCalledTimes(3);
  });
});
