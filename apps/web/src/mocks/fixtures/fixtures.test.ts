import { readFileSync, readdirSync, statSync } from 'node:fs';
import { basename, join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';
import * as fixtures from './index';

/**
 * Материалы клиента client не переносятся в интерфейс: фикстуры, тесты и
 * демонстрации используют только синтетические данные
 * (FR-038, SC-011, принцип VI).
 *
 * Проверяются признаки самих материалов — имена полей и файлов из документов
 * кейса — и попытки импортировать что-либо из каталога кейса. Упоминание
 * правила в комментарии нарушением не является, поэтому по одному слову с
 * названием клиента не ищем: это давало бы ложные срабатывания на пояснениях.
 */
// В окружении jsdom import.meta.url не является файловым URL, поэтому
// каталог исходников берётся от рабочего каталога пакета.
const SOURCE_ROOT = join(process.cwd(), 'src');

const CLIENT_DATA_MARKERS = [
  /FIELD_TIME_ZONE_SHIFT/u,
  /FIELD_TIMEZONE_CALC/u,
  /Тестовые данные\.pdf/u,
  /Основные моменты документации/u,
  /Шаблоны документации/u,
  /test-data-page-05/u,
];

/** Импорт чего-либо из каталога кейса запрещён (принцип VI, правило линтера). */
const CLIENT_IMPORT = /(?:from|import)\s+['"][^'"]*\/client\//u;

function sourceFiles(directory: string): string[] {
  return readdirSync(directory).flatMap((entry) => {
    const full = join(directory, entry);
    if (entry === 'generated' || entry === 'node_modules') {
      return [];
    }
    if (statSync(full).isDirectory()) {
      return sourceFiles(full);
    }
    return /\.(ts|tsx|css|json|md|txt)$/u.test(entry) ? [full] : [];
  });
}

describe('синтетичность данных интерфейса (FR-038, SC-011)', () => {
  it('в исходниках интерфейса нет данных клиента и импортов из каталога кейса', () => {
    const offenders: string[] = [];

    for (const file of sourceFiles(SOURCE_ROOT)) {
      // Сам сторожевой тест содержит признаки как образцы поиска.
      if (basename(file) === 'fixtures.test.ts') {
        continue;
      }
      const content = readFileSync(file, 'utf8');
      for (const marker of [...CLIENT_DATA_MARKERS, CLIENT_IMPORT]) {
        if (marker.test(content)) {
          offenders.push(`${relative(SOURCE_ROOT, file)} — ${String(marker)}`);
        }
      }
    }

    expect(offenders).toEqual([]);
  });

  it('фикстуры описывают вымышленную организацию', () => {
    expect(fixtures.bootstrap.workspace.organization_name).toBe('Example Data Company');
    expect(fixtures.mainDocument.filename).toBe('synthetic-spec.md');
  });

  it('синтетические документы названы явно', () => {
    for (const document of [
      fixtures.contextDocument,
      fixtures.unreadableDocument,
      fixtures.partiallyExtractedDocument,
    ]) {
      expect(document.filename).toMatch(/^synthetic-/u);
    }
  });
});
