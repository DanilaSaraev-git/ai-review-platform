import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import * as fixtures from '@/mocks/fixtures';
import { API } from './base';
import { happyPath } from './happy-path';

/** Minimal two-page PDF, generated from ASCII-only synthetic text with exact xref offsets. */
function twoPagePdf(): string {
  const stream = (page: number) => `BT /F1 22 Tf 72 750 Td (Synthetic document - page ${page}) Tj ET\n72 680 120 20 re f\n`;
  const first = stream(1);
  const second = stream(2);
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 7 0 R >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    `<< /Length ${first.length} >>\nstream\n${first}endstream`,
    `<< /Length ${second.length} >>\nstream\n${second}endstream`,
  ];
  let result = '%PDF-1.4\n';
  const offsets = [0];
  objects.forEach((object, index) => {
    offsets.push(result.length);
    result += `${index + 1} 0 obj\n${object}\nendobj\n`;
  });
  const xref = result.length;
  result += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  result += offsets.slice(1).map((offset) => `${String(offset).padStart(10, '0')} 00000 n \n`).join('');
  result += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return result;
}

/** PDF bytes go through the normal generated client and the real PDF.js worker. */
export function pdfDocument(): RequestHandler[] {
  const content = twoPagePdf();
  const document = { ...fixtures.mainDocument, filename: 'synthetic-two-pages.pdf', media_type: 'application/pdf', size_bytes: content.length };
  const finding = fixtures.report.findings[0]!;
  const quote = 'Synthetic document - page 2';
  return [
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId`, () => HttpResponse.json(fixtures.runCompleted)),
    http.get(`${API}/workspaces/:workspaceId/documents/:documentId`, () => HttpResponse.json(document)),
    http.get(`${API}/workspaces/:workspaceId/documents/:documentId/content`, () =>
      new HttpResponse(content, { headers: { 'Content-Type': 'application/pdf' } })),
    http.get(`${API}/workspaces/:workspaceId/review-runs/:runId/report`, () => HttpResponse.json({
      ...fixtures.report,
      findings: [{
        ...finding,
        anchors: [{ ...finding.anchors[0], source_name: document.filename, fragment_id: 'source-main-page-2', quote, quote_start: 0, quote_end: quote.length,
          location: { kind: 'pdf', page: 2, rects: [[0.12, 0.08, 0.75, 0.12]] } }],
      }],
      provenance: { ...fixtures.report.provenance, sources: fixtures.report.provenance.sources.map((source) => ({ ...source, filename: document.filename })) },
    })),
    ...happyPath(),
  ];
}
