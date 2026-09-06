import * as Dialog from '@radix-ui/react-dialog';
import { useInfiniteQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { listDocumentFamilyRuns, listDocumentFamilyVersions } from '@/api/generated/endpoints';
import { Button, Callout } from '@/components/ui';
import { formatDateTime } from '@/lib/format';
import { RUN_STATE_TEXT } from '@/lib/error-messages';

export function ReviewHistory({ workspaceId, familyId, runId, open, onClose }: { workspaceId: string; familyId: string; runId: string; open: boolean; onClose: () => void }) {
  const versions = useInfiniteQuery({ queryKey: ['family-versions', workspaceId, familyId], queryFn: ({ pageParam }) => listDocumentFamilyVersions(workspaceId, familyId, { cursor: pageParam, limit: 100 }), initialPageParam: undefined as string | undefined, getNextPageParam: page => page.next_cursor ?? undefined, enabled: open });
  const runs = useInfiniteQuery({ queryKey: ['family-runs', workspaceId, familyId], queryFn: ({ pageParam }) => listDocumentFamilyRuns(workspaceId, familyId, { cursor: pageParam, limit: 100 }), initialPageParam: undefined as string | undefined, getNextPageParam: page => page.next_cursor ?? undefined, enabled: open });
  return <Dialog.Root open={open} onOpenChange={value => { if (!value) onClose(); }}><Dialog.Portal><Dialog.Overlay className="review-modal-overlay" /><Dialog.Content className="review-history">
    <header><Dialog.Title>История проверки</Dialog.Title><Dialog.Close asChild><Button aria-label="Закрыть историю">×</Button></Dialog.Close></header><Dialog.Description className="text-xs text-ink-muted">Версии файла и результаты их проверки</Dialog.Description>
    {versions.isError || runs.isError ? <Callout tone="warn" title="Не удалось загрузить историю"><Button onClick={() => { void versions.refetch(); void runs.refetch(); }}>Повторить</Button></Callout> : null}
    {versions.data?.pages.flatMap(p => p.items).map(v => <section className="history-version" key={v.document.id}><h3>Версия {v.version_number}</h3><p className="text-xs text-ink-muted">{v.document.filename}</p>
      {runs.data?.pages.flatMap(p => p.items).filter(r => r.document_id === v.document.id).map(r => <Link onClick={onClose} className={r.id === runId ? 'history-run selected' : 'history-run'} key={r.id} to={`/runs/${r.id}${r.report_available ? '/report' : ''}`}><span>{formatDateTime(r.created_at)}</span><span>{RUN_STATE_TEXT[r.state].label}{r.id === runId ? ' · Открытый результат' : ''}</span></Link>)}
    </section>)}
    {versions.hasNextPage ? <Button onClick={() => void versions.fetchNextPage()}>Ещё версии</Button> : null}
    {runs.hasNextPage ? <Button onClick={() => void runs.fetchNextPage()}>Ещё запуски</Button> : null}
  </Dialog.Content></Dialog.Portal></Dialog.Root>;
}
