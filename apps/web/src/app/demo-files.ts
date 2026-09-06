/** Synthetic inputs used only in the browser demo. */
export function demoText(version = 1) {
  return `# Витрина обращений\n\n${version === 1 ? 'Обновление витрины выполняется регулярно.' : 'Обновление витрины выполняется ежедневно в 06:00, Europe/Moscow.'}\n\n${version === 1 ? 'Обращения хранятся в витрине.' : 'Обращения хранятся 90 дней; старые записи удаляются ежедневно после обновления.'}\n`;
}
export function demoFile(version = 1) {
  return new File([demoText(version)], `Демо — витрина обращений v${version}.md`, { type: 'text/markdown' });
}
