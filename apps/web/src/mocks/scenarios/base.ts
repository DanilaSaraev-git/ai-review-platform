import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import {
  getGetBootstrapMockHandler,
  getGetDocumentMockHandler,
  getListDocumentsMockHandler,
  getListModelProfilesMockHandler,
  getListReviewProfilesMockHandler,
  getListReviewRunsMockHandler,
  getUploadDocumentMockHandler,
} from '@/api/generated/endpoints.msw';
import type { Problem } from '@/api/generated/model';
import * as fixtures from '@/mocks/fixtures';

/**
 * Общие обработчики, одинаковые для всех сценариев.
 *
 * Сгенерированные Orval handlers покрывают успешные ответы. Ответы об ошибках
 * (RFC 9457 problem+json) генератор не порождает, поэтому негативные случаи
 * собираются обычными обработчиками MSW, но с типами из сгенерированной модели.
 */
export const API = '*/v1';

export function problem(status: number, code: string, title: string, detail?: string) {
  const body: Problem = {
    type: `/problems/${code.replace(/_/gu, '-')}`,
    title,
    status,
    detail,
    code,
    request_id: `request-${code}`,
    errors: [],
  };
  return HttpResponse.json(body, { status, headers: { 'Content-Type': 'application/problem+json' } });
}

/** Документ выбирается по идентификатору из синтетического набора. */
const documentsById = () =>
  new Map([
    [fixtures.mainDocument.id, fixtures.mainDocument],
    [fixtures.contextDocument.id, fixtures.contextDocument],
    [fixtures.unreadableDocument.id, fixtures.unreadableDocument],
    [fixtures.partiallyExtractedDocument.id, fixtures.partiallyExtractedDocument],
  ]);

export function baseHandlers(): RequestHandler[] {
  return [
    getGetBootstrapMockHandler(fixtures.bootstrap),
    getListDocumentsMockHandler(fixtures.documentPage),
    getUploadDocumentMockHandler(fixtures.mainDocument),
    getGetDocumentMockHandler(({ params }) => {
      const found = documentsById().get(String(params.documentId));
      return found ?? fixtures.mainDocument;
    }),
    getListReviewProfilesMockHandler({ items: fixtures.reviewProfiles }),
    getListModelProfilesMockHandler({ items: fixtures.modelProfiles }),
    getListReviewRunsMockHandler(fixtures.runPage),

    // Байты исходного документа для просмотрщика фрагмента.
    http.get(`${API}/workspaces/:workspaceId/documents/:documentId/content`, () =>
      HttpResponse.text(fixtures.mainDocumentText, {
        headers: { 'Content-Type': 'text/markdown', ETag: '"synthetic-main-document"' },
      }),
    ),
  ];
}

/**
 * Идентификатор вне настроенного рабочего пространства — обычное несовпадение
 * namespace, а не отказ в доступе (FR-003, принцип IV).
 */
export function namespaceGuard(): RequestHandler {
  return http.all(`${API}/workspaces/:workspaceId/*`, ({ params }) => {
    if (String(params.workspaceId) !== fixtures.workspaceId) {
      return problem(404, 'not_found', 'Ресурс не найден');
    }
    return undefined;
  });
}
