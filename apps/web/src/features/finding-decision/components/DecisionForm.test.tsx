import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import * as fixtures from '@/mocks/fixtures';
import { getPutFindingDecisionMockHandler } from '@/api/generated/endpoints.msw';
import type { PutFindingDecision } from '@/api/generated/model';
import { mockServer, useScenario } from '@/mocks/server';
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
  it('перенесённая оценка сохраняется с ревизией текущего замечания', async () => {
    let body: PutFindingDecision | undefined;
    mockServer.use(getPutFindingDecisionMockHandler(async ({ request }) => {
      body = await request.json() as PutFindingDecision;
      return { ...fixtures.decision, revision: 1 };
    }));
    renderWithQueryClient(<DecisionForm workspaceId={fixtures.workspaceId} runId={fixtures.runId} findingId={fixtures.findingId} decision={{ ...fixtures.decision, revision: 7 }} expectedRevision={0} />);
    await userEvent.setup().click(screen.getByRole('button', { name: 'Сохранить решение' }));
    await screen.findByText(/Решение сохранено/u);
    expect(body?.expected_revision).toBe(0);
  });

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
    await user.type(screen.getByLabelText(/Обоснование/u), ' Дополнение');
    expect(screen.queryByText(/Решение сохранено/u)).not.toBeInTheDocument();
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

  it('для ещё не рассмотренного замечания не показывает пустые поля', () => {
    renderForm();

    expect(screen.queryByLabelText(/Обоснование/u)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Формулировка резолюции/u)).not.toBeInTheDocument();
  });

  it('принимает сохранённое решение, пришедшее после первого рендера', async () => {
    const user = userEvent.setup();
    function DeferredDecision() {
      const [decision, setDecision] = useState<typeof fixtures.decision | undefined>();
      return (
        <>
          <button type="button" onClick={() => setDecision(fixtures.decision)}>Загрузить состояние</button>
          <DecisionForm
            workspaceId={fixtures.workspaceId}
            runId={fixtures.runId}
            findingId={fixtures.findingId}
            decision={decision}
          />
        </>
      );
    }
    renderWithQueryClient(<DeferredDecision />);

    await user.click(screen.getByRole('button', { name: 'Загрузить состояние' }));
    expect(screen.getByRole('radio', { name: /Подтверждено/u })).toBeChecked();
  });
});
