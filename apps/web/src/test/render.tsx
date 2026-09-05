import type { ReactElement, ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createMemoryRouter } from 'react-router';
import { render, type RenderResult } from '@testing-library/react';

/**
 * Общая обвязка компонентных тестов: провайдеры те же, что в приложении,
 * поэтому проверяется настоящее поведение, а не упрощённая копия.
 */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

export function renderWithProviders(ui: ReactElement, initialPath = '/'): RenderResult {
  const queryClient = createTestQueryClient();
  const router = createMemoryRouter([{ path: '*', element: ui }], { initialEntries: [initialPath] });

  function Wrapper({ children }: { children?: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }

  return render(<RouterProvider router={router} />, { wrapper: Wrapper });
}

export function renderWithQueryClient(ui: ReactElement, queryClient = createTestQueryClient()): RenderResult {
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}
