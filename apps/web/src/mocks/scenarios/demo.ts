import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import type { FindingDialogue, HumanDecision, ReviewRun } from '@/api/generated/model';
import { apiBaseUrl } from '@/api/http-client';
import { appBaseUrl, DEMO_REPLY_NOTICE } from '@/app/demo-mode';
import type { DemoPackage } from '@/mocks/demo-package';
import * as fixtures from '@/mocks/fixtures';
import { readState, scopeMockStorage, writeState } from '@/mocks/store';
import { problem } from './base';

/** A prepared review, with browser-local dialogue and decisions, never a model call. */
export function demo(data: DemoPackage): RequestHandler[] {
  const API = `${apiBaseUrl()}/v1`;
  const bootstrap = data.bootstrap ?? fixtures.bootstrap;
  const workspace = bootstrap.workspace.id;
  const base = `${API}/workspaces/${workspace}`;
  scopeMockStorage(`demo:${data.report.id}:${data.document.sha256}`);
  const runs = readState<ReviewRun[]>('runs', []);
  const runKeys = readState<Record<string, string>>('runKeys', {});
  const dialogues = readState<Record<string, FindingDialogue>>('dialogues', {});
  const decisions = readState<Record<string, HumanDecision>>('decisions', {});
  const turnKeys = readState<Record<string, FindingDialogue>>('turnKeys', {});

  const keyFor = (runId: string, findingId: string) => `${runId}:${findingId}`;
  const hasFinding = (runId: string, findingId: string) =>
    runs.some((run) => run.id === runId) && data.report.findings.some((finding) => finding.id === findingId);
  const decisionFor = (runId: string, findingId: string) =>
    decisions[keyFor(runId, findingId)] ?? { ...fixtures.unreviewedDecision };

  function dialogueFor(runId: string, findingId: string): FindingDialogue {
    const key = keyFor(runId, findingId);
    if (dialogues[key]) return dialogues[key];
    const dialogue: FindingDialogue = {
      ...data.dialogues[findingId]!,
      id: crypto.randomUUID(),
      run_id: runId,
      finding_id: findingId,
      revision: 0,
      turn_count: 0,
      turns: [],
      state: 'open',
      can_send_message: true,
      blocked_reason: null,
    };
    dialogues[key] = dialogue;
    writeState('dialogues', dialogues);
    return dialogue;
  }

  return [
    http.get(`${API}/bootstrap`, () => HttpResponse.json(bootstrap)),
    http.get(`${base}/documents`, () => HttpResponse.json({ items: [data.document], next_cursor: null })),
    http.post(`${base}/documents`, () => HttpResponse.json(data.document, { status: 201 })),
    http.get(`${base}/documents/:documentId`, ({ params }) =>
      params.documentId === data.document.id ? HttpResponse.json(data.document) : problem(404, 'not_found', 'Документ не найден'),
    ),
    http.get(`${base}/documents/:documentId/content`, async ({ params }) => {
      if (params.documentId !== data.document.id) {
        return problem(404, 'not_found', 'Документ не найден');
      }
      if (data.document.media_type !== 'application/pdf') {
        return HttpResponse.text(data.documentText!, { headers: { 'Content-Type': data.document.media_type } });
      }
      const response = await fetch(`${appBaseUrl}data/document.pdf`, { cache: 'no-store' });
      if (!response.ok) {
        return problem(503, 'demo_document_unavailable', 'Документ демонстрации недоступен');
      }
      return new HttpResponse(await response.arrayBuffer(), { headers: { 'Content-Type': 'application/pdf' } });
    }),
    http.get(`${base}/profiles`, () => HttpResponse.json({ items: [{
      ...fixtures.reviewProfiles[0]!,
      ...data.report.provenance.execution_snapshot.profile,
      name: 'Демонстрационная проверка',
    }] })),
    http.get(`${base}/model-profiles`, () => HttpResponse.json({ items: [{
      ...fixtures.modelProfiles[0]!,
      id: data.report.provenance.execution_snapshot.model_profile.id,
      version: data.report.provenance.execution_snapshot.model_profile.version,
      name: 'Готовый разбор · без модели',
      description: 'Заранее подготовленные замечания и ответы для демонстрационного документа.',
      availability: 'available',
    }] })),
    http.post(`${base}/review-runs`, ({ request }) => {
      const key = request.headers.get('Idempotency-Key') ?? '';
      const replay = runs.find((run) => run.id === runKeys[key]);
      if (replay) return HttpResponse.json(replay, { status: 202 });
      const now = new Date().toISOString();
      const run: ReviewRun = {
        ...fixtures.runCompleted,
        id: crypto.randomUUID(),
        workspace_id: workspace,
        document_id: data.document.id,
        execution_snapshot: data.report.provenance.execution_snapshot,
        created_by: bootstrap.actor,
        created_at: now,
        started_at: now,
        finished_at: now,
        progress: { percent: 100, message: 'Демонстрационный отчёт готов. Модель не вызывалась.' },
      };
      runs.unshift(run);
      runKeys[key] = run.id;
      writeState('runs', runs);
      writeState('runKeys', runKeys);
      return HttpResponse.json(run, { status: 202 });
    }),
    http.get(`${base}/review-runs`, () => HttpResponse.json({ items: runs, next_cursor: null })),
    http.get(`${base}/review-runs/:runId`, ({ params }) => {
      const run = runs.find((item) => item.id === params.runId);
      return run ? HttpResponse.json(run) : problem(404, 'not_found', 'Проверка не найдена');
    }),
    http.get(`${base}/review-runs/:runId/report`, ({ params }) => {
      if (!runs.some((run) => run.id === params.runId)) return problem(404, 'not_found', 'Проверка не найдена');
      return HttpResponse.json({ ...data.report, run_id: String(params.runId) }, {
        headers: { ETag: `"demo-${data.report.id}"` },
      });
    }),
    http.get(`${base}/review-runs/:runId/finding-states`, ({ params }) => {
      const runId = String(params.runId);
      if (!runs.some((run) => run.id === runId)) return problem(404, 'not_found', 'Проверка не найдена');
      return HttpResponse.json({ items: data.report.findings.map((finding) => {
        const dialogue = dialogueFor(runId, finding.id);
        return {
          finding_id: finding.id,
          decision: decisionFor(runId, finding.id),
          dialogue: {
            dialogue_id: dialogue.id,
            revision: dialogue.revision,
            state: dialogue.state,
            turn_count: dialogue.turn_count,
            can_send_message: dialogue.can_send_message,
            blocked_reason: dialogue.blocked_reason,
            policy: dialogue.policy,
          },
        };
      }) });
    }),
    http.get(`${base}/review-runs/:runId/findings/:findingId/dialogue`, ({ params }) => {
      const runId = String(params.runId);
      const findingId = String(params.findingId);
      return hasFinding(runId, findingId)
        ? HttpResponse.json(dialogueFor(runId, findingId))
        : problem(404, 'not_found', 'Замечание не найдено');
    }),
    http.post(`${base}/review-runs/:runId/findings/:findingId/dialogue/turns`, async ({ params, request }) => {
      const runId = String(params.runId);
      const findingId = String(params.findingId);
      if (!hasFinding(runId, findingId)) return problem(404, 'not_found', 'Замечание не найдено');
      const key = keyFor(runId, findingId);
      const turnKey = `${key}:${request.headers.get('Idempotency-Key')}`;
      if (turnKeys[turnKey]) return HttpResponse.json(turnKeys[turnKey], { status: 202 });
      const body = await request.json() as { message: string; expected_revision: number };
      const dialogue = dialogueFor(runId, findingId);
      if (!dialogue.can_send_message) return problem(409, 'dialogue_blocked', 'Диалог закрыт решением человека');
      if (body.expected_revision !== dialogue.revision) return problem(409, 'revision_conflict', 'Версия диалога изменилась');
      const template = data.dialogues[findingId]!.turns[0]!;
      const response = template.assistant_response!;
      const now = new Date().toISOString();
      const updated: FindingDialogue = {
        ...dialogue,
        revision: dialogue.revision + 1,
        turn_count: dialogue.turn_count + 1,
        turns: [...dialogue.turns, {
          ...template,
          id: crypto.randomUUID(),
          ordinal: dialogue.turn_count + 1,
          member_message: body.message,
          actor: bootstrap.actor,
          created_at: now,
          finished_at: now,
          assistant_response: { ...response, content: `${DEMO_REPLY_NOTICE}\n\n${response.content}` },
        }],
      };
      dialogues[key] = updated;
      turnKeys[turnKey] = updated;
      writeState('dialogues', dialogues);
      writeState('turnKeys', turnKeys);
      return HttpResponse.json(updated, { status: 202 });
    }),
    http.put(`${base}/review-runs/:runId/findings/:findingId/decision`, async ({ params, request }) => {
      const runId = String(params.runId);
      const findingId = String(params.findingId);
      if (!hasFinding(runId, findingId)) return problem(404, 'not_found', 'Замечание не найдено');
      const body = await request.json() as Pick<HumanDecision, 'status' | 'reason' | 'resolution'> & { expected_revision: number };
      const current = decisionFor(runId, findingId);
      if (body.expected_revision !== current.revision) return problem(409, 'revision_conflict', 'Версия решения изменилась');
      const decision: HumanDecision = body.status === 'unreviewed'
        ? { ...fixtures.unreviewedDecision, revision: current.revision + 1 }
        : { status: body.status, reason: body.reason, resolution: body.resolution, actor: bootstrap.actor, decided_at: new Date().toISOString(), revision: current.revision + 1 };
      const key = keyFor(runId, findingId);
      const open = decision.status === 'unreviewed';
      decisions[key] = decision;
      dialogues[key] = { ...dialogueFor(runId, findingId), state: open ? 'open' : 'closed', can_send_message: open, blocked_reason: open ? null : 'human_decision_recorded' };
      writeState('decisions', decisions);
      writeState('dialogues', dialogues);
      return HttpResponse.json(decision);
    }),
    // Unsupported API calls fail locally instead of reaching a live service.
    http.all('*', ({ request }) => {
      if (/\/(?:api|v1)(?:\/|$)/u.test(new URL(request.url).pathname)) {
        return problem(503, 'demo_only', 'В деморежиме этот запрос недоступен');
      }
      return undefined;
    }),
  ];
}
