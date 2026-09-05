import { describe, expect, it } from 'vitest';
import type { PublicLimits } from '@/api/generated/model';
import { validateUpload } from './validate-upload';

const limits: PublicLimits = {
  document_upload_max_bytes: 1024,
  max_context_documents: 3,
};

describe('validateUpload (FR-006)', () => {
  it('принимает поддерживаемый формат в пределах лимита', () => {
    expect(validateUpload({ name: 'spec.md', size: 512, type: 'text/markdown' }, limits)).toEqual({ ok: true });
    expect(validateUpload({ name: 'spec.pdf', size: 1024, type: 'application/pdf' }, limits)).toEqual({ ok: true });
  });

  it('принимает файл по расширению, когда браузер не сообщил тип', () => {
    expect(validateUpload({ name: 'spec.md', size: 10, type: '' }, limits)).toEqual({ ok: true });
  });

  it('отклоняет неподдерживаемый формат и называет поддерживаемые', () => {
    const result = validateUpload({ name: 'spec.docx', size: 10, type: 'application/vnd.oasis' }, limits);
    expect(result.ok).toBe(false);
    expect(result.ok === false && result.reason).toMatch(/PDF, Markdown/u);
  });

  it('отклоняет файл больше лимита и называет действующий лимит', () => {
    const result = validateUpload({ name: 'spec.pdf', size: 4096, type: 'application/pdf' }, limits);
    expect(result.ok).toBe(false);
    expect(result.ok === false && result.reason).toMatch(/1 КБ/u);
  });

  it('отклоняет пустой файл', () => {
    expect(validateUpload({ name: 'spec.txt', size: 0, type: 'text/plain' }, limits).ok).toBe(false);
  });
});
