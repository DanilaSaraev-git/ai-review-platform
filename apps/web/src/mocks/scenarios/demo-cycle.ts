import { http, HttpResponse } from 'msw';
import type { CreateReviewRun, DocumentFamily, DocumentFamilyVersion, HumanDecision, PutIssueResolution, ReviewCycle, ReviewReport, ReviewRun } from '@/api/generated/model';
import type { DemoPackage } from '../demo-package';
import * as fixtures from '../fixtures';
import { readState, writeState } from '../store';
import { demoText } from '@/app/demo-files';
import { problem } from './base';

/** Tab-local workflow simulation. All report changes are scripted, never inferred. */
export function demoCycle(base: string, data: DemoPackage, decisionFor: (run: string, finding: string) => HumanDecision) {
  const now = () => new Date().toISOString();
  const actor = (data.bootstrap ?? fixtures.bootstrap).actor;
  const firstFamily = { ...fixtures.documentFamily, name: 'Демо — витрина обращений', latest_document_id: data.document.id };
  const versions = readState<DocumentFamilyVersion[]>('versions', [{ ...fixtures.documentFamilyVersion, document: data.document }]);
  const families = readState<DocumentFamily[]>('families', [firstFamily]);
  const runs = readState<ReviewRun[]>('runs', [{ ...fixtures.runCompleted, document_id: data.document.id, execution_snapshot: data.report.provenance.execution_snapshot }]);
  const reports = readState<Record<string, ReviewReport>>('reports', { [fixtures.runId]: { ...data.report, run_id: fixtures.runId } });
  const cycles = readState<Record<string, ReviewCycle>>('cycles', {});
  const keys = readState<Record<string, string>>('keys', {});
  const save = () => { writeState('versions', versions); writeState('families', families); writeState('runs', runs); writeState('reports', reports); writeState('cycles', cycles); writeState('keys', keys); };
  const membership = (id: string) => versions.find(v => v.document.id === id);
  const familyRuns = (id: string) => runs.filter(r => membership(r.document_id)?.family_id === id);
  const reportFor = (id: string) => reports[id];
  const runFor = (id: string) => {
    const run = runs.find(r => r.id === id);
    if (!run || run.state === 'completed') return run;
    const elapsed = Date.now() - Date.parse(run.created_at);
    if (elapsed >= 3000) {
      Object.assign(run, { state: 'completed', report_available: true, finished_at: now(), progress: { percent: 100, message: 'Демонстрационный разбор готов. Модель не вызывалась.' } }); save();
    } else {
      run.state = elapsed < 1000 ? 'preparing' : 'reviewing';
      run.progress = { percent: elapsed < 1000 ? 20 : 65, message: 'Показываем этапы демонстрационной проверки…' };
    }
    return run;
  };
  function cycleFor(id: string): ReviewCycle {
    if (cycles[id]) return cycles[id];
    const version = membership(runs.find(r => r.id === id)!.document_id)!;
    const siblings = familyRuns(version.family_id);
    const previous = siblings[siblings.findIndex(r => r.id === id) + 1];
    const entries = previous ? cycleFor(previous.id).entries.map(e => ({ ...e, current_finding_id: null, previous_run_id: previous.id, previous_finding_id: e.current_finding_id ?? e.previous_finding_id, status: 'not_detected' as const, previous_decision: e.current_finding_id ? decisionFor(previous.id, e.current_finding_id) : e.previous_decision, decision_carried: false, match_basis: 'Демосценарий: в новой версии расписание и срок хранения заданы явно.' })) : reportFor(id)!.findings.map(f => ({ ...fixtures.firstCycle.entries[0]!, issue_id: crypto.randomUUID(), origin_run_id: id, origin_finding_id: f.id, current_finding_id: f.id }));
    cycles[id] = { ...fixtures.firstCycle, run_id: id, family_id: version.family_id, document_id: version.document.id, version_number: version.version_number, baseline_run_id: previous?.id ?? null, compared_at: now(), entries, completion: null };
    save(); return cycles[id];
  }
  function invalidate(id: string) { const cycle = cycles[id]; if (cycle?.completion) { cycle.completion = null; cycle.revision++; save(); } }
  async function upload(request: Request, familyId?: string) {
    const key = `upload:${request.headers.get('Idempotency-Key') ?? crypto.randomUUID()}`;
    if (keys[key]) return membership(keys[key])!;
    const file = (await request.formData()).get('file') as File;
    const number = familyId ? Math.max(...versions.filter(v => v.family_id === familyId).map(v => v.version_number)) + 1 : 1;
    // Keep only the selected filename. The preview always uses synthetic text.
    const document = { ...data.document, id: crypto.randomUUID(), filename: file.name, media_type: 'text/markdown' as const, size_bytes: new TextEncoder().encode(demoText(number)).length, created_at: now() };
    const version = { ...fixtures.documentFamilyVersion, family_id: familyId ?? crypto.randomUUID(), version_number: number, document };
    versions.unshift(version);
    const family = families.find(f => f.id === familyId);
    if (family) Object.assign(family, { latest_document_id: document.id, latest_version_number: number });
    else families.unshift({ ...firstFamily, id: version.family_id, name: file.name, created_at: now(), latest_document_id: document.id });
    keys[key] = document.id; save(); return version;
  }
  const missing = () => problem(404, 'not_found', 'Демонстрационная проверка не найдена');
  return { runs, reportFor, membership, invalidate, handlers: [
    http.get(`${base}/documents`, () => HttpResponse.json({ items: versions.map(v => v.document), next_cursor: null })),
    http.post(`${base}/documents`, async ({ request }) => HttpResponse.json((await upload(request)).document, { status: 201 })),
    http.get(`${base}/documents/:documentId`, ({ params }) => membership(String(params.documentId)) ? HttpResponse.json(membership(String(params.documentId))!.document) : missing()),
    http.get(`${base}/documents/:documentId/content`, ({ params }) => { const version = membership(String(params.documentId)); return version ? HttpResponse.text(demoText(version.version_number), { headers: { 'Content-Type': 'text/markdown' } }) : missing(); }),
    http.get(`${base}/documents/:documentId/family`, ({ params }) => membership(String(params.documentId)) ? HttpResponse.json(membership(String(params.documentId))!) : missing()),
    http.get(`${base}/document-families`, () => HttpResponse.json({ items: families.filter(f => familyRuns(f.id).length), next_cursor: null })),
    http.get(`${base}/document-families/:familyId`, ({ params }) => { const family = families.find(f => f.id === params.familyId); return family ? HttpResponse.json(family) : missing(); }),
    http.get(`${base}/document-families/:familyId/versions`, ({ params }) => HttpResponse.json({ items: versions.filter(v => v.family_id === params.familyId), next_cursor: null })),
    http.post(`${base}/document-families/:familyId/versions`, async ({ params, request }) => families.some(f => f.id === params.familyId) ? HttpResponse.json(await upload(request, String(params.familyId)), { status: 201 }) : missing()),
    http.get(`${base}/document-families/:familyId/review-runs`, ({ params }) => HttpResponse.json({ items: familyRuns(String(params.familyId)).map(r => runFor(r.id)), next_cursor: null })),
    http.post(`${base}/review-runs`, async ({ request }) => {
      const key = `run:${request.headers.get('Idempotency-Key')}`;
      if (keys[key]) return HttpResponse.json(runFor(keys[key]), { status: 202 });
      const input = await request.json() as CreateReviewRun;
      const version = membership(input.document_id);
      if (!version) return missing();
      const run: ReviewRun = { ...fixtures.runQueued, id: crypto.randomUUID(), document_id: input.document_id, context_document_ids: input.context_document_ids, locale: input.locale, execution_snapshot: data.report.provenance.execution_snapshot, created_at: now(), started_at: now() };
      runs.unshift(run); keys[key] = run.id;
      reports[run.id] = { ...data.report, id: crypto.randomUUID(), run_id: run.id, created_at: now(), findings: version.version_number === 1 ? data.report.findings.map(f => ({ ...f, anchors: f.anchors.map(a => ({ ...a, document_id: input.document_id, source_name: version.document.filename })) })) : [], summary: version.version_number === 1 ? data.report.summary : 'Согласованные правки внесены в демонстрационную версию. Подтвердите исправление прежних замечаний.' };
      cycleFor(run.id); save(); return HttpResponse.json(run, { status: 202 });
    }),
    http.get(`${base}/review-runs`, () => HttpResponse.json({ items: runs.map(r => runFor(r.id)), next_cursor: null })),
    http.get(`${base}/review-runs/:runId`, ({ params }) => runFor(String(params.runId)) ? HttpResponse.json(runFor(String(params.runId))!) : missing()),
    http.get(`${base}/review-runs/:runId/report`, ({ params }) => runFor(String(params.runId))?.report_available ? HttpResponse.json(reportFor(String(params.runId))) : missing()),
    http.get(`${base}/review-runs/:runId/review-cycle`, ({ params }) => runFor(String(params.runId)) ? HttpResponse.json(cycleFor(String(params.runId))) : missing()),
    http.post(`${base}/review-runs/:runId/review-cycle/compare`, async ({ params, request }) => {
      if (!runFor(String(params.runId))) return missing();
      const cycle = cycleFor(String(params.runId)); const body = await request.json() as { expected_revision: number };
      if (body.expected_revision !== cycle.revision) return problem(409, 'revision_conflict', 'Состояние изменилось');
      cycle.revision++; save(); return HttpResponse.json(cycle);
    }),
    http.put(`${base}/review-runs/:runId/review-cycle/issues/:issueId/resolution`, async ({ params, request }) => {
      if (!runFor(String(params.runId))) return missing();
      const cycle = cycleFor(String(params.runId)); const entry = cycle.entries.find(e => e.issue_id === params.issueId);
      const body = await request.json() as PutIssueResolution;
      if (!entry || body.expected_revision !== entry.resolution.revision) return problem(409, 'revision_conflict', 'Состояние изменилось');
      entry.resolution = { status: body.status, reason: body.reason, revision: entry.resolution.revision + 1, actor, decided_at: now() };
      cycle.completion = null; cycle.revision++; save(); return HttpResponse.json(cycle);
    }),
    http.post(`${base}/review-runs/:runId/review-cycle/complete`, async ({ params, request }) => {
      const id = String(params.runId); const run = runFor(id);
      if (!run) return missing();
      const cycle = cycleFor(id); const body = await request.json() as { expected_revision: number };
      if (body.expected_revision !== cycle.revision) return problem(409, 'revision_conflict', 'Состояние изменилось');
      const open = reportFor(id)!.findings.some(f => decisionFor(id, f.id).status !== 'rejected') || cycle.entries.some(e => !e.current_finding_id && e.resolution.status !== 'resolved' && e.previous_decision?.status !== 'rejected');
      if (run.state !== 'completed' || open) return problem(409, 'open_questions', 'Сначала разберите открытые вопросы');
      cycle.completion = { completed_at: now(), actor, state_digest: 'd'.repeat(64) }; cycle.revision++; save(); return HttpResponse.json(cycle);
    }),
  ] };
}
