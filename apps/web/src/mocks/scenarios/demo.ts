import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import type { FindingDialogue, HumanDecision } from '@/api/generated/model';
import { apiBaseUrl } from '@/api/http-client';
import { DEMO_REPLY_NOTICE } from '@/app/demo-mode';
import type { DemoPackage } from '@/mocks/demo-package';
import * as fixtures from '@/mocks/fixtures';
import { readState, scopeMockStorage, writeState } from '@/mocks/store';
import { problem } from './base';
import { demoCycle } from './demo-cycle';

/** A prepared review, with browser-local dialogue and decisions, never a model call. */
export function demo(data: DemoPackage): RequestHandler[] {
  const API = `${apiBaseUrl()}/v1`;
  const bootstrap = data.bootstrap ?? fixtures.bootstrap;
  const workspace = bootstrap.workspace.id;
  const base = `${API}/workspaces/${workspace}`;
  scopeMockStorage(`demo-cycle-v1:${data.report.id}:${data.document.sha256}`);
  const dialogues = readState<Record<string, FindingDialogue>>('dialogues', {});
  const decisions = readState<Record<string, HumanDecision>>('decisions', {});
  const turnKeys = readState<Record<string, FindingDialogue>>('turnKeys', {});

  const keyFor = (runId: string, findingId: string) => `${runId}:${findingId}`;
  const hasFinding = (runId: string, findingId: string) =>
    cycle.reportFor(runId)?.findings.some((finding) => finding.id === findingId);
  const decisionFor = (runId: string, findingId: string) =>
    decisions[keyFor(runId, findingId)] ?? { ...fixtures.unreviewedDecision };

  const cycle = demoCycle(base, data, decisionFor);
  const { runs } = cycle;

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
    ...cycle.handlers,
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
    http.get(`${base}/review-runs/:runId/finding-states`, ({ params }) => {
      const runId = String(params.runId);
      if (!runs.some((run) => run.id === runId)) return problem(404, 'not_found', 'Проверка не найдена');
      return HttpResponse.json({ items: cycle.reportFor(runId)!.findings.map((finding) => {
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
      const body = await request.json() as { message: string; expected_revision: number; attachment_document_ids?: string[] };
      if (body.attachment_document_ids?.some(id => !cycle.membership(id))) return problem(404, 'not_found', 'Вложение не найдено');
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
          attachment_document_ids: body.attachment_document_ids ?? [],
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
      const open = decision.status === 'unreviewed' || decision.status === 'needs_context';
      cycle.invalidate(runId);
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
