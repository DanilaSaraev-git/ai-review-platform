import { setupServer } from 'msw/node';
import { handlersFor, type ScenarioName } from './scenarios';

/**
 * Серверный вариант MSW для компонентных тестов: те же сценарии, что в dev
 * и E2E, поэтому проверка идёт против одного и того же набора ответов.
 */
export const mockServer = setupServer(...handlersFor('happy-path'));

/** Переключение сценария внутри теста без пересборки окружения. */
export function useScenario(name: ScenarioName): void {
  mockServer.resetHandlers(...handlersFor(name));
}
