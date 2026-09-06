import familyExample from '@contracts/document-family.json';
import versionExample from '@contracts/document-family-version.json';
import firstCycleExample from '@contracts/review-cycle.first.json';
import persistingCycleExample from '@contracts/review-cycle.persisting.json';
import type { DocumentFamily, DocumentFamilyVersion, ReviewCycle } from '@/api/generated/model';
import bootstrapExample from '@contracts/bootstrap.json';
import documentExample from '@contracts/document.json';
import profilesExample from '@contracts/profiles.json';
import modelProfilesExample from '@contracts/model-profiles.json';
import runQueuedExample from '@contracts/review-run.queued.json';
import runCompletedExample from '@contracts/review-run.completed.json';
import runFailedExample from '@contracts/review-run.failed.json';
import reportExample from '@contracts/report.json';
import reportPartialExample from '@contracts/report.partial.json';
import findingStatesExample from '@contracts/finding-states.json';
import dialogueOpenExample from '@contracts/dialogue.open.json';
import dialogueGeneratingExample from '@contracts/dialogue.generating.json';
import dialogueFailedExample from '@contracts/dialogue.failed.json';
import decisionExample from '@contracts/decision.json';

import type {
  Bootstrap,
  Document,
  DocumentPage,
  FindingDialogue,
  FindingStateList,
  HumanDecision,
  ModelProfile,
  ReviewProfile,
  ReviewReport,
  ReviewRun,
  ReviewRunPage,
} from '@/api/generated/model';

/**
 * Данные моков берутся из канонических примеров контракта
 * contracts/review-platform/v1/examples/http/. Они синтетические и не содержат
 * материалов клиента client (принцип VI, FR-038).
 *
 * Типы приходят только из сгенерированной модели: ручных копий DTO нет
 * (принцип II).
 */
export const bootstrap = bootstrapExample as Bootstrap;
export const mainDocument = documentExample as Document;
export const reviewProfiles = profilesExample.items as ReviewProfile[];
export const modelProfiles = modelProfilesExample.items as ModelProfile[];
export const runQueued = runQueuedExample as ReviewRun;
export const runCompleted = runCompletedExample as ReviewRun;
export const runFailed = runFailedExample as ReviewRun;
export const report = reportExample as ReviewReport;
export const reportPartial = reportPartialExample as ReviewReport;
export const findingStates = findingStatesExample as FindingStateList;
export const dialogueOpen = dialogueOpenExample as FindingDialogue;
export const dialogueGenerating = dialogueGeneratingExample as FindingDialogue;
export const dialogueFailed = dialogueFailedExample as FindingDialogue;
export const decision = decisionExample as HumanDecision;

export const workspaceId = bootstrap.workspace.id;
export const actor = bootstrap.actor;
export const findingId = report.findings[0]!.id;
export const runId = runCompleted.id;

/** Синтетический контекстный документ: правила именования вымышленной команды. */
export const contextDocument: Document = {
  ...mainDocument,
  id: '40000000-0000-4000-8000-000000000002',
  filename: 'synthetic-rules.md',
  media_type: 'text/markdown',
  size_bytes: 640,
  sha256: 'f'.repeat(64),
};

/** Документ, у которого извлечение текста не удалось (FR-040). */
export const unreadableDocument: Document = {
  ...mainDocument,
  id: '40000000-0000-4000-8000-000000000003',
  filename: 'synthetic-scan.pdf',
  media_type: 'application/pdf',
  extraction_state: 'failed',
};

/** Документ, извлечённый частично: запуск остаётся доступным с предупреждением. */
export const partiallyExtractedDocument: Document = {
  ...mainDocument,
  id: '40000000-0000-4000-8000-000000000004',
  filename: 'synthetic-partial.pdf',
  media_type: 'application/pdf',
  extraction_state: 'partial',
};

/** Содержимое синтетического основного документа для просмотрщика. */
export const mainDocumentText = [
  '# Витрина обращений абонентов',
  '',
  'Обновление витрины выполняется регулярно.',
  'Источник — топик обращений; приёмник — витрина отчётности.',
  '',
  '## Поля',
  '',
  '- идентификатор обращения;',
  '- время регистрации;',
  '- регион обслуживания.',
].join('\n');

export const documentPage: DocumentPage = {
  items: [mainDocument],
  next_cursor: null,
};

export const runPage: ReviewRunPage = {
  items: [runCompleted],
  next_cursor: null,
};

export const unreviewedDecision: HumanDecision = {
  status: 'unreviewed',
  revision: 0,
  actor: null,
  reason: null,
  resolution: null,
  decided_at: null,
};

export const documentFamily = familyExample as DocumentFamily;
export const documentFamilyVersion = versionExample as DocumentFamilyVersion;
export const firstCycle = firstCycleExample as ReviewCycle;
export const persistingCycle = persistingCycleExample as ReviewCycle;
