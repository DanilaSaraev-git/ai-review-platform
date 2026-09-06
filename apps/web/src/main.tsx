import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router';
import { AppProviders } from './app/providers';
import { router } from './app/router';
import './styles/index.css';
import { appBaseUrl, isDemoMode } from './app/demo-mode';

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
  const worker = await createWorker(scenario);
  await worker.start({
    serviceWorker: { url: `${appBaseUrl}mockServiceWorker.js`, options: { scope: appBaseUrl } },
    onUnhandledRequest(request, print) {
      if (isDemoMode && /\/(?:api|v1)(?:\/|$)/u.test(new URL(request.url).pathname)) print.error();
    },
    quiet: true,
  });
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

void bootstrap().catch(() => {
  const container = document.getElementById('root');
  if (!container) return;
  createRoot(container).render(
    <main className="mx-auto max-w-xl p-6">
      <h1 className="text-lg font-semibold">{isDemoMode ? 'Деморежим недоступен' : 'Не удалось открыть приложение'}</h1>
      <p className="mt-3 text-sm">{isDemoMode ? 'Не удалось загрузить демонстрационные материалы или запустить деморежим. Модель не вызывалась.' : 'Обновите страницу и повторите попытку.'}</p>
      <button className="mt-4 text-sm font-semibold text-accent underline" onClick={() => window.location.reload()}>Повторить</button>
    </main>,
  );
});
