import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import * as fixtures from '@/mocks/fixtures';
import { renderWithProviders } from '@/test/render';
import { ReportSummary, isTestReport } from './ReportSummary';

describe('ReportSummary', () => {
  it('прямо называет синтетический результат тестовым', () => {
    expect(isTestReport(fixtures.report)).toBe(true);
    renderWithProviders(<ReportSummary report={fixtures.report} reviewedCount={0} />);
    expect(screen.getByText('Тестовый результат')).toBeInTheDocument();
  });

  it('не маркирует семантическое исполнение как тестовое', () => {
    const report = {
      ...fixtures.report,
      limitations: [],
      coverage: { ...fixtures.report.coverage, gaps: [] },
      provenance: {
        ...fixtures.report.provenance,
        model: { ...fixtures.report.provenance.model, provider: 'openai', model: 'gpt-production' },
      },
    };
    expect(isTestReport(report)).toBe(false);
  });
});
