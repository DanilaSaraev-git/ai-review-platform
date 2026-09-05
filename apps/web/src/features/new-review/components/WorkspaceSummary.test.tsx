import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import * as fixtures from '@/mocks/fixtures';
import { renderWithProviders } from '@/test/render';
import { WorkspaceSummary } from './WorkspaceSummary';

describe('WorkspaceSummary (FR-001, FR-002)', () => {
  it('показывает пространство, организацию, атрибуцию и действующие лимиты', () => {
    renderWithProviders(
      <WorkspaceSummary
        workspace={fixtures.bootstrap.workspace}
        actor={fixtures.bootstrap.actor}
        limits={fixtures.bootstrap.limits}
        isLoading={false}
      />,
    );

    expect(screen.getByText(fixtures.bootstrap.workspace.name)).toBeInTheDocument();
    expect(screen.getByText(fixtures.bootstrap.workspace.organization_name)).toBeInTheDocument();
    expect(screen.getByText(fixtures.bootstrap.actor.display_name)).toBeInTheDocument();
    expect(screen.getByText(/файл до/u)).toBeInTheDocument();
    expect(screen.getByText(/контекст до/u)).toBeInTheDocument();
  });

  it('не предлагает вход, выход и смену рабочего пространства', () => {
    renderWithProviders(
      <WorkspaceSummary
        workspace={fixtures.bootstrap.workspace}
        actor={fixtures.bootstrap.actor}
        limits={fixtures.bootstrap.limits}
        isLoading={false}
      />,
    );

    for (const forbidden of [/войти/iu, /выйти/iu, /регистрац/iu, /сменить пространство/iu, /аккаунт/iu]) {
      expect(screen.queryByText(forbidden)).not.toBeInTheDocument();
    }
  });

  it('во время загрузки показывает состояние, а не пустую область', () => {
    renderWithProviders(
      <WorkspaceSummary workspace={undefined} actor={undefined} limits={undefined} isLoading />,
    );
    expect(screen.getByRole('status')).toHaveTextContent(/Загружаем/u);
  });
});
