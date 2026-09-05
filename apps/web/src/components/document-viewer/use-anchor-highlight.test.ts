import { describe, expect, it } from 'vitest';
import type { Finding } from '@/api/generated/model';
import * as fixtures from '@/mocks/fixtures';
import { toDocumentLines } from './sanitize';
import { NO_ANCHOR_TEXT, UNMATCHED_TEXT, matchAnchor } from './use-anchor-highlight';

const lines = toDocumentLines(fixtures.mainDocumentText);
const baseFinding = fixtures.report.findings[0]!;

describe('matchAnchor (FR-021, SC-003)', () => {
  it('находит текстовый фрагмент по строкам TextLocation', () => {
    const finding: Finding = {
      ...baseFinding,
      anchors: [
        {
          ...baseFinding.anchors[0]!,
          quote: 'Обновление витрины выполняется регулярно.',
          location: { kind: 'text', line_start: 3, line_end: 3, char_start: 0, char_end: 41 },
        },
      ],
    };

    const match = matchAnchor(finding, lines);
    expect(match.matched).toBe(true);
    expect(match.kind).toBe('text');
    if (match.kind === 'text') {
      expect(match.lineStart).toBe(3);
    }
  });

  it('переходит к странице и координатам для PdfLocation', () => {
    const finding: Finding = {
      ...baseFinding,
      anchors: [
        {
          ...baseFinding.anchors[0]!,
          location: { kind: 'pdf', page: 5, rects: [[0.1, 0.2, 0.9, 0.3]], table: null, row: null },
        },
      ],
    };

    const match = matchAnchor(finding, lines);
    expect(match.kind).toBe('pdf');
    if (match.kind === 'pdf') {
      expect(match.page).toBe(5);
      expect(match.rects).toHaveLength(1);
    }
  });

  it('сообщает о несопоставленном фрагменте вместо произвольной подсветки', () => {
    const finding: Finding = {
      ...baseFinding,
      anchors: [
        {
          ...baseFinding.anchors[0]!,
          quote: 'Такой строки в документе нет',
          location: { kind: 'text', line_start: 3, line_end: 3, char_start: 0, char_end: 10 },
        },
      ],
    };

    const match = matchAnchor(finding, lines);
    expect(match.matched).toBe(false);
    expect(match.kind).toBe('unmatched');
    if (match.kind === 'unmatched') {
      expect(match.reason).toBe(UNMATCHED_TEXT);
    }
  });

  it('обрабатывает замечание вида missing без привязок как штатный случай', () => {
    const finding: Finding = {
      ...baseFinding,
      kind: 'missing',
      anchors: [],
      scope: ['source-main-lines-1-3'],
    };

    const match = matchAnchor(finding, lines);
    expect(match.kind).toBe('no-anchor');
    if (match.kind === 'no-anchor') {
      expect(match.reason).toBe(NO_ANCHOR_TEXT);
      expect(match.scope).toEqual(['source-main-lines-1-3']);
    }
  });

  it('сообщает о несопоставлении, когда указанных строк нет в документе', () => {
    const finding: Finding = {
      ...baseFinding,
      anchors: [
        {
          ...baseFinding.anchors[0]!,
          location: { kind: 'text', line_start: 900, line_end: 901, char_start: 0, char_end: 5 },
        },
      ],
    };

    expect(matchAnchor(finding, lines).kind).toBe('unmatched');
  });
});
