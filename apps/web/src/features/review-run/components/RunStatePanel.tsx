import { Link } from 'react-router';
import type { ReviewRun } from '@/api/generated/model';
import { Callout, StatusBadge } from '@/components/ui';
import { RUN_ERROR_TEXT, RUN_STATE_TEXT } from '@/lib/error-messages';
import { formatDateTime, formatDuration } from '@/lib/format';
import type { RunProgressState } from '../lib/stall-detector';

/**
 * Состояние запуска для всех семи значений контракта (FR-013).
 * Ни одно состояние не приводит к пустому экрану: у каждого есть подпись,
 * пояснение и, где уместно, следующий шаг.
 */
const TONE: Record<ReviewRun['state'], 'progress' | 'ok' | 'danger' | 'neutral'> = {
  queued: 'progress',
  preparing: 'progress',
  reviewing: 'progress',
  validating: 'progress',
  completed: 'ok',
  failed: 'danger',
  cancelled: 'neutral',
};

export function RunStatePanel({
  run,
  progress,
  isOffline = false,
}: {
  run: ReviewRun;
  progress: RunProgressState;
  isOffline?: boolean;
}) {
  const text = RUN_STATE_TEXT[run.state];
  const snapshot = run.execution_snapshot;

  return (
    <section aria-labelledby="run-state-title" className="rounded border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="run-state-title" className="text-sm font-semibold text-ink">
          Состояние проверки
        </h2>
        <StatusBadge tone={TONE[run.state]}>{text.label}</StatusBadge>
      </div>

      <p className="mt-2 text-sm text-ink-muted">{run.progress?.message || text.hint}</p>
      <p className="mt-1 text-xs text-ink-muted">Идёт {formatDuration(progress.durationMs)}</p>

      {/* Предупреждение не подменяет состояние и не прекращает наблюдение (FR-039). */}
      {progress.warning ? (
        <div className="mt-3">
          <Callout tone="warn" title="Проверка идёт дольше обычного">
            {progress.warning}
          </Callout>
        </div>
      ) : null}

      {isOffline ? (
        <div className="mt-3">
          <Callout tone="warn" title="Состояние не обновляется">
            Связь с сервисом временно потеряна. Проверка продолжается на стороне сервиса; обновление возобновится
            автоматически.
          </Callout>
        </div>
      ) : null}

      {run.state === 'failed' && run.error ? (
        <div className="mt-3">
          <Callout tone="danger" title="Проверка не удалась">
            <p>{RUN_ERROR_TEXT[run.error.code]}</p>
            <p className="mt-1">
              {run.error.retryable
                ? 'Повтор допустим: можно создать новую проверку с теми же настройками.'
                : 'Повтор не поможет: нужны другие входные данные или настройки.'}
            </p>
            <p className="mt-1 font-medium">Отчёт не опубликован.</p>
          </Callout>
        </div>
      ) : null}

      {run.state === 'cancelled' ? (
        <div className="mt-3">
          <Callout tone="neutral" title="Проверка отменена">
            Отчёт не публиковался.
          </Callout>
        </div>
      ) : null}

      {run.state === 'completed' && run.report_available ? (
        <p className="mt-3">
          <Link className="text-accent underline" to={`/runs/${run.id}/report`}>
            Открыть отчёт
          </Link>
        </p>
      ) : null}

      <details className="mt-4">
        <summary className="cursor-pointer text-xs font-medium text-ink-muted">
          Зафиксированные версии проверки
        </summary>
        <dl className="mt-2 grid gap-2 text-xs sm:grid-cols-2">
          <div>
            <dt className="text-ink-muted">Профиль проверки</dt>
            <dd className="text-ink">
              {snapshot.profile.id} · {snapshot.profile.version}
            </dd>
          </div>
          <div>
            <dt className="text-ink-muted">Профиль модели</dt>
            <dd className="text-ink">
              {snapshot.model_profile.id} · {snapshot.model_profile.version}
            </dd>
          </div>
          <div>
            <dt className="text-ink-muted">Навык</dt>
            <dd className="text-ink">
              {snapshot.skill.id} · {snapshot.skill.version}
            </dd>
          </div>
          <div>
            <dt className="text-ink-muted">Версия движка</dt>
            <dd className="text-ink">{snapshot.engine_version}</dd>
          </div>
          <div>
            <dt className="text-ink-muted">Создан</dt>
            <dd className="text-ink">{formatDateTime(run.created_at)}</dd>
          </div>
          <div>
            <dt className="text-ink-muted">Завершён</dt>
            <dd className="text-ink">{formatDateTime(run.finished_at)}</dd>
          </div>
        </dl>
      </details>
    </section>
  );
}
