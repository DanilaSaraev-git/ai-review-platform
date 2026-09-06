import { useInfiniteQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { listDocumentFamilies } from '@/api/generated/endpoints';
import { Button, Callout, Spinner } from '@/components/ui';
import { useBootstrap } from '@/features/new-review/api/use-bootstrap';
import { formatDateTime } from '@/lib/format';
import '@/styles/review-entry.css';

export function DocumentsPage() {
  const { workspaceId, error, retry } = useBootstrap();
  const query = useInfiniteQuery({
    queryKey: ['document-families', workspaceId],
    queryFn: ({ pageParam }) => listDocumentFamilies(workspaceId, { cursor: pageParam, limit: 20 }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: Boolean(workspaceId),
  });
  const documents = query.data?.pages.flatMap((page) => page.items) ?? [];
  return <main className="history-page">
    <header className="history-page-header"><h1>Документы</h1><Link to="/new" className="history-new-link">Загрузить документ</Link></header>
    {error || query.isError ? <Callout tone="danger" title="Не удалось загрузить документы"><Button onClick={() => void (error ? retry() : query.refetch())}>Повторить</Button></Callout>
      : query.isPending ? <Spinner label="Загружаем документы…" />
        : documents.length === 0 ? <p className="text-sm text-ink-muted">Документов пока нет.</p>
          : <div className="history-table-wrap"><table className="history-table"><thead><tr><th>Документ</th><th>Версий</th><th>Создан</th></tr></thead>
            <tbody>{documents.map((document) => <tr key={document.id}>
              <th scope="row"><Link to={`/documents/${document.id}`}>{document.name}</Link></th>
              <td>{document.latest_version_number}</td><td>{formatDateTime(document.created_at)}</td>
            </tr>)}</tbody></table></div>}
    {query.hasNextPage ? <Button className="mt-3" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>Показать ещё документы</Button> : null}
  </main>;
}
