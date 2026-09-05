import type { RequestHandler } from 'msw';
import { getGetDocumentMockHandler, getUploadDocumentMockHandler } from '@/api/generated/endpoints.msw';
import * as fixtures from '@/mocks/fixtures';
import { happyPath } from './happy-path';

/**
 * Загруженный документ не удалось извлечь: запуск запрещён с причиной,
 * заведомо обречённый запуск не создаётся (FR-040, US1-9).
 */
export function documentExtractionFailed(): RequestHandler[] {
  return [
    getUploadDocumentMockHandler(fixtures.unreadableDocument),
    getGetDocumentMockHandler(fixtures.unreadableDocument),
    ...happyPath(),
  ];
}
