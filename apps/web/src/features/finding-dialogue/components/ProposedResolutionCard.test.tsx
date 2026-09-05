import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import * as fixtures from '@/mocks/fixtures';
import { latestProposedResolution, resolutionTextFor } from '../lib/apply-proposed-resolution';
import { ProposedResolutionCard } from './ProposedResolutionCard';

const proposal = fixtures.dialogueOpen.turns[0]!.assistant_response!.proposed_resolution!;

describe('предложенная резолюция (FR-029, SC-007)', () => {
  it('показывает предложение отдельно от решения', () => {
    render(<ProposedResolutionCard proposal={proposal} />);

    expect(screen.getByText(proposal.text)).toBeInTheDocument();
    expect(screen.getByText(proposal.rationale)).toBeInTheDocument();
    expect(screen.getByText(/Решение не сохранится/u)).toBeInTheDocument();
  });

  it('без отдельного действия аналитика ничего не переносит', () => {
    const onUse = vi.fn();
    render(<ProposedResolutionCard proposal={proposal} onUse={onUse} />);

    expect(onUse).not.toHaveBeenCalled();
  });

  it('переносит текст только по явному действию и не сохраняет решение', async () => {
    const user = userEvent.setup();
    const onUse = vi.fn();
    render(<ProposedResolutionCard proposal={proposal} onUse={onUse} />);

    await user.click(screen.getByRole('button', { name: /Использовать предложение/u }));

    expect(onUse).toHaveBeenCalledExactlyOnceWith(proposal.text);
  });

  it('находит последнее предложение в диалоге', () => {
    expect(latestProposedResolution(fixtures.dialogueOpen)).toEqual(proposal);
    expect(resolutionTextFor(latestProposedResolution(fixtures.dialogueOpen))).toBe(proposal.text);
  });

  it('не находит предложения там, где его нет', () => {
    expect(latestProposedResolution(fixtures.dialogueGenerating)).toBeNull();
    expect(resolutionTextFor(null)).toBeNull();
  });
});
