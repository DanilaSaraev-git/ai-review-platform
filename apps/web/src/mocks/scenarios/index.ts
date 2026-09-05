import type { RequestHandler } from 'msw';
import { happyPath } from './happy-path';
import { runFailed } from './run-failed';
import { runStalled } from './run-stalled';
import { documentExtractionFailed } from './document-extraction-failed';
import { reportPartial } from './report-partial';
import { contextPartial } from './context-partial';
import { emptyReport } from './empty-report';
import { notFound } from './not-found';
import { decisionConflict } from './decision-conflict';
import { dialogueGenerating } from './dialogue-generating';
import { dialogueFailed } from './dialogue-failed';
import { dialogueConflict } from './dialogue-conflict';

/**
 * Реестр именованных сценариев моков (contracts/msw-scenarios.md).
 * Сценарий выбирается переменной окружения VITE_MSW_SCENARIO и определяет
 * только ответы сетевого слоя: компоненты и hooks о моках не знают (принцип III).
 */
export const scenarios = {
  'happy-path': happyPath,
  'run-failed': runFailed,
  'run-stalled': runStalled,
  'document-extraction-failed': documentExtractionFailed,
  'report-partial': reportPartial,
  'context-partial': contextPartial,
  'empty-report': emptyReport,
  'not-found': notFound,
  'decision-conflict': decisionConflict,
  'dialogue-generating': dialogueGenerating,
  'dialogue-failed': dialogueFailed,
  'dialogue-conflict': dialogueConflict,
} as const;

export type ScenarioName = keyof typeof scenarios;

export const DEFAULT_SCENARIO: ScenarioName = 'happy-path';

export function isScenarioName(value: string): value is ScenarioName {
  return value in scenarios;
}

export function handlersFor(name: string = DEFAULT_SCENARIO): RequestHandler[] {
  const scenario = isScenarioName(name) ? scenarios[name] : scenarios[DEFAULT_SCENARIO];
  return scenario();
}
