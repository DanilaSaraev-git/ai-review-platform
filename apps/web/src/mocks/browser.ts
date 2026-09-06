import { setupWorker } from 'msw/browser';
import { handlersFor } from './scenarios';
import { loadDemoPackage } from './demo-package';

/**
 * Worker моков для браузера. Включается только по переменной окружения:
 * при пустом VITE_MSW_SCENARIO приложение идёт в реальный backend, и это
 * единственное отличие — код компонентов и hooks не меняется (принцип III).
 */
export async function createWorker(scenario: string) {
  const data = scenario === 'demo' ? await loadDemoPackage() : undefined;
  return setupWorker(...handlersFor(scenario, data));
}
