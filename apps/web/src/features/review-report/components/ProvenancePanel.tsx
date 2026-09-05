import type { ModelExecution } from '@/api/generated/model';

/**
 * Происхождение результата (FR-004, принцип IV).
 *
 * Показываются только безопасные сведения: провайдер, модель, её версия,
 * безопасные параметры и расход токенов. Значения секретов провайдера в
 * интерфейс не попадают — их нет и в контракте, и добавлять их сюда нельзя.
 */
export function ProvenancePanel({ model }: { model: ModelExecution }) {
  const safeParameters = Object.entries(model.safe_parameters ?? {});

  return (
    <section aria-labelledby="provenance-title" className="rounded border border-line bg-surface p-4">
      <h2 id="provenance-title" className="text-sm font-semibold text-ink">
        Чем выполнена проверка
      </h2>
      <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
        <div>
          <dt className="text-ink-muted">Провайдер</dt>
          <dd className="text-ink">{model.provider}</dd>
        </div>
        <div>
          <dt className="text-ink-muted">Модель</dt>
          <dd className="text-ink">
            {model.model} · {model.model_version}
          </dd>
        </div>
        <div>
          <dt className="text-ink-muted">Токенов на входе</dt>
          <dd className="text-ink">{model.usage.input_tokens ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-ink-muted">Токенов на выходе</dt>
          <dd className="text-ink">{model.usage.output_tokens ?? '—'}</dd>
        </div>
      </dl>

      {safeParameters.length > 0 ? (
        <div className="mt-3">
          <h3 className="text-xs font-semibold text-ink">Безопасные параметры</h3>
          <ul className="mt-1 text-xs text-ink-muted">
            {safeParameters.map(([key, value]) => (
              <li key={key}>
                {key}: {String(value)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
