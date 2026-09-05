/**
 * Разбор RFC 9457 problem+json в одном месте.
 * Отображение выбирается по коду, а не по серверной строке (решение R-11).
 * 404 — обычное отсутствие ресурса в namespace настроенного рабочего
 * пространства, без семантики доступа (FR-003, принцип IV).
 */
export interface ApiProblem {
  type: string;
  title: string;
  status: number;
  detail?: string;
  instance?: string;
  code: string;
  requestId?: string;
  errors: Array<{ field: string; message: string }>;
}

export class ApiProblemError extends Error {
  readonly problem: ApiProblem;

  constructor(problem: ApiProblem) {
    super(problem.title);
    this.name = 'ApiProblemError';
    this.problem = problem;
  }

  get status(): number {
    return this.problem.status;
  }

  get code(): string {
    return this.problem.code;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export async function parseProblem(response: Response): Promise<ApiProblem> {
  const fallback: ApiProblem = {
    type: 'about:blank',
    title: 'Запрос не выполнен',
    status: response.status,
    code: 'unknown_error',
    errors: [],
  };

  try {
    const body: unknown = await response.json();
    if (!isRecord(body)) {
      return fallback;
    }
    return {
      type: typeof body.type === 'string' ? body.type : fallback.type,
      title: typeof body.title === 'string' ? body.title : fallback.title,
      status: typeof body.status === 'number' ? body.status : response.status,
      detail: typeof body.detail === 'string' ? body.detail : undefined,
      instance: typeof body.instance === 'string' ? body.instance : undefined,
      code: typeof body.code === 'string' ? body.code : fallback.code,
      requestId: typeof body.request_id === 'string' ? body.request_id : undefined,
      errors: Array.isArray(body.errors)
        ? body.errors.filter(isRecord).map((item) => ({
            field: String(item.field ?? ''),
            message: String(item.message ?? ''),
          }))
        : [],
    };
  } catch {
    return fallback;
  }
}

export function isProblem(error: unknown): error is ApiProblemError {
  return error instanceof ApiProblemError;
}

/** Идентификатор не принадлежит настроенному рабочему пространству либо ресурса нет. */
export function isNotFound(error: unknown): boolean {
  return isProblem(error) && error.status === 404;
}

/** Действие выполнено поверх устаревшей ревизии решения или диалога (FR-027, FR-036). */
export function isRevisionConflict(error: unknown): boolean {
  return isProblem(error) && error.status === 409 && error.code === 'revision_conflict';
}

/** Тот же Idempotency-Key отправлен с другим телом запроса. */
export function isIdempotencyConflict(error: unknown): boolean {
  return isProblem(error) && error.status === 409 && error.code === 'idempotency_key_reuse';
}

/** Отчёт ещё не опубликован: запуск не завершился успешно (FR-018). */
export function isReportUnavailable(error: unknown): boolean {
  return isProblem(error) && error.status === 409 && !isRevisionConflict(error) && !isIdempotencyConflict(error);
}

/** Файл превышает действующие лимиты рабочего пространства (FR-006). */
export function isPayloadTooLarge(error: unknown): boolean {
  return isProblem(error) && error.status === 413;
}
