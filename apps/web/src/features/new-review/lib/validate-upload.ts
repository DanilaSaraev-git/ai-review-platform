import type { PublicLimits } from '@/api/generated/model';
import { formatBytes } from '@/lib/format';

/**
 * Проверка файла до загрузки (FR-006).
 * Отклонённый файл не доходит до сервиса, а аналитик сразу видит действующий
 * лимит и перечень поддерживаемых форматов.
 */
export const SUPPORTED_MEDIA_TYPES = ['application/pdf', 'text/markdown', 'text/plain'] as const;

export const SUPPORTED_EXTENSIONS = ['.pdf', '.md', '.txt'] as const;

export const SUPPORTED_FORMATS_TEXT = 'PDF, Markdown (.md) и обычный текст (.txt)';

export interface UploadCandidate {
  name: string;
  size: number;
  type: string;
}

export type UploadValidation = { ok: true } | { ok: false; reason: string };

function hasSupportedExtension(name: string): boolean {
  const lower = name.toLowerCase();
  return SUPPORTED_EXTENSIONS.some((extension) => lower.endsWith(extension));
}

function hasSupportedMediaType(type: string): boolean {
  return (SUPPORTED_MEDIA_TYPES as readonly string[]).includes(type);
}

export function validateUpload(file: UploadCandidate, limits: PublicLimits): UploadValidation {
  // Браузер не всегда сообщает media type для .md, поэтому расширение
  // считается равноправным признаком формата.
  if (!hasSupportedMediaType(file.type) && !hasSupportedExtension(file.name)) {
    return {
      ok: false,
      reason: `Формат не поддерживается. Поддерживаются ${SUPPORTED_FORMATS_TEXT}.`,
    };
  }

  if (file.size <= 0) {
    return { ok: false, reason: 'Файл пуст: проверять нечего.' };
  }

  if (file.size > limits.document_upload_max_bytes) {
    return {
      ok: false,
      reason: `Файл больше лимита ${formatBytes(limits.document_upload_max_bytes)}. Размер файла — ${formatBytes(file.size)}.`,
    };
  }

  return { ok: true };
}
