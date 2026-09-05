import { describe, expect, it } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import {
  IMMUTABLE_REPORT_OPTIONS,
  dialogueKey,
  findingStatesKey,
  invalidateAfterDecision,
  invalidateAfterDialogueTurn,
  reportKey,
} from '@/api/query-keys';
import * as fixtures from '@/mocks/fixtures';

/**
 * Ключевая проверка принципа V: решения и диалог не могут изменить отчёт.
 *
 * Неизменяемость обеспечена устройством кэша, а не дисциплиной разработчика,
 * поэтому проверяется именно она: после мутаций ключ отчёта не помечается
 * устаревшим и его данные остаются прежними (FR-018, FR-037).
 */
describe('кэш отчёта (FR-018, FR-037, принцип V)', () => {
  const workspaceId = fixtures.workspaceId;
  const runId = fixtures.runId;
  const findingId = fixtures.findingId;

  function primedClient(): QueryClient {
    const client = new QueryClient();
    client.setQueryData(reportKey(workspaceId, runId), fixtures.report);
    client.setQueryData(findingStatesKey(workspaceId, runId), fixtures.findingStates);
    client.setQueryData(dialogueKey(workspaceId, runId, findingId), fixtures.dialogueOpen);
    return client;
  }

  it('ключ отчёта отделён от ключей изменяемых состояний', () => {
    expect(reportKey(workspaceId, runId)).not.toEqual(findingStatesKey(workspaceId, runId));
    expect(reportKey(workspaceId, runId)).not.toEqual(dialogueKey(workspaceId, runId, findingId));
  });

  it('сохранение решения не инвалидирует отчёт', async () => {
    const client = primedClient();
    await invalidateAfterDecision(client, workspaceId, runId, findingId);

    const reportState = client.getQueryState(reportKey(workspaceId, runId));
    const statesState = client.getQueryState(findingStatesKey(workspaceId, runId));

    expect(reportState?.isInvalidated).toBe(false);
    expect(statesState?.isInvalidated).toBe(true);
    expect(client.getQueryData(reportKey(workspaceId, runId))).toEqual(fixtures.report);
  });

  it('ход диалога не инвалидирует отчёт', async () => {
    const client = primedClient();
    await invalidateAfterDialogueTurn(client, workspaceId, runId, findingId);

    expect(client.getQueryState(reportKey(workspaceId, runId))?.isInvalidated).toBe(false);
    expect(client.getQueryState(dialogueKey(workspaceId, runId, findingId))?.isInvalidated).toBe(true);
    expect(client.getQueryData(reportKey(workspaceId, runId))).toEqual(fixtures.report);
  });

  it('отчёт не устаревает и не перезапрашивается автоматически', () => {
    expect(IMMUTABLE_REPORT_OPTIONS.staleTime).toBe(Number.POSITIVE_INFINITY);
    expect(IMMUTABLE_REPORT_OPTIONS.refetchOnMount).toBe(false);
    expect(IMMUTABLE_REPORT_OPTIONS.refetchOnWindowFocus).toBe(false);
  });
});
