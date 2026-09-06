import type { Bootstrap, Document, FindingDialogue, ReviewReport } from '@/api/generated/model';
import { appBaseUrl } from '@/app/demo-mode';

/** Runtime data is mounted privately. Customer examples never enter the bundle. */
export interface DemoPackage {
  schemaVersion: 1;
  bootstrap?: Bootstrap;
  document: Document;
  report: ReviewReport;
  dialogues: Record<string, FindingDialogue>;
  /** Only used by synthetic text packages. PDF packages use data/document.pdf. */
  documentText?: string;
}

export async function loadDemoPackage(): Promise<DemoPackage> {
  const response = await fetch(`${appBaseUrl}data/demo.json`, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error('Демонстрационные материалы недоступны.');
  }
  const value = await response.json() as DemoPackage;
  if (
    value.schemaVersion !== 1 || !value.document?.id || !value.report?.id ||
    !Array.isArray(value.report.findings) || !value.dialogues ||
    (value.document.media_type !== 'application/pdf' && typeof value.documentText !== 'string') ||
    value.report.findings.some((finding) => !value.dialogues[finding.id]?.turns?.[0]?.assistant_response)
  ) {
    throw new Error('Демонстрационные материалы имеют неподдерживаемый формат.');
  }
  return value;
}
