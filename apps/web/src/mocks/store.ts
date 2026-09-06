/**
 * Хранилище состояния моков, переживающее перезагрузку страницы.
 *
 * Без него сценарий терял бы созданные запуски и сохранённые решения при
 * каждом переходе с перезагрузкой, и проверки вроде «вернуться к запуску
 * позже» (US1-8) или «решение переживает обновление страницы» (US3) были бы
 * невозможны. Это часть слоя моков: приложение о нём не знает.
 */
const memory = new Map<string, string>();
let storagePrefix = `msw:${import.meta.env.BASE_URL}:`;

/** A private demo package cannot reuse decisions from another demo revision. */
export function scopeMockStorage(scope: string): void {
  storagePrefix = `msw:${import.meta.env.BASE_URL}:${scope}:`;
}

function storage(): Pick<Storage, 'getItem' | 'setItem'> {
  try {
    if (typeof sessionStorage !== 'undefined') {
      return sessionStorage;
    }
  } catch {
    // Доступ к sessionStorage может быть запрещён: работаем в памяти.
  }
  return {
    getItem: (key: string) => memory.get(key) ?? null,
    setItem: (key: string, value: string) => void memory.set(key, value),
  };
}

export function readState<T>(key: string, fallback: T): T {
  try {
    const raw = storage().getItem(`${storagePrefix}${key}`);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

export function writeState<T>(key: string, value: T): void {
  try {
    storage().setItem(`${storagePrefix}${key}`, JSON.stringify(value));
  } catch {
    // Хранилище недоступно: состояние останется в пределах загрузки страницы.
  }
}
