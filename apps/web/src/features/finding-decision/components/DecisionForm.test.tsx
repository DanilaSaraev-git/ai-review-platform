import { describe, expect, it } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import * as fixtures from '@/mocks/fixtures';
import { useScenario } from '@/mocks/server';
import { renderWithQueryClient } from '@/test/render';
import { DecisionForm } from './DecisionForm';

const REASON = 'Расписание действительно нужно согласовать до разработки.';

function renderForm() {
  return renderWithQueryClient(
    <DecisionForm
      workspaceId={fixtures.workspaceId}
      runId={fixtures.runId}
      findingId={fixtures.findingId}
      decision={fixtures.unreviewedDecision}
    />,
  );
}

describe('DecisionForm (FR-025, FR-027, SC-005)', () => {
  it('не сохраняет решение без обоснования и объясняет причину', async () => {
    const user = userEvent.setup();
    renderForm();

    await user.click(screen.getByRole('radio', { name: /Подтверждено/u }));
    await user.click(screen.getByRole('button', { name: /Сохранить решение/u }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/Укажите обоснование/u);
  });

  it('сохраняет решение с обоснованием', async () => {
    const user = userEvent.setup();
    renderForm();

    await user.click(screen.getByRole('radio', { name: /Подтверждено/u }));
    await user.type(screen.getByLabelText(/Обоснование/u), REASON);
    await user.click(screen.getByRole('button', { name: /Сохранить решение/u }));

    expect(await screen.findByText(/Решение сохранено/u)).toBeInTheDocument();
  });

  it('при конфликте ревизии сохраняет введённый текст и предлагает повтор одним действием', async () => {
    useScenario('decision-conflict');
    const user = userEvent.setup();
    renderForm();

    await user.click(screen.getByRole('radio', { name: /Подтверждено/u }));
    await user.type(screen.getByLabelText(/Обоснование/u), REASON);
    await user.click(screen.getByRole('button', { name: /Сохранить решение/u }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/Решение изменилось/u);
    });

    // Введённый текст не потерян (SC-005).
    expect(screen.getByLabelText(/Обоснование/u)).toHaveValue(REASON);
    // Повтор доступен одним действием.
    expect(screen.getByRole('button', { name: /Повторить с актуальной версией/u })).toBeEnabled();
  });

  it('при сбросе в «не рассмотрено» поля обоснования и резолюции недоступны', async () => {
    const user = userEvent.setup();
    renderForm();

    await user.click(screen.getByRole('radio', { name: /Не рассмотрено/u }));

    expect(screen.getByLabelText(/Обоснование/u)).toBeDisabled();
    expect(screen.getByLabelText(/Формулировка резолюции/u)).toBeDisabled();
  });
});
