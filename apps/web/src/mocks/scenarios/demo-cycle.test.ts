// @vitest-environment node
import { beforeEach, expect, it, vi } from 'vitest';
import { mockServer } from '../server';
import { syntheticDemo } from '../synthetic-demo';
import { demo } from './demo';
import * as fixtures from '../fixtures';
import type { DocumentFamilyVersion, FindingDialogue, ReviewCycle, ReviewRun } from '@/api/generated/model';
import { apiBaseUrl } from '@/api/http-client';

vi.stubGlobal('location', new URL('http://localhost'));
const storage = new Map<string, string>();
vi.stubGlobal('sessionStorage', { clear: () => storage.clear(), getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value) });
const base = new URL(`${apiBaseUrl()}/v1/workspaces/${fixtures.workspaceId}`, location.origin).href;
const data = syntheticDemo();
async function request(path: string, method = 'GET', body?: object | FormData) {
  return fetch(`${base}${path}`, { method, headers: body instanceof FormData ? { 'Idempotency-Key': crypto.randomUUID() } : { 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() }, body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined });
}
beforeEach(() => { sessionStorage.clear(); mockServer.resetHandlers(...demo(data)); });

it('walks decisions → version 2 → human fixes → completion and restores history after reload', async () => {
  const first = fixtures.runId;
  for (const finding of data.report.findings) {
    const result = await request(`/review-runs/${first}/findings/${finding.id}/decision`, 'PUT', { status: 'confirmed', reason: 'Внесём правки в демоверсию', resolution: null, expected_revision: 0 });
    expect(result.status).toBe(200);
  }
  const form = new FormData(); form.append('file', new File(['synthetic'], 'demo-v2.md', { type: 'text/markdown' }));
  const version = await (await request(`/document-families/${fixtures.documentFamily.id}/versions`, 'POST', form)).json() as DocumentFamilyVersion;
  expect(version.version_number).toBe(2);
  const run = await (await request('/review-runs', 'POST', { document_id: version.document.id, context_document_ids: [], profile: data.report.provenance.execution_snapshot.profile, model_profile: data.report.provenance.execution_snapshot.model_profile, locale: 'ru-RU' })).json() as ReviewRun;
  expect(run.state).toBe('queued');
  const clock = vi.spyOn(Date, 'now').mockReturnValue(Date.now() + 4000);
  expect((await (await request(`/review-runs/${run.id}`)).json()).state).toBe('completed'); clock.mockRestore();
  let cycle = await (await request(`/review-runs/${run.id}/review-cycle`)).json() as ReviewCycle;
  expect(cycle.entries).toHaveLength(2);
  expect((await request(`/review-runs/${run.id}/review-cycle/complete`, 'POST', { expected_revision: cycle.revision })).status).toBe(409);
  for (const entry of cycle.entries) {
    cycle = await (await request(`/review-runs/${run.id}/review-cycle/issues/${entry.issue_id}/resolution`, 'PUT', { status: 'resolved', reason: 'Проверено в исходнике версии 2', expected_revision: entry.resolution.revision })).json() as ReviewCycle;
  }
  expect((await request(`/review-runs/${run.id}/review-cycle/complete`, 'POST', { expected_revision: cycle.revision })).status).toBe(200);
  mockServer.resetHandlers(...demo(data));
  expect((await (await request(`/review-runs/${run.id}/review-cycle`)).json()).completion).toBeTruthy();
  expect((await (await request(`/document-families/${fixtures.documentFamily.id}/versions`)).json()).items).toHaveLength(2);
  expect((await (await request(`/review-runs/${first}/report`)).json()).findings).toHaveLength(2);
  expect((await (await request(`/review-runs/${run.id}/report`)).json()).findings).toHaveLength(0);
});

it('keeps context requests open, records attachments and blocks unsupported API locally', async () => {
  const path = `/review-runs/${fixtures.runId}/findings/${data.report.findings[0]!.id}`;
  await request(`${path}/decision`, 'PUT', { status: 'needs_context', reason: 'Уточним расписание', resolution: null, expected_revision: 0 });
  const dialogue = await (await request(`${path}/dialogue`)).json() as FindingDialogue;
  expect(dialogue.can_send_message).toBe(true);
  const result = await (await request(`${path}/dialogue/turns`, 'POST', { message: 'Вложил регламент', attachment_document_ids: [data.document.id], expected_revision: dialogue.revision })).json() as FindingDialogue;
  expect(result.turns[0]!.attachment_document_ids).toEqual([data.document.id]);
  expect(result.turns[0]!.assistant_response!.content).toContain('Заранее подготовленный ответ');
  expect((await request('/unsupported-model-call', 'POST', {})).status).toBe(503);
});
