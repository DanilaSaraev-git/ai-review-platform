const EXPLANATIONS: Record<string, string> = {
  exact_unique: 'Найдено однозначное соответствие замечаний.',
  candidate_only: 'Есть похожие замечания. Связь должен проверить аналитик.',
  no_correspondence: 'Соответствие прежним замечаниям не найдено.',
  not_in_current_report: 'В текущем результате замечание не обнаружено. Это не подтверждает исправление.',
  manual_link: 'Замечания связаны аналитиком.',
  manual_unlink: 'Аналитик разъединил замечания. Требуется отдельная оценка.',
  review_conditions_changed: 'Условия проверки изменились. Прежние оценки требуют пересмотра; исчезновение замечаний не установлено.',
  review_coverage_incomplete: 'Документ проверен не полностью. Отсутствие замечания не подтверждает его устранение.',
  comparison_failed: 'Сравнение не удалось завершить. Основной отчёт сохранён; сравнение можно повторить.',
};

/** Known machine codes become UI copy; server-authored explanations remain readable. */
export function comparisonText(value: string): string {
  return EXPLANATIONS[value] ?? (/^[a-z][a-z0-9_]*$/u.test(value)
    ? 'Для этого результата есть дополнительное ограничение. Проверьте замечание вручную.'
    : value);
}
