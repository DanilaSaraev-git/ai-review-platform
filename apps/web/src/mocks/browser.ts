import { setupWorker } from 'msw/browser';
import { handlersFor } from './scenarios';

/**
 * Worker моков для браузера. Включается только по переменной окружения:
 * при пустом VITE_MSW_SCENARIO приложение идёт в реальный backend, и это
 * единственное отличие — код компонентов и hooks не меняется (принцип III).
 */
export function createWorker(scenario: string) {
  return setupWorker(...handlersFor(scenario));
}
