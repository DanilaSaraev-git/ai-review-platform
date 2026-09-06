import { useRef, useState } from 'react';
import { useUploadDocument } from '@/api/generated/endpoints';
import type { Document } from '@/api/generated/model';
import { useBootstrap } from '@/features/new-review/api/use-bootstrap';
import { validateUpload, SUPPORTED_EXTENSIONS } from '@/features/new-review/lib/validate-upload';
import { Button } from '@/components/ui';

export function DialogueAttachments({ workspaceId, documents, disabled, onChange, onBusy }: { workspaceId: string; documents: Document[]; disabled: boolean; onChange: (documents: Document[]) => void; onBusy: (busy: boolean) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const upload = useUploadDocument();
  const { limits } = useBootstrap();
  const [error, setError] = useState('');
  async function attach(files: File[]) {
    if (!limits || disabled || upload.isPending) return;
    if (files.length + documents.length > Math.min(10, limits.max_context_documents)) { setError('Достигнут лимит прикреплённых файлов.'); return; }
    const added: Document[] = [];
    onBusy(true); setError('');
    try {
      for (const file of files) {
        const validation = validateUpload(file, limits);
        if (!validation.ok) throw new Error(validation.reason);
        added.push(await upload.mutateAsync({ workspaceId, data: { file } }));
        onChange([...documents, ...added]);
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Не удалось прикрепить файл.'); }
    finally { onBusy(false); }
  }
  return <div className="mt-1.5" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); void attach([...e.dataTransfer.files]); }}>
    <input ref={input} hidden type="file" multiple accept={SUPPORTED_EXTENSIONS.join(',')} onChange={e => { void attach([...e.target.files ?? []]); e.target.value = ''; }} />
    <Button disabled={disabled || upload.isPending || !limits} onClick={() => input.current?.click()}>Прикрепить файл</Button>
    <p className="mt-1 text-xs text-ink-subtle">PDF, Markdown, TXT · можно перетащить сюда</p>
    {documents.map(d => <div className="mt-2 flex items-center justify-between rounded border border-line p-2 text-xs" key={d.id}><span>{d.filename}</span><Button disabled={disabled} aria-label={`Удалить ${d.filename}`} onClick={() => onChange(documents.filter(item => item.id !== d.id))}>×</Button></div>)}
    {error ? <p role="alert" className="text-xs text-accent">{error}</p> : null}
  </div>;
}
