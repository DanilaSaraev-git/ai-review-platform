import { useState, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { isProblem } from '@/api/errors';

/**
 * Повторять запрос имеет смысл только при сетевом сбое. Ответ с problem+json
 * — это осознанный ответ сервиса (404, 409, 400), и повтор его не исправит,
 * а конфликт ревизии должен дойти до аналитика (FR-027, FR-036).
 */
function shouldRetry(failureCount: number, error: unknown): boolean {
  if (isProblem(error)) {
    return false;
  }
  return failureCount < 2;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: shouldRetry,
        refetchOnWindowFocus: true,
        staleTime: 5_000,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

export function AppProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createQueryClient);
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
