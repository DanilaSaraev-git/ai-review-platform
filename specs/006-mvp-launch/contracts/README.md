# Interfaces: 006

## HTTP v1

[Канонический OpenAPI](../../../contracts/review-platform/v1/openapi.yaml) остаётся источником DTO; Orval генерируется перед сборкой. Новые публичные endpoint/поля не планируются. Ревизии, idempotency, model_unavailable и immutable report сохраняют прежний смысл.

## Web interaction contract

- Existing /new, /runs/:runId, report, finding и dialogue URLs остаются открываемыми напрямую.
- Выбор finding и dialogue не убирает документ на desktop.
- Отчёт кэшируется отдельно от mutable finding/dialogue state.
- Model unavailable запрещает запуск с понятной причиной; synthetic режим включается только явно для проверки.
- Вторичные metadata доступны через раскрытие; допустимость следующего хода определяется сервером.

## Operator contract

Deployment owner определяет точный CLI в tools/ops и документирует команды в docs/operations. Обязательные операции: release, preflight, backup, isolated restore, rollback, certificate renewal, model connection. Операции должны возвращать ненулевой exit code при ошибке; secrets не принимаются literal аргументами и не выводятся. Production restore требует явно названной цели; обычная проверка восстановления изолирована. Gateway закрывает также API/docs/artifacts; открытым может остаться только certificate challenge/redirect.
