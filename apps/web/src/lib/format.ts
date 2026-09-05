/**
 * Форматирование для локали ru-RU (решение R-14).
 * Контракт передаёт время в UTC RFC 3339, поэтому часовой пояс указывается
 * явно: аналитик не должен путать момент решения.
 */
export const LOCALE = 'ru-RU';

// dateStyle/timeStyle нельзя сочетать с timeZoneName, поэтому компоненты
// перечислены явно: часовой пояс обязателен, иначе момент решения читается
// неоднозначно (решение R-14).
const dateTimeFormat = new Intl.DateTimeFormat(LOCALE, {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  timeZoneName: 'short',
});

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return '—';
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? '—' : dateTimeFormat.format(parsed);
}

/** Длительность запуска словами: «4 мин 12 с» (FR-039). */
export function formatDuration(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) {
    return '—';
  }
  const totalSeconds = Math.floor(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours} ч ${minutes} мин`;
  }
  if (minutes > 0) {
    return `${minutes} мин ${seconds} с`;
  }
  return `${seconds} с`;
}

const numberFormat = new Intl.NumberFormat(LOCALE);

export function formatNumber(value: number): string {
  return numberFormat.format(value);
}

/** Размер файла в единицах, понятных при сверке с лимитом (FR-006). */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${formatNumber(bytes)} Б`;
  }
  if (bytes < 1024 * 1024) {
    return `${formatNumber(Math.round(bytes / 1024))} КБ`;
  }
  return `${formatNumber(Math.round((bytes / (1024 * 1024)) * 10) / 10)} МБ`;
}

export function formatMediaType(mediaType: string): string {
  switch (mediaType) {
    case 'application/pdf':
      return 'PDF';
    case 'text/markdown':
      return 'Markdown';
    case 'text/plain':
      return 'Текст';
    default:
      return mediaType;
  }
}
