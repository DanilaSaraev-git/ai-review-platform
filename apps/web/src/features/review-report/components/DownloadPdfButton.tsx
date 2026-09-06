import { useState } from 'react';
import { downloadReviewPdf } from '@/api/generated/endpoints';
import { Button } from '@/components/ui';
import { isDemoMode } from '@/app/demo-mode';

/** Export always uses the selected run and the server's coherent, unfiltered snapshot. */
export function DownloadPdfButton({ workspaceId, runId }: { workspaceId: string; runId: string }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);
  async function download() {
    setPending(true);
    setError(false);
    try {
      if (isDemoMode) { const { printDemoReport } = await import('./print-demo-report'); await printDemoReport(workspaceId, runId); return; }
      const bytes = await downloadReviewPdf(workspaceId, runId);
      if (!(bytes instanceof Blob) || !bytes.type.includes('application/pdf')) throw new Error('Invalid PDF response');
      const url = URL.createObjectURL(bytes);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `numbat-${runId}.pdf`;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      globalThis.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { setError(true); } finally { setPending(false); }
  }
  return <div><Button disabled={pending} onClick={() => void download()}>{pending ? 'Готовим PDF…' : 'Скачать PDF'}</Button>
    {error ? <p role="alert" className="mt-2 text-xs text-accent">Не удалось скачать PDF. Повторите попытку.</p> : null}</div>;
}
