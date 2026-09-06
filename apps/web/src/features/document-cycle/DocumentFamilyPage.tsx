import { useQuery } from '@tanstack/react-query';
import { Navigate, Link, useParams } from 'react-router';
import { listDocumentFamilyRuns } from '@/api/generated/endpoints';
import { useBootstrap } from '@/features/new-review/api/use-bootstrap';
import { Button, Callout, Spinner } from '@/components/ui';

/** Preserve old bookmarks without another document/history screen. */
export function DocumentFamilyPage() {
  const { familyId = '' } = useParams();
  const { workspaceId } = useBootstrap();
  const runs = useQuery({ queryKey: ['latest-family-run', workspaceId, familyId], queryFn: () => listDocumentFamilyRuns(workspaceId, familyId, { limit: 1 }), enabled: Boolean(workspaceId && familyId) });
  const run = runs.data?.items[0];
  if (run) return <Navigate replace to={`/runs/${run.id}${run.report_available ? '/report' : ''}`} />;
  if (runs.isError) return <Callout tone="warn" title="Не удалось открыть проверку"><Button onClick={() => void runs.refetch()}>Повторить</Button></Callout>;
  if (runs.isPending) return <Spinner label="Открываем последний результат…" />;
  return <div className="p-5"><p>Для этого файла ещё нет проверки.</p><Link to="/new">Новая проверка</Link></div>;
}
