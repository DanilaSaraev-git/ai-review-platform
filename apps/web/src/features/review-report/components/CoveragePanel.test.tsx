import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import type { Coverage } from '@/api/generated/model';
import * as fixtures from '@/mocks/fixtures';
import { renderWithProviders } from '@/test/render';
import { COVERAGE_GAP_TEXT } from '@/lib/error-messages';
import { CoveragePanel } from './CoveragePanel';

describe('CoveragePanel (FR-022)', () => {
  it('показывает полный охват как таковой', () => {
    renderWithProviders(<CoveragePanel coverage={fixtures.report.coverage} />);
    expect(screen.getByText('Полный охват')).toBeInTheDocument();
  });

  it('заметно показывает неполный охват и причины пропусков', () => {
    renderWithProviders(<CoveragePanel coverage={fixtures.reportPartial.coverage} />);

    expect(screen.getByText('Неполный охват')).toBeInTheDocument();
    expect(screen.getByText(/Результат неполный/u)).toBeInTheDocument();
    expect(screen.getByText(/выводы не учитывают его правила/u)).toBeInTheDocument();
  });

  it.each(Object.keys(COVERAGE_GAP_TEXT) as Array<Coverage['gaps'][number]['code']>)(
    'называет причину пропуска с кодом «%s»',
    (code) => {
      const coverage: Coverage = {
        status: 'partial',
        target_fragment_ids: ['fragment-1'],
        reviewed_fragment_ids: [],
        gaps: [{ source_id: 'source-context', fragment_id: null, code, reason: 'Синтетическая причина.' }],
      };
      renderWithProviders(<CoveragePanel coverage={coverage} />);
      expect(screen.getByText(new RegExp(COVERAGE_GAP_TEXT[code], 'u'))).toBeInTheDocument();
    },
  );
});
