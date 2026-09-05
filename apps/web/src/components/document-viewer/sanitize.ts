/**
 * Содержимое документа выводится как данные (FR-043).
 *
 * Загруженный файл — недоверенный ввод: он может содержать разметку, скрипты
 * или указания, адресованные модели. Интерфейс показывает их как текст, не
 * исполняет и не меняет из-за них своё поведение. Поэтому содержимое никогда
 * не попадает в innerHTML: оно разбивается на строки и рендерится текстовыми
 * узлами, а функции ниже — явная граница этого правила.
 */

/** Экранирование на случай, когда содержимое всё же попадает в HTML-строку. */
export function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export interface DocumentLine {
  /** Номер строки с единицы: он же адрес фрагмента в TextLocation. */
  number: number;
  text: string;
}

/**
 * Разбор содержимого документа в строки для текстового представления.
 * Управляющие символы удаляются, разметка остаётся видимым текстом.
 */
export function toDocumentLines(content: string): DocumentLine[] {
  return content
    .replaceAll('\r\n', '\n')
    .replaceAll('\r', '\n')
    .split('\n')
    .map((text, index) => ({
      number: index + 1,
      // Удаляются только непечатаемые управляющие символы; теги и подобная
      // разметка сохраняются как текст, потому что это содержимое документа.
      text: stripControlCharacters(text),
    }));
}

function stripControlCharacters(value: string): string {
  let result = '';
  for (const char of value) {
    const code = char.codePointAt(0) ?? 0;
    const isControl = code < 0x20 || (code >= 0x7f && code <= 0x9f);
    result += isControl && char !== '\t' ? ' ' : char;
  }
  return result;
}
