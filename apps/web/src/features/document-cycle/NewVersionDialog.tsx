import { useRef, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { useQueries } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { getDocument, getGetDocumentQueryOptions, uploadDocument, useGetDocument, useListModelProfiles, useListReviewProfiles, useUploadDocumentVersion } from '@/api/generated/endpoints';
import type { Document, ReviewRun } from '@/api/generated/model';
import { Button, Callout } from '@/components/ui';
import { useBootstrap } from '@/features/new-review/api/use-bootstrap';
import { useCreateReviewRun } from '@/features/new-review/api/use-create-review-run';
import { DialogueAttachments } from '@/features/finding-dialogue/components/DialogueAttachments';
import { validateUpload, SUPPORTED_EXTENSIONS } from '@/features/new-review/lib/validate-upload';

export function NewVersionDialog({ workspaceId, familyId, prior, onClose }: { workspaceId: string; familyId: string; prior: ReviewRun; onClose: () => void }) {
  const navigate = useNavigate();
  const { limits } = useBootstrap();
  const [file, setFile] = useState<File>();
  const [uploaded, setUploaded] = useState<Document>();
  const [extra, setExtra] = useState<Document[]>([]);
  const [removed, setRemoved] = useState<string[]>([]);
  const [note, setNote] = useState('');
  const [noteDocument, setNoteDocument] = useState<Document>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [profileId, setProfileId] = useState(prior.execution_snapshot.profile.id + '@' + prior.execution_snapshot.profile.version);
  const [modelId, setModelId] = useState(prior.execution_snapshot.model_profile.id + '@' + prior.execution_snapshot.model_profile.version);
  const profiles = useListReviewProfiles(workspaceId);
  const models = useListModelProfiles(workspaceId);
  const inherited = useQueries({ queries: prior.context_document_ids.map(id => getGetDocumentQueryOptions(workspaceId, id)) });
  const contexts = [...inherited.flatMap(q => q.data ? [q.data] : []), ...extra].filter(d => !removed.includes(d.id));
  const contextQueries = useQueries({ queries: contexts.map(d => getGetDocumentQueryOptions(workspaceId, d.id, { query: { refetchInterval: q => q.state.data?.extraction_state === 'pending' ? 1000 : false } })) });
  const input = useRef<HTMLInputElement>(null);
  const headers = useRef(new Headers({ 'Idempotency-Key': crypto.randomUUID() }));
  const upload = useUploadDocumentVersion({ request: { headers: headers.current } });
  const run = useCreateReviewRun();
  const document = useGetDocument(workspaceId, uploaded?.id ?? '', { query: { enabled: Boolean(uploaded), refetchInterval: q => q.state.data?.extraction_state === 'pending' ? 1000 : false } });
  const noteQuery = useGetDocument(workspaceId, noteDocument?.id ?? '', { query: { enabled: Boolean(noteDocument), refetchInterval: q => q.state.data?.extraction_state === 'pending' ? 1000 : false } });
  const pending = upload.isPending || run.isPending || busy;
  const profile = profiles.data?.items.find(p => p.id + '@' + p.version === profileId);
  const model = models.data?.items.find(p => p.id + '@' + p.version === modelId && p.availability === 'available');
  const waiting = [...contextQueries, ...(noteDocument ? [noteQuery] : []), ...(uploaded ? [document] : [])].some(q => !q.data || !['completed', 'partial'].includes(q.data.extraction_state));
  async function choose(next: File) {
    if (!limits || pending) return;
    const validation = validateUpload(next, limits);
    if (!validation.ok) { setError(validation.reason); return; }
    setFile(next); setUploaded(undefined); setError('');
    headers.current.set('Idempotency-Key', crypto.randomUUID());
    try { setUploaded((await upload.mutateAsync({ workspaceId, familyId, data: { file: next } })).document); }
    catch { setError('Файл не загружен. Выберите его повторно.'); }
  }
  async function start() {
    if (!uploaded || !profile || !model || waiting || pending) return;
    setError('');
    if (limits && contexts.length + (note.trim() ? 1 : 0) > limits.max_context_documents) { setError('Достигнут лимит контекстных материалов. Удалите лишний файл.'); return; }
    try {
      let notes = noteDocument;
      if (note.trim() && !notes) {
        setBusy(true);
        notes = await uploadDocument(workspaceId, { file: new File([note], 'Уточнения к проверке.txt', { type: 'text/plain' }) });
        setNoteDocument(notes);
        for (let attempt = 0; notes.extraction_state === 'pending' && attempt < 30; attempt++) {
          await new Promise(resolve => setTimeout(resolve, 1000));
          notes = await getDocument(workspaceId, notes.id);
        }
        if (!['completed', 'partial'].includes(notes.extraction_state)) throw new Error('Текст уточнений ещё не готов.');
      }
      const result = await run.createRun({ workspaceId, documentId: uploaded.id, contextDocumentIds: [...contexts.map(d => d.id), ...(notes ? [notes.id] : [])], profile, modelProfile: model, locale: prior.locale });
      setBusy(false); onClose(); void navigate(`/runs/${result.id}`);
    } catch { setBusy(false); setError('Не удалось запустить проверку. Загруженные материалы сохранены в форме. Повторите запуск.'); }
  }
  async function retryUpload() {
    if (!file || pending) return;
    setError('');
    try { setUploaded((await upload.mutateAsync({ workspaceId, familyId, data: { file } })).document); }
    catch { setError('Файл не загружен. Повторите загрузку.'); }
  }
  return <Dialog.Root open onOpenChange={open => { if (!open && !pending) onClose(); }}><Dialog.Portal><Dialog.Overlay className="review-modal-overlay" /><Dialog.Content className="review-version-modal">
    <header><Dialog.Title>Следующая версия</Dialog.Title><Button aria-label="Закрыть" disabled={pending} onClick={onClose}>×</Button></header><Dialog.Description className="text-xs text-ink-muted">Загрузите исправленный файл. Прежний результат и решения сохранятся в истории.</Dialog.Description>
    <div className="review-file-drop" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) void choose(f); }}>
      <p>{file?.name ?? 'Перетащите файл новой версии'}</p><p className="text-xs text-ink-muted">PDF, Markdown или TXT</p>
      <input ref={input} type="file" aria-label="Файл новой версии" hidden accept={SUPPORTED_EXTENSIONS.join(',')} onChange={e => { const f = e.target.files?.[0]; if (f) void choose(f); e.target.value = ''; }} />
      <Button disabled={pending || !limits} onClick={() => input.current?.click()}>{upload.isPending ? 'Загружаем…' : 'Выбрать файл'}</Button>
    </div>
    <label className="block text-sm" htmlFor="version-context">Контекст и уточнения</label><textarea className="review-note" id="version-context" rows={2} value={note} disabled={pending} onChange={e => { setNote(e.target.value); setNoteDocument(undefined); }} placeholder="Добавьте уточнения для проверки" />
    <DialogueAttachments workspaceId={workspaceId} documents={contexts} disabled={pending} onBusy={setBusy} onChange={next => {
      setExtra(next.filter(d => !prior.context_document_ids.includes(d.id)));
      setRemoved(prior.context_document_ids.filter(id => !next.some(d => d.id === id)));
    }} />
    {inherited.some(q => q.isError) ? <Callout tone="warn" title="Не удалось загрузить прежний контекст"><Button onClick={() => inherited.forEach(q => { void q.refetch(); })}>Повторить</Button></Callout> : null}
    <details><summary>Параметры проверки</summary><label htmlFor="version-profile">Профиль проверки</label><select id="version-profile" value={profileId} onChange={e => setProfileId(e.target.value)}>{!profile ? <option value={profileId}>Прежний профиль недоступен — выберите профиль</option> : null}{profiles.data?.items.map(p => <option key={p.id} value={p.id + '@' + p.version}>{p.name} · {p.version}</option>)}</select>
      <label htmlFor="version-model">Модель</label><select id="version-model" value={modelId} onChange={e => setModelId(e.target.value)}>{!model ? <option value={modelId}>Выберите доступную модель</option> : null}{models.data?.items.filter(m => m.availability === 'available').map(m => <option key={m.id} value={m.id + '@' + m.version}>{m.name}</option>)}</select></details>
    {error ? <div role="alert" className="text-sm text-accent"><p>{error}</p>{file && !uploaded ? <Button disabled={pending} onClick={() => void retryUpload()}>Повторить загрузку</Button> : null}</div> : null}
    {document.data?.extraction_state === 'partial' || contextQueries.some(q => q.data?.extraction_state === 'partial') ? <Callout tone="warn" title="Часть текста извлечь не удалось">Проверка охватит только доступные фрагменты.</Callout> : null}
    {waiting ? <p className="text-xs text-ink-muted">Ожидаем извлечения текста. При ошибке обработки выберите другой файл.</p> : null}
    <footer><Button disabled={pending} onClick={onClose}>Отмена</Button><Button variant="primary" disabled={!uploaded || !profile || !model || pending || waiting || inherited.some(q => !q.isSuccess)} onClick={() => void start()}>{pending ? 'Подготавливаем…' : 'Проверить новую версию'}</Button></footer>
  </Dialog.Content></Dialog.Portal></Dialog.Root>;
}
