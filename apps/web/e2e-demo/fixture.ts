import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import type { EvidenceAnchor, FindingDialogue, ReviewReport } from '../src/api/generated/model';
import type { DemoPackage } from '../src/mocks/demo-package';

/** An ASCII-only two-page PDF built solely for the browser verification. */
function syntheticPdf(): Buffer {
  const text = 'BT /F1 16 Tf 40 740 Td (Synthetic demo document) Tj ET';
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    `<< /Length ${text.length} >>\nstream\n${text}\nendstream`,
  ];
  let pdf = '%PDF-1.4\n';
  const offsets = objects.map((value, index) => {
    const offset = pdf.length;
    pdf += `${index + 1} 0 obj\n${value}\nendobj\n`;
    return offset;
  });
  const xref = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  pdf += offsets.map((offset) => `${String(offset).padStart(10, '0')} 00000 n \n`).join('');
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(pdf);
}

async function canonical<T>(name: string): Promise<T> {
  return JSON.parse(await readFile(new URL(`../../../contracts/review-platform/v1/examples/http/${name}.json`, import.meta.url), 'utf8')) as T;
}

export async function installSyntheticDemoPackage(): Promise<DemoPackage> {
  const pdf = syntheticPdf();
  const document = await canonical<DemoPackage['document']>('document');
  document.filename = 'synthetic-demo.pdf';
  document.media_type = 'application/pdf';
  document.size_bytes = pdf.byteLength;
  document.sha256 = createHash('sha256').update(pdf).digest('hex');
  const report = await canonical<ReviewReport>('report');
  const anchor: EvidenceAnchor = {
    ...report.findings[0]!.anchors[0]!,
    source_name: document.filename,
    fragment_id: 'source-main-page-2',
    quote: 'Synthetic demo document',
    quote_start: 0,
    quote_end: 23,
    location: { kind: 'pdf', page: 2, rects: [[0.05, 0.04, 0.6, 0.1]] },
  };
  report.findings[0]!.anchors = [anchor];
  report.findings.push({
    ...report.findings[0]!,
    id: '80000000-0000-4000-8000-000000000002',
    ordinal: 2,
    title: 'Не определено поведение при повторной загрузке',
  });
  report.provenance.sources[0]!.filename = document.filename;
  report.provenance.sources[0]!.sha256 = document.sha256;
  report.coverage.target_fragment_ids = [anchor.fragment_id];
  report.coverage.reviewed_fragment_ids = [anchor.fragment_id];
  const template = await canonical<FindingDialogue>('dialogue.open');
  template.turns[0]!.assistant_response!.anchors = [anchor];
  const data: DemoPackage = {
    schemaVersion: 1,
    document,
    report,
    dialogues: Object.fromEntries(report.findings.map((finding) => [finding.id, { ...template, finding_id: finding.id }])),
  };
  await mkdir('dist-demo/data', { recursive: true });
  await writeFile('dist-demo/data/demo.json', JSON.stringify(data));
  await writeFile('dist-demo/data/document.pdf', pdf);
  return data;
}
