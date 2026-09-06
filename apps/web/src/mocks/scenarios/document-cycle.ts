import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import { getCompareReviewCycleMockHandler, getCreateReviewRunMockHandler, getDownloadReviewPdfMockHandler, getGetDocumentFamilyMockHandler, getGetDocumentMockHandler, getGetDocumentVersionFamilyMockHandler, getGetReviewCycleMockHandler, getGetReviewReportMockHandler, getGetReviewRunMockHandler, getListDocumentFamiliesMockHandler, getListDocumentFamilyRunsMockHandler, getListDocumentFamilyVersionsMockHandler, getPutIssueResolutionMockHandler, getPutReviewCycleLinkMockHandler, getUploadDocumentVersionMockHandler } from '@/api/generated/endpoints.msw';
import type { CreateReviewRun, CycleEntry, DocumentFamilyVersion, PutIssueResolution, PutReviewCycleLink, ReviewCycle, ReviewRun } from '@/api/generated/model';
import * as fixtures from '@/mocks/fixtures';
import { readState, writeState } from '@/mocks/store';
import { API, problem } from './base';
import { happyPath } from './happy-path';

const id = (group: string, number: number) => `${group}-0000-4000-8000-${String(number).padStart(12, '0')}`;
const currentRunId = id('60000000', 2);
const title = (number: number) => ['Не задано расписание обновления', 'Не описано удаление данных', 'Нет обработки пустого источника', 'Не определён ключ записи', 'Не проверен срок хранения', 'Повторно отсутствует часовой пояс'][number - 1]!;

/** Six synthetic issues demonstrate independent comparison and human-fix states. */
export const cycleExample: ReviewCycle = {
  ...fixtures.persistingCycle,
  run_id: currentRunId,
  document_id: id('40000000', 2),
  version_number: 2,
  entries: (['persisting', 'new', 'not_detected', 'uncertain', 'not_checked', 'reappeared'] as const).map((status, index): CycleEntry => {
    const number = index + 1;
    return {
      ...fixtures.persistingCycle.entries[0]!,
      issue_id: id('91000000', number),
      origin_run_id: status === 'new' ? currentRunId : fixtures.runId,
      origin_finding_id: id('80000000', number),
      previous_run_id: status === 'new' ? null : fixtures.runId,
      previous_finding_id: status === 'new' ? null : id('80000000', number),
      current_finding_id: ['not_detected', 'not_checked'].includes(status) ? null : id('80000000', number),
      status,
      match_basis: { persisting: 'Замечание, источники и условия проверки неизменны.', new: 'Соответствие прежним проблемам не найдено.', not_detected: 'В полном сопоставимом результате проблема не обнаружена.', uncertain: 'Есть похожая проблема; связь требует проверки аналитиком.', not_checked: 'Эта часть документа не вошла в проверку.', reappeared: 'Проблема обнаружена после отсутствия в предыдущей версии.' }[status],
      decision_carried: status === 'persisting',
      previous_decision: ['persisting', 'reappeared'].includes(status) ? fixtures.decision : null,
      resolution: { ...fixtures.persistingCycle.entries[0]!.resolution },
    };
  }),
};

export function documentCycle(): RequestHandler[] {
  let cycle = readState<ReviewCycle>('cycle-v1', cycleExample);
  const versions = readState<DocumentFamilyVersion[]>('cycle-versions', [{ ...fixtures.documentFamilyVersion, version_number: 2, document: { ...fixtures.mainDocument, id: id('40000000', 2), filename: 'synthetic-spec-v2.md' } }, fixtures.documentFamilyVersion]);
  const runs = readState<ReviewRun[]>('cycle-runs', [{ ...fixtures.runCompleted, id: currentRunId, document_id: versions[0]!.document.id }, fixtures.runCompleted]);
  const keys = new Map<string, ReviewRun | DocumentFamilyVersion>();
  const contents = readState<Record<string, string>>('cycle-contents', {});
  const persist = () => writeState('cycle-v1', cycle);
  return [
    getListDocumentFamiliesMockHandler(() => ({ items: [{ ...fixtures.documentFamily, latest_version_number: versions[0]!.version_number, latest_document_id: versions[0]!.document.id }], next_cursor: null })),
    getGetDocumentFamilyMockHandler(() => ({ ...fixtures.documentFamily, latest_version_number: versions[0]!.version_number, latest_document_id: versions[0]!.document.id })),
    getListDocumentFamilyVersionsMockHandler(() => ({ items: versions, next_cursor: null })),
    getListDocumentFamilyRunsMockHandler(() => ({ items: runs, next_cursor: null })),
    getGetDocumentVersionFamilyMockHandler(({ params }) => versions.find((version) => version.document.id === params.documentId) ?? fixtures.documentFamilyVersion),
    getGetDocumentMockHandler(({ params }) => versions.find((version) => version.document.id === params.documentId)?.document ?? fixtures.mainDocument),
    http.get(`${API}/workspaces/:workspaceId/documents/:documentId/content`, ({ params }) => HttpResponse.text(contents[String(params.documentId)] ?? fixtures.mainDocumentText, { headers: { 'Content-Type': 'text/markdown' } })),
    getUploadDocumentVersionMockHandler(async ({ request }) => {
      const key = request.headers.get('Idempotency-Key')!;
      const prior = keys.get(key);
      if (prior && 'version_number' in prior) return prior;
      const data = await request.formData();
      const file = data.get('file') as File;
      const version = { ...fixtures.documentFamilyVersion, version_number: versions.length + 1, document: { ...fixtures.mainDocument, id: id('40000000', versions.length + 1), filename: file.name } };
      versions.unshift(version);
      contents[version.document.id] = await file.text();
      writeState('cycle-contents', contents);
      keys.set(key, version);
      writeState('cycle-versions', versions);
      return version;
    }),
    getCreateReviewRunMockHandler(async ({ request }) => {
      const key = request.headers.get('Idempotency-Key')!;
      const prior = keys.get(key);
      if (prior && 'state' in prior) return prior;
      const input = await request.json() as CreateReviewRun;
      const run: ReviewRun = { ...fixtures.runCompleted, id: id('60000000', runs.length + 1), document_id: input.document_id, context_document_ids: input.context_document_ids, locale: input.locale };
      keys.set(key, run);
      runs.unshift(run);
      writeState('cycle-runs', runs);
      return run;
    }),
    getGetReviewRunMockHandler(({ params }) => runs.find((run) => run.id === params.runId) ?? fixtures.runCompleted),
    getGetReviewReportMockHandler(({ params }) => ({ ...fixtures.report, run_id: String(params.runId), findings: [1, 2, 3, 4, 5, 6].filter((number) => params.runId === fixtures.runId || ![3, 5].includes(number)).map((number) => ({ ...fixtures.report.findings[0]!, id: id('80000000', number), ordinal: number, title: title(number) })) })),
    getGetReviewCycleMockHandler(({ params }) => ({ ...cycle, run_id: String(params.runId) })),
    getCompareReviewCycleMockHandler(() => { cycle = { ...cycle, revision: cycle.revision + 1 }; persist(); return cycle; }),
    http.put(`${API}/workspaces/:workspaceId/review-runs/:runId/review-cycle/issues/:issueId/resolution`, async ({ request, params }) => {
      const input = await request.clone().json() as PutIssueResolution;
      const entry = cycle.entries.find((item) => item.issue_id === params.issueId);
      if (entry?.resolution.revision !== input.expected_revision) return problem(409, 'revision_conflict', 'Версия исправления изменилась');
      return undefined;
    }),
    getPutIssueResolutionMockHandler(async ({ request, params }) => {
      const input = await request.json() as PutIssueResolution;
      cycle = { ...cycle, revision: cycle.revision + 1, entries: cycle.entries.map((entry) => entry.issue_id !== params.issueId ? entry : { ...entry, resolution: { status: input.status, reason: input.reason, revision: entry.resolution.revision + 1, actor: fixtures.actor, decided_at: '2026-09-06T12:00:00Z' } }) };
      persist();
      return cycle;
    }),
    http.put(`${API}/workspaces/:workspaceId/review-runs/:runId/review-cycle/links/:findingId`, async ({ request, params }) => {
      const input = await request.clone().json() as PutReviewCycleLink;
      const target = cycle.entries.find((item) => item.issue_id === input.previous_issue_id);
      if (input.expected_revision !== cycle.revision || (target?.current_finding_id && target.current_finding_id !== params.findingId)) return problem(409, 'revision_conflict', 'Связь уже занята');
      return undefined;
    }),
    getPutReviewCycleLinkMockHandler(async ({ request, params }) => {
      const input = await request.json() as PutReviewCycleLink;
      const source = cycle.entries.find((entry) => entry.current_finding_id === params.findingId)!;
      if (input.previous_issue_id) {
        cycle = { ...cycle, entries: cycle.entries.filter((entry) => entry.issue_id !== source.issue_id).map((entry) => entry.issue_id !== input.previous_issue_id ? entry : { ...entry, current_finding_id: String(params.findingId), status: 'persisting', decision_carried: false }) };
      } else {
        cycle = { ...cycle, entries: [...cycle.entries.map((entry) => entry !== source ? entry : { ...entry, current_finding_id: null, status: 'uncertain' as const }), { ...source, issue_id: crypto.randomUUID(), origin_run_id: String(params.runId), previous_run_id: null, previous_finding_id: null, previous_decision: null, decision_carried: false, status: 'new' }] };
      }
      cycle = { ...cycle, revision: cycle.revision + 1 }; persist(); return cycle;
    }),
    getDownloadReviewPdfMockHandler(new TextEncoder().encode('%PDF-1.4\n% Synthetic Numbat export\n%%EOF').buffer),
    ...happyPath(),
  ];
}
