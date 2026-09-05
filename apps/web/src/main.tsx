import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router';
import { AppProviders } from './app/providers';
import { router } from './app/router';
import './styles/index.css';

/**
 * Worker моков включается только по переменной окружения VITE_MSW_SCENARIO.
 * Прикладной код о моках не знает: переключение на реальный backend меняет
 * транспорт, но не компоненты и hooks (принцип III).
 */
function scenarioName(): string | undefined {
  const configured = import.meta.env.VITE_MSW_SCENARIO;
  if (!import.meta.env.DEV) {
    return configured;
  }
  // В dev-сборке сценарий можно переопределить для конкретной страницы: этим
  // пользуются E2E-проверки, чтобы прогонять негативные случаи без перезапуска
  // сервера. В production-сборке переопределение недоступно.
  const injected = (globalThis as unknown as Record<string, string | undefined>).__MSW_SCENARIO__;
  return injected ?? configured;
}

async function startMocks(): Promise<void> {
  const scenario = scenarioName();
  if (!scenario) {
    return;
  }
  const { createWorker } = await import('./mocks/browser');
  await createWorker(scenario).start({ onUnhandledRequest: 'bypass', quiet: true });
}

async function bootstrap(): Promise<void> {
  await startMocks();
  const container = document.getElementById('root');
  if (!container) {
    throw new Error('Не найден корневой элемент приложения');
  }
  createRoot(container).render(
    <StrictMode>
      <AppProviders>
        <RouterProvider router={router} />
      </AppProviders>
    </StrictMode>,
  );
}

void bootstrap();
