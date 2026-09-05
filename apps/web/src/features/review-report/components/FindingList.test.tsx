import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import type { Finding, FindingState } from '@/api/generated/model';
import * as fixtures from '@/mocks/fixtures';
import { renderWithProviders } from '@/test/render';
import { FindingList } from './FindingList';

const states = new Map<string, FindingState>(
  fixtures.findingStates.items.map((item) => [item.finding_id, item]),
);

describe('FindingList (FR-019, FR-023)', () => {
  it('показывает пустой отчёт как содержательный результат, а не ошибку', () => {
    renderWithProviders(<FindingList findings={[]} states={states} runId={fixtures.runId} />);

    expect(screen.getByText('Замечаний не найдено')).toBeInTheDocument();
    expect(screen.getByText(/охват проверки и ограничения/u)).toBeInTheDocument();
  });

  it('сохраняет устойчивый порядок замечаний по ordinal', () => {
    const first = fixtures.report.findings[0]!;
    const second: Finding = { ...first, id: 'second-finding', ordinal: 2, title: 'Второе замечание' };
    const third: Finding = { ...first, id: 'third-finding', ordinal: 3, title: 'Третье замечание' };

    renderWithProviders(
      <FindingList findings={[third, first, second]} states={states} runId={fixtures.runId} />,
    );

    const headings = screen.getAllByRole('heading', { level: 3 }).map((node) => node.textContent ?? '');
    expect(headings[0]).toMatch(/^1\./u);
    expect(headings[1]).toMatch(/^2\./u);
    expect(headings[2]).toMatch(/^3\./u);
  });

  it('показывает статус решения рядом с замечанием', () => {
    renderWithProviders(
      <FindingList findings={fixtures.report.findings} states={states} runId={fixtures.runId} />,
    );
    expect(screen.getByText('Не рассмотрено')).toBeInTheDocument();
  });
});
