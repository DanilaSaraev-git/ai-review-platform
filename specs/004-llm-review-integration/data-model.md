# Data Model: операции и попытки ML-исполнения

Статус: проект изменений поверх финального backend 003. [Спецификация](spec.md), [план](plan.md), [baseline](research.md). Схема дерева проблем здесь не определяется.

## Повторное использование хранения 003

| Сущность | Изменение |
| --- | --- |
| model_profile_versions | Immutable payload точного подключения вместо deterministic-заглушки; несколько версий сосуществуют |
| skill_versions | Точная версия, manifest digest и package digest; manifest semantics входят в идентичность новой версии |
| execution_snapshots | Immutable profile/skill/policy; прежние значения не переписываются |
| review_run_executions | Активировать в default flow: один execution на run, claim token/owner, deadline, prepared input digest и safe error |
| review_work_items | Один whole-document item с полным ordered target set; fragment_id становится nullable, item не равен одному фрагменту |
| model_attempts | Запись на каждое сетевое обращение: максимум две на разрешённый автоматический цикл |
| generation_attempts | Логический запуск ответа; ручной retry создаёт следующую ordinal на прежнем turn |
| dialogue_turns | Active generation attempt ID; прежние turn identity/message/ordinal при retry |
| finding_dialogues / finding_states / human_decisions | Актуальное состояние под общими блокировками; human revision и dialogue revision независимы |
| review_reports / artifacts | Прежние immutable bytes/hash/ETag и ограничения целостности |

В review_run_executions добавить типизированный JSON payload: prepared_input_digest, deadline_at, started_at, finished_at, error. Existing lease_token/lease_owner используются как ownership/fencing identity; expiry/heartbeat/requeue workflow не активируется.

## Общая история сетевых попыток

Текущая model_attempts ссылается только на review work item. Расширить на оба вида операций: nullable work_item_id, nullable generation_attempt_id, ровно один владелец по CHECK. Сохранить составные namespace FK. PK заменить на `(organization_id, workspace_id, id)`; добавить раздельные partial unique indexes по owner и ordinal.

Attempt payload: request_id, purpose, input_digest, response_digest и response_size_bytes (число байт, не raw body) при получении, started_at, finished_at, deadline_at, provider_request_id, finish_reason, provider, model, model_version, safe_parameters, usage, latency_ms, error_code, safe_error_message, retry_after_seconds, automatic_retry_allowed, outcome_known.

Неизвестные usage — null; отсутствие ответа не означает нулевой расход. Authorization, ключи, raw provider error и chain-of-thought не сохраняются. Новые служебные сведения не добавляются в HTTP v1.

## Идентичность и атомарность

- Review: run → execution → whole-document work item → model attempt. Replay не создаёт execution.
- Dialogue: dialogue → turn → generation attempt → model attempt. Автоповтор создаёт model attempt внутри generation attempt; ручной retry создаёт generation attempt на том же turn.
- Request ID равен уникальному ID сетевой попытки. Для dialogue work_item_id нормативного запроса — ID generation attempt, а не строка review-only таблицы.
- Idempotency scope: namespace + operation + resource IDs + неизменённый user key. Digest валидированного тела считается прежним codec, включая expected_revision.
- Transaction advisory lock по scope предшествует lookup/insert. Точная строка scope проверяется независимо от hash lock. Replay разрешается до проверок текущего revision/state.
- Claim и terminal writes сравнивают owner token, active attempt ID и разрешённое состояние. Ноль обновлённых строк означает устаревший результат.
- Review publish/cancel блокируют run одинаково. Dialogue prepare/publish/decision используют `dialogue → finding_state → turn/attempt`; сети внутри транзакции нет.

## Жизненный цикл

| Объект | Переходы |
| --- | --- |
| ReviewRun | queued → preparing → reviewing → validating → completed; ошибка → failed; отмена до terminal → cancelled |
| Review execution | accepted → running → completed/failed/cancelled; один claim |
| DialogueTurn | queued → generating → completed/failed; ручной retry failed → queued на том же ID |
| Generation attempt | accepted → running → completed/failed; новая попытка только после failed |
| Model attempt | prepared → sending → succeeded/failed; outcome_known=false для неизвестного исхода |

Невалидный смысловой ответ сохраняет transport outcome отдельно от статуса операции: HTTP 200 не означает completed review. Terminal success CAS после deadline, отмены, прерывания или замены попытки запрещён. Финальный CAS проверяет DB clock и ownership/state под блокировкой непосредственно перед commit; остальная success-транзакция при отказе откатывается. Commit уже допущенного CAS может завершиться в bounded finalization, как определено в plan.md; неизвестный исход commit сверяется с durable state, а не объявляется rollback.

## Снимки и неизменяемость

До первого model call закрепить document/context identities и порядок, prepared fragments, review profile, skill manifest/files, model profile, retry/timeout policy, locale и engine version. Prepared input хранится в существующих review_run_sources.prepared и generation_attempts.value; snapshot ссылается на точные immutable версии. Дополнительные retry/timeout/prepared-input сведения — внутренняя execution metadata, не новые поля публичного ExecutionSnapshot v1. Secret payload не входит в снимок.

Dialogue использует model/skill versions исходного отчёта и актуальный snapshot хода; latest молча не выбирается. Если версия отключена, report читается, новый dialogue/retry получает недоступность. Новое ревью может выбрать другую версию.

Final report provenance описывает успешный вызов, породивший содержание. Usage неуспешного вызова остаётся в его attempt; неполная сумма не выдаётся за полную стоимость операции.

## Startup reconciliation

После exclusive deployment ownership и до readiness идемпотентная процедура переводит нетерминальные execution/turn/attempt в failed с причиной прерывания; пересчитывает dialogue availability по актуальному решению. Генерация не запускается; terminal records не меняются.

После durable report commit сохраняются исходные report/run. Если процесс умер до commit, отчёта по HTTP нет, операция получает failed; возможный unreferenced artifact остаётся под существующей cleanup policy, без нового collector scope.

Direct CLI использует изолированное локальное хранение, не эту deployment-БД. Его запуск не меняет API executions и не участвует в startup reconciliation API.

## Миграция

Новая additive Alembic revision поверх фактического head 003: execution payload, nullable whole-document fragment_id, общий owner model_attempts, active generation attempt pointer, FK и unique indexes. Исторические reports/snapshots/profile payloads не backfill-ятся вымышленной provenance. Legacy rows с отсутствующей ML metadata читаются.

Upgrade проверяется на пустой БД и завершённых данных 003. Downgrade должен явно отклоняться при наличии новых ML records, не представимых в 003; после их отдельного удаления оператором и остановки приложения выполняется обычный downgrade. Автоматического удаления истории или переписывания reports нет.
