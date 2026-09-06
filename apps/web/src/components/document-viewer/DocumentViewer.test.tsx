import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import * as fixtures from '@/mocks/fixtures';
import { DocumentViewer } from './index';

describe('основной документ', () => {
  it('привязка к контексту не подменяет основной документ и не подсвечивает совпавший текст', async () => {
    const original = fixtures.report.findings[0]!;
    const finding = { ...original, anchors: original.anchors.map((anchor) => ({ ...anchor, document_id: fixtures.contextDocument.id })) };
    const { container } = render(<DocumentViewer workspaceId={fixtures.workspaceId} document={fixtures.mainDocument} finding={finding} />);
    expect(await screen.findByText('Обновление витрины выполняется регулярно.')).toBeInTheDocument();
    expect(screen.getByText('Цитата из источника контекста')).toBeInTheDocument();
    expect(container.querySelector('[data-highlighted="true"]')).toBeNull();
  });
});
