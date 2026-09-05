import type { EvidenceAnchor, Finding } from '@/api/generated/model';
import type { DocumentLine } from './sanitize';

/**
 * Связывание замечания с фрагментом исходного документа (FR-021, SC-003).
 *
 * Возможны три исхода, и все три показываются честно:
 *  - фрагмент найден и подсвечивается;
 *  - у замечания вида missing привязок нет вовсе — это штатный случай
 *    контракта, показывается проверенная область;
 *  - цитата не сопоставилась с отрисованным фрагментом — сообщается прямо,
 *    произвольное место документа не подсвечивается.
 */
export type AnchorMatch =
  | { kind: 'text'; lineStart: number; lineEnd: number; quote: string; matched: true }
  | { kind: 'pdf'; page: number; rects: number[][]; quote: string; matched: true }
  | { kind: 'unmatched'; quote: string; matched: false; reason: string }
  | { kind: 'no-anchor'; matched: false; reason: string; scope: readonly string[] };

export const UNMATCHED_TEXT = 'Фрагмент не удалось сопоставить с документом: показываем замечание без подсветки.';

export const NO_ANCHOR_TEXT =
  'У этого замечания нет цитаты: оно говорит об отсутствующем требовании. Ниже — проверенная область.';

export function primaryAnchor(finding: Finding): EvidenceAnchor | undefined {
  return finding.anchors[0];
}

export function matchAnchor(finding: Finding, lines: readonly DocumentLine[]): AnchorMatch {
  const anchor = primaryAnchor(finding);

  if (!anchor) {
    return { kind: 'no-anchor', matched: false, reason: NO_ANCHOR_TEXT, scope: finding.scope };
  }

  const location = anchor.location;

  if (location.kind === 'pdf') {
    return {
      kind: 'pdf',
      page: location.page,
      rects: location.rects.map((rect) => [...rect]),
      quote: anchor.quote,
      matched: true,
    };
  }

  const selected = lines.filter(
    (line) => line.number >= location.line_start && line.number <= location.line_end,
  );

  if (selected.length === 0) {
    return { kind: 'unmatched', matched: false, quote: anchor.quote, reason: UNMATCHED_TEXT };
  }

  const normalizedQuote = anchor.quote.trim();
  const found = selected.some((line) => line.text.includes(normalizedQuote)) ||
    selected.map((line) => line.text).join('\n').includes(normalizedQuote);

  if (!found) {
    return { kind: 'unmatched', matched: false, quote: anchor.quote, reason: UNMATCHED_TEXT };
  }

  return {
    kind: 'text',
    lineStart: location.line_start,
    lineEnd: location.line_end,
    quote: anchor.quote,
    matched: true,
  };
}
