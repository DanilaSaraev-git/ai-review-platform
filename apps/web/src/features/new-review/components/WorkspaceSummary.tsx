import type { Actor, PublicLimits, Workspace } from '@/api/generated/model';
import { Spinner } from '@/components/ui';
import { formatBytes, formatNumber } from '@/lib/format';

/**
 * Сводка настроенного рабочего пространства и действующих лимитов (FR-001).
 *
 * Имя действующего лица показывается как атрибуция созданного, а не как
 * признак входа в систему: экранов входа, аккаунтов и ролей в v1 нет
 * (FR-002, принцип IV).
 */
export function WorkspaceSummary({
  workspace,
  actor,
  limits,
  isLoading,
}: {
  workspace: Workspace | undefined;
  actor: Actor | undefined;
  limits: PublicLimits | undefined;
  isLoading: boolean;
}) {
  if (isLoading) {
    return <Spinner label="Загружаем рабочее пространство…" />;
  }

  if (!workspace || !limits || !actor) {
    return null;
  }

  return (
    <section aria-labelledby="workspace-summary-title" className="rounded border border-line bg-surface p-4">
      <h2 id="workspace-summary-title" className="text-sm font-semibold text-ink">
        Рабочее пространство
      </h2>
      <dl className="mt-3 grid gap-3 sm:grid-cols-2">
        <div>
          <dt className="text-xs text-ink-muted">Пространство</dt>
          <dd className="text-sm text-ink">{workspace.name}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Организация</dt>
          <dd className="text-sm text-ink">{workspace.organization_name}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Действия записываются на</dt>
          <dd className="text-sm text-ink">{actor.display_name}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Лимиты</dt>
          <dd className="text-sm text-ink">
            файл до {formatBytes(limits.document_upload_max_bytes)}, контекст до{' '}
            {formatNumber(limits.max_context_documents)} материалов
          </dd>
        </div>
      </dl>
    </section>
  );
}
