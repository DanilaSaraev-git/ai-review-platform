import { useGetBootstrap } from '@/api/generated/endpoints';
import type { Actor, PublicLimits, Workspace } from '@/api/generated/model';

/**
 * Настроенное рабочее пространство, действующее лицо и публичные лимиты (FR-001).
 *
 * workspace.id — единственный источник workspaceId во всех URL: аналитик его
 * не вводит и не выбирает (принцип IV). Данные не меняются в течение сессии,
 * поэтому кэшируются надолго.
 */
export interface BootstrapState {
  actor: Actor | undefined;
  workspace: Workspace | undefined;
  limits: PublicLimits | undefined;
  workspaceId: string;
  isLoading: boolean;
  error: unknown;
}

export function useBootstrap(): BootstrapState {
  const query = useGetBootstrap({
    query: {
      staleTime: Number.POSITIVE_INFINITY,
      gcTime: Number.POSITIVE_INFINITY,
      refetchOnWindowFocus: false,
    },
  });

  const bootstrap = query.data;

  return {
    actor: bootstrap?.actor,
    workspace: bootstrap?.workspace,
    limits: bootstrap?.limits,
    workspaceId: bootstrap?.workspace.id ?? '',
    isLoading: query.isPending,
    error: query.error,
  };
}
