import { describe, expect, it } from 'vitest';
import type { Document } from '@/api/generated/model';
import * as fixtures from '@/mocks/fixtures';
import { runReadiness } from './run-readiness';

function documentWith(state: Document['extraction_state']): Document {
  return { ...fixtures.mainDocument, extraction_state: state };
}

describe('runReadiness (FR-040)', () => {
  it('разрешает запуск, когда текст извлечён полностью', () => {
    const readiness = runReadiness(documentWith('completed'));
    expect(readiness.canStart).toBe(true);
    expect(readiness.warning).toBeNull();
  });

  it('разрешает запуск при частичном извлечении, но предупреждает о непрочитанной части', () => {
    const readiness = runReadiness(documentWith('partial'));
    expect(readiness.canStart).toBe(true);
    expect(readiness.warning).toMatch(/не будет проверена/u);
  });

  it('запрещает запуск при неудачном извлечении и предлагает следующий шаг', () => {
    const readiness = runReadiness(documentWith('failed'));
    expect(readiness.canStart).toBe(false);
    expect(readiness.blockedReason).toMatch(/извлечь не удалось/u);
    expect(readiness.nextStep).toMatch(/в другом виде/u);
  });

  it('не даёт запустить, пока извлечение не завершилось', () => {
    const readiness = runReadiness(documentWith('pending'));
    expect(readiness.canStart).toBe(false);
    expect(readiness.blockedReason).toMatch(/ещё готовится/u);
  });

  it('не даёт запустить без выбранного документа', () => {
    expect(runReadiness(undefined).canStart).toBe(false);
  });
});
