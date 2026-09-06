import { useRef, useState } from 'react';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router';
import { getGetDocumentFamilyQueryKey, listDocumentFamilyRuns, listDocumentFamilyVersions, useGetDocumentVersionFamily, useGetDocumentFamily, useUploadDocumentVersion } from '@/api/generated/endpoints';
import type { DocumentFamilyVersion, PublicLimits, ReviewRun } from '@/api/generated/model';
import { isProblem } from '@/api/errors';
import { DocumentViewer } from '@/components/document-viewer';
import { Button, Callout, Spinner, StatusBadge } from '@/components/ui';
import { useBootstrap } from '@/features/new-review/api/use-bootstrap';
import { SUPPORTED_EXTENSIONS, validateUpload } from '@/features/new-review/lib/validate-upload';
import { ReviewWorkspace } from '@/features/review-report/components/ReviewWorkspace';
import { RUN_STATE_TEXT } from '@/lib/error-messages';
import { formatDateTime } from '@/lib/format';

export function DocumentFamilyPage() {
  const { familyId = '' } = useParams();
  return <FamilyWorkspace key={familyId} familyId={familyId} />;
}

function FamilyWorkspace({ familyId }: { familyId: string }) {
  const { workspaceId, limits, error: bootstrapError, retry } = useBootstrap();
  const [selected, setSelected] = useState<DocumentFamilyVersion>();
  const family = useGetDocumentFamily(workspaceId, familyId, { query: { enabled: Boolean(workspaceId && familyId) } });
  const versions = useInfiniteQuery({
    queryKey: ['document-family-versions', workspaceId, familyId],
    queryFn: ({ pageParam }) => listDocumentFamilyVersions(workspaceId, familyId, { cursor: pageParam, limit: 20 }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: Boolean(workspaceId && familyId),
  });
  const runs = useInfiniteQuery({
    queryKey: ['document-family-runs', workspaceId, familyId],
    queryFn: ({ pageParam }) => listDocumentFamilyRuns(workspaceId, familyId, { cursor: pageParam, limit: 20 }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: Boolean(workspaceId && familyId),
  });
  const entries = versions.data?.pages.flatMap((page) => page.items) ?? [];
  const current = selected ?? entries.find((version) => version.document.id === family.data?.latest_document_id) ?? entries[0];
  if (bootstrapError || family.isError) return <div className="p-5"><Callout tone="danger" title="Не удалось открыть документ"><Button onClick={() => void (bootstrapError ? retry() : family.refetch())}>Повторить</Button></Callout></div>;
  return <ReviewWorkspace toolbar={<>
    <Link to="/documents" className="text-xs text-accent">Документы</Link>
    <h1 className="numbat-workspace-filename">{family.data?.name ?? 'Документ'}</h1>
    {current ? <span className="text-xs text-ink-muted">Версия {current.version_number} · {current.document.filename}</span> : null}
  </>} document={current ? <DocumentViewer key={current.document.id} workspaceId={workspaceId} document={current.document} finding={undefined} /> : versions.isError ? <Callout tone="danger" title="Не удалось загрузить версии"><Button onClick={() => void versions.refetch()}>Повторить</Button></Callout> : <Spinner label="Загружаем исходник…" />} panel={<div className="numbat-panel-scroll p-5">
    <h2 className="mb-4 text-lg font-medium">Версии и проверки</h2>
    {limits ? <VersionUpload workspaceId={workspaceId} familyId={familyId} limits={limits} onUploaded={setSelected} /> : null}
    {current ? <div className="my-4">
      <Link to={`/new?document=${current.document.id}`} className="text-sm font-medium text-accent">Проверить версию {current.version_number}</Link>
      {current.unchanged_from_previous ? <p className="mt-2 text-xs text-ink-muted">Содержимое совпадает с предыдущей версией.</p> : null}
    </div> : null}
    <section aria-label="История версий" className="my-5 flex flex-col gap-3">
      {versions.isError ? <Callout tone="danger" title="История версий не обновилась"><Button onClick={() => void versions.refetch()}>Повторить</Button></Callout> : null}
      {entries.map((version) => <div key={version.document.id} className={`rounded-[6px] border p-3 ${current?.document.id === version.document.id ? 'border-accent bg-accent-tint' : 'border-line'}`}>
        <button type="button" aria-pressed={current?.document.id === version.document.id} onClick={() => setSelected(version)} className="cursor-pointer text-left text-sm font-medium text-accent">Версия {version.version_number} · {version.document.filename}</button>
        <p className="mt-1 text-xs text-ink-muted">{formatDateTime(version.document.created_at)} · {version.document.created_by.display_name}</p>
      </div>)}
      {versions.hasNextPage ? <Button disabled={versions.isFetchingNextPage} onClick={() => void versions.fetchNextPage()}>Ещё версии</Button> : null}
    </section>
    <section aria-label="Проверки документа"><h3 className="mb-3 text-sm font-medium">Проверки документа</h3>
      {runs.isPending ? <Spinner label="Загружаем проверки…" /> : runs.isError ? <Callout tone="danger" title="Не удалось загрузить проверки"><Button onClick={() => void runs.refetch()}>Повторить</Button></Callout> : null}
      {runs.data?.pages.flatMap((page) => page.items).map((run) => <FamilyRun key={run.id} workspaceId={workspaceId} run={run} />)}
      {runs.hasNextPage ? <Button disabled={runs.isFetchingNextPage} onClick={() => void runs.fetchNextPage()}>Ещё проверки</Button> : null}
    </section>
  </div>} />;
}

function VersionUpload({ workspaceId, familyId, limits, onUploaded }: { workspaceId: string; familyId: string; limits: PublicLimits; onUploaded: (version: DocumentFamilyVersion) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const headers = useRef(new Headers());
  const upload = useUploadDocumentVersion({ request: { headers: headers.current } });
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File>();
  const [error, setError] = useState<string>();
  const intentKey = useRef(crypto.randomUUID());
  async function submit() {
    if (!file) return;
    setError(undefined);
    try {
      headers.current.set('Idempotency-Key', intentKey.current);
      const version = await upload.mutateAsync({ workspaceId, familyId, data: { file } });
      onUploaded(version);
      setFile(undefined);
      await queryClient.invalidateQueries({ queryKey: ['document-family-versions', workspaceId, familyId] });
      await queryClient.invalidateQueries({ queryKey: ['document-families', workspaceId] });
      await queryClient.invalidateQueries({ queryKey: getGetDocumentFamilyQueryKey(workspaceId, familyId) });
    } catch (cause) { setError(isProblem(cause) ? cause.problem.title : 'Не удалось загрузить версию. Повторите загрузку выбранного файла.'); }
  }
  return <section aria-label="Новая версия" className="rounded-[6px] border border-line p-3">
    <label className="block text-sm font-medium" htmlFor="version-file">Файл новой версии</label>
    <input ref={input} id="version-file" type="file" className="sr-only" accept={SUPPORTED_EXTENSIONS.join(',')} disabled={upload.isPending} onChange={(event) => {
      const next = event.target.files?.[0];
      if (!next) return;
      const result = validateUpload({ name: next.name, size: next.size, type: next.type }, limits);
      setError(result.ok ? undefined : result.reason);
      setFile(result.ok ? next : undefined);
      intentKey.current = crypto.randomUUID();
      event.target.value = '';
    }} />
    <p className="my-2 break-words text-xs text-ink-muted">{file?.name ?? 'PDF, Markdown или TXT.'}</p>
    <Button className="mr-2" disabled={upload.isPending} onClick={() => input.current?.click()}>Выбрать файл</Button>
    <Button disabled={!file || upload.isPending} onClick={() => void submit()}>{upload.isPending ? 'Загружаем…' : 'Загрузить новую версию'}</Button>
    {error ? <p role="alert" className="mt-2 text-xs text-accent">{error}</p> : null}
  </section>;
}

function FamilyRun({ workspaceId, run }: { workspaceId: string; run: ReviewRun }) {
  const version = useGetDocumentVersionFamily(workspaceId, run.document_id, { query: { staleTime: Infinity } });
  return <div className="mb-3 border-b border-line pb-3 text-xs">
    <Link to={`/runs/${run.id}${run.report_available ? '/report' : ''}`} className="font-medium text-accent">Проверка от {formatDateTime(run.created_at)}</Link>
    <p className="my-2">{version.data ? `Версия ${version.data.version_number} · ${version.data.document.filename}` : version.isError ? 'Сведения о версии недоступны' : 'Загружаем сведения о версии…'}</p>
    <StatusBadge tone={run.state === 'failed' ? 'danger' : 'neutral'}>{RUN_STATE_TEXT[run.state].label}</StatusBadge>
    <Link className="ml-3 text-accent" to={`/new?repeat=${run.id}`}>Проверить повторно</Link>
  </div>;
}
