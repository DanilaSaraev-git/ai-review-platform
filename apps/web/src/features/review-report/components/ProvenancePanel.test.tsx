import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import * as fixtures from '@/mocks/fixtures';
import { ProvenancePanel } from './ProvenancePanel';

const model = fixtures.report.provenance.model;

describe('ProvenancePanel (FR-004, принцип IV)', () => {
  it('показывает провайдера, модель, версию и расход токенов', () => {
    render(<ProvenancePanel model={model} />);

    expect(screen.getByText(model.provider)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(model.model_version, 'u'))).toBeInTheDocument();
    expect(screen.getByText(String(model.usage.input_tokens))).toBeInTheDocument();
  });

  it('показывает только безопасные параметры', () => {
    render(<ProvenancePanel model={model} />);
    expect(screen.getByText(/temperature: 0/u)).toBeInTheDocument();
  });

  it('не выводит значений, похожих на секреты провайдера', () => {
    const { container } = render(<ProvenancePanel model={model} />);
    const text = container.textContent ?? '';

    for (const forbidden of [/api[_-]?key/iu, /secret/iu, /token[_-]?value/iu, /Bearer /u, /sk-/u]) {
      expect(text).not.toMatch(forbidden);
    }
  });
});
