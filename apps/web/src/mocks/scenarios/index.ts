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
import { historyPagination } from './history-pagination';
import { historyError } from './history-error';
import { reportErrorRetry } from './report-error-retry';
import { modelUnconfigured } from './model-unconfigured';
import { reportLong } from './report-long';
import { persistentDocument } from './persistent-document';
import { pdfDocument } from './pdf-document';
import { demo } from './demo';
import type { DemoPackage } from '@/mocks/demo-package';

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
  'history-pagination': historyPagination,
  'history-error': historyError,
  'report-error-retry': reportErrorRetry,
  'model-unconfigured': modelUnconfigured,
  'report-long': reportLong,
  'persistent-document': persistentDocument,
  'pdf-document': pdfDocument,
} as const;

export type ScenarioName = keyof typeof scenarios | 'demo';

export const DEFAULT_SCENARIO = 'happy-path';

export function isScenarioName(value: string): value is ScenarioName {
  return value === 'demo' || value in scenarios;
}

export function handlersFor(name: string = DEFAULT_SCENARIO, data?: DemoPackage): RequestHandler[] {
  if (name === 'demo') {
    if (!data) throw new Error('Демонстрационные материалы не загружены.');
    return demo(data);
  }
  const scenario = name in scenarios ? scenarios[name as keyof typeof scenarios] : scenarios[DEFAULT_SCENARIO];
  return scenario();
}
