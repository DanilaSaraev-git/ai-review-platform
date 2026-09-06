import type { DemoPackage } from './demo-package';
import * as fixtures from './fixtures';
import { demoText } from '@/app/demo-files';

/** No private mounted files are required for the public walkthrough. */
export function syntheticDemo(): DemoPackage {
  const first = fixtures.report.findings[0]!;
  const quote = 'Обращения хранятся в витрине.';
  const second = { ...first, id: '80000000-0000-4000-8000-000000000002', ordinal: 2,
    title: 'Не определён срок хранения обращений',
    problem: 'Не указан срок хранения и порядок удаления старых записей.',
    reason: 'Нельзя проверить объём истории и корректность очистки витрины.',
    question: 'Сколько дней хранить обращения и когда удалять старые записи?',
    anchors: first.anchors.map(a => ({ ...a, quote, quote_start: 0, quote_end: quote.length, location: { kind: 'text' as const, line_start: 5, line_end: 5, char_start: 0, char_end: quote.length } })),
  };
  return {
    schemaVersion: 1, bootstrap: fixtures.bootstrap,
    document: { ...fixtures.mainDocument, filename: 'Демо — витрина обращений v1.md', media_type: 'text/markdown' },
    documentText: demoText(),
    report: { ...fixtures.report, summary: 'Нужно уточнить расписание обновления и срок хранения.', limitations: [], findings: [first, second] },
    dialogues: Object.fromEntries([first, second].map(f => [f.id, { ...fixtures.dialogueOpen, finding_id: f.id, turns: [{ ...fixtures.dialogueOpen.turns[0]!, assistant_response: { ...fixtures.dialogueOpen.turns[0]!.assistant_response!, content: f.id === first.id ? 'Для примера зададим расписание: ежедневно в 06:00 по Europe/Moscow. Примите замечание к доработке и перенесите регламент в следующую версию.' : 'Для примера используем срок 90 дней и ежедневное удаление старых записей после обновления. Примите замечание к доработке и уточните ТЗ.' } }] }])),
  };
}
