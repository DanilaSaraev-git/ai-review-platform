import { ApiProblemError, parseProblem } from './errors';
import { idempotencyKeyFor, requestIntent } from './idempotency';

/**
 * Единственная точка выхода в сеть. Отвечает за базовый URL, заголовок
 * Idempotency-Key для создающих операций и разбор application/problem+json.
 * Сгенерированный клиент вызывает только её, поэтому переключение с MSW на
 * реальный backend не затрагивает компоненты и hooks (принципы II и III).
 *
 * Ответ, отличный от 2xx, выбрасывается исключением ApiProblemError: успешная
 * ветка возвращает только полезную нагрузку, и типам не приходится описывать
 * ошибочные варианты.
 */

/**
 * Операции, для которых контракт требует Idempotency-Key: создание запуска,
 * ход диалога и повтор хода. Загрузка документа его не требует.
 */
const IDEMPOTENT_PATHS = /\/(review-runs|turns|retry)$/u;

export function apiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? '/api';
}

function needsIdempotencyKey(pathname: string, method: string): boolean {
  return method.toUpperCase() === 'POST' && IDEMPOTENT_PATHS.test(pathname);
}

async function readBody(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return undefined;
  }
  const contentType = response.headers.get('Content-Type') ?? '';
  if (contentType.includes('json')) {
    return response.json();
  }
  if (contentType.startsWith('text/')) {
    return response.text();
  }
  return response.blob();
}

export async function httpClient<T>(url: string, options: RequestInit = {}): Promise<T> {
  const absolute = url.startsWith('http') ? url : `${apiBaseUrl()}${url}`;
  const pathname = new URL(absolute, globalThis.location?.origin ?? 'http://localhost').pathname;
  const method = options.method ?? 'GET';
  const headers = new Headers(options.headers);

  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }

  // Ключ вырабатывается по намерению пользователя: путь плюс тело запроса
  // (решение R-05). Одно и то же намерение — тот же ключ, поэтому двойное
  // нажатие и повтор после разрыва связи не создают второй запуск (FR-012).
  // Изменившееся тело — другое намерение и другой ключ.
  if (needsIdempotencyKey(pathname, method) && !headers.has('Idempotency-Key')) {
    headers.set('Idempotency-Key', idempotencyKeyFor(requestIntent(method, pathname, options.body)));
  }

  const response = await fetch(absolute, { ...options, headers });

  if (!response.ok) {
    throw new ApiProblemError(await parseProblem(response));
  }

  return (await readBody(response)) as T;
}

export default httpClient;
