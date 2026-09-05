# Quickstart: инженерная проверка ML-интеграции

Статус: инженерные T001–T049 завершены на synthetic данных; baseline и выполненные проверки приведены ниже. API-ключ не нужен для mandatory gate. Реальный endpoint не выбран и не проверялся.

## 1. Зафиксировать основу

Принят backend **e0dd57e6bdc2967c49bbcb10ad88d1af315b528f**. Восстановлены обязательные checkpoint **f96a0e3** и mypy-fix **e2039a1**; инженерный runtime зафиксирован коммитом **8ff9cb3**. Alembic head — **20260905_0002**. Сверка исходной истории и ограничения — в [research.md](research.md).

Повторный запуск в изолированной среде (перед запуском проверить, что имена/порты принадлежат этому тестовому запуску или свободны):

```sh
export MVP_PROJECT=review-platform-004-sol-mvp MVP_PORT=18086
export REVIEW_MVP_PROJECT=review-platform-004-sol-mvp REVIEW_MVP_BASE_URL=http://127.0.0.1:18086
export RELEASE_PROJECT=review-platform-004-sol-release RELEASE_DB_PORT=55448
uv sync --frozen --all-packages
make mvp-up
make mvp-smoke
make mvp-restart
make release-check
```

`release-check` самостоятельно создаёт и удаляет только свой изолированный PostgreSQL test project; default `release-check-local` пропускает integration/migration/Compose E2E. Protected-path guard блокирует возврат клиентских и продуктовых материалов. E2E читает `REVIEW_MVP_PROJECT`; default остаётся review-platform-mvp. Существующие операторские `review-platform-mvp_*` volumes в этих командах не используются.

Результаты относятся к полностью реализованному synthetic ML/runtime пути, но не доказывают совместимость или качество реальной модели. При завершении тестовой работы `make mvp-down` с тем же MVP_PROJECT останавливает только собственную среду и сохраняет её данные; `mvp-reset` здесь не используется.

## 2. Mandatory проверки без реальной модели

### Выполнено для полного engineering gate — 2026-09-05

Полный `make release-check` с указанными выше изолированными проектами/портами завершился успешно. Чужой проект `review-platform-004-review-storage` и его PostgreSQL на 55447 не изменялись.

| Suite | Результат |
| --- | --- |
| Contract | 80 passed |
| Core/runtime/CLI unit | 102 passed |
| Security | 12 passed |
| Migration (реальный PostgreSQL 18) | 8 passed |
| Integration | 46 passed |
| E2E | 9 passed / 1 optional skip |

Итого **257 passed / 1 optional skip**. Пропуск — отсутствие заранее доступного local-model endpoint; модель не устанавливалась и не загружалась. Ruff, mypy (103 configured source files), canonical schema/reference/example validation, Orval generation и TypeScript consumer typecheck прошли. Предупреждения зависимостей о deprecated interfaces сохранены; они не являются ошибками gate.

Smoke и restart подтвердили неизменность SHA-256/ETag **bb6f408940658fa261492c89fbfa13b6d96c7a05bf77edc6a4098894cd995ec6** для run `568d79f6-3cb4-4e69-bdcd-5974f5508ede`. Это проверка deterministic Compose и durable restart, не реального ML endpoint.

Synthetic suites покрывают ModelAdapter, exact skill/profile identity, retry/deadline/error policy, review и dialogue mapping, durable attempts, same-key/cancel races, same-turn retry, immutable report, availability, restart ownership/reconciliation, отсутствие limiter, default offline Compose и opt-in Compose с локальным fake provider. Protected-path tests блокируют клиентские и продуктовые файлы. Публичный HTTP v1.0.2 не менялся. Файлы инструкций synthetic package не являются предметным harness; реальные endpoints не вызывались.

```sh
uv run --frozen pytest -q tests/contract/test_ml_fixture_package.py tests/integration/test_fake_model_provider.py tests/contract/test_protected_path_guard.py
```

### Целевые synthetic проверки

```sh
uv run --frozen pytest tests/contract/test_model_adapter_v1.py tests/contract/test_ml_review_output.py tests/contract/test_ml_dialogue_output.py
uv run --frozen pytest packages/review-core/tests/test_ml_execution.py packages/review-runtime/tests/test_ml_model_config.py
uv run --frozen pytest tests/integration/test_ml_review_http.py tests/integration/test_ml_dialogue_http.py tests/integration/test_ml_concurrency.py
uv run --frozen pytest tests/migration/test_ml_migration.py tests/e2e/test_ml_restart.py tests/security/test_ml_boundary.py
```

Integration fixtures используют реальный PostgreSQL по принятому test setup 003; не направлять их на пользовательскую БД. Fake provider слушает только локальный адрес/тестовую Compose network, не обращается наружу. Внешний override для этих тестов не требуется.

| Сценарий | Ожидаемый результат |
| --- | --- |
| Валидный ответ review | Один model POST, один canonical report, точные anchors и фактическая fake-provider provenance |
| Input oversize | Ошибка context_limit, ноль model POST, исходные документы сохранены |
| Unknown/ambiguous quote, неверное coverage или JSON | Ошибка без отчёта; нет auto repair |
| 429 → успех | Две попытки с разными request IDs в одном deadline, один итоговый report |
| Timeout с неизвестным исходом / invalid envelope | Один вызов, безопасная ошибка; следующий вызов только вручную |
| Три удерживаемых вызова | Все три достигают fake provider до освобождения barrier; health/polling читаются в это время |
| Same-key concurrent/replay | Тот же run/turn, ноль дополнительных генераций; different body — 409 |
| Failed dialogue → retry | Прежние turn ID/ordinal/message/count, новая generation attempt |
| Decision/cancel во время сети | Human Decision/cancel сохраняются; поздний ответ не публикует чужое состояние |
| Deadline внутри publish / неизвестный commit outcome | До terminal CAS — rollback success; CAS вовремя допускает bounded commit; неизвестный исход сверяется с durable state |
| Direct CLI при работающем API | Изолированный local storage; API runs не изменены, CLI не требует deployment lock/БД |
| Restart после accept/во время модели/до commit | Нет auto generation; failed interrupted; ручной repeat доступен |
| Restart после commit и смена config | Идентичные report bytes/hash/ETag; старая provenance сохранена |

Time budget тестировать под управляемым clock, не ждать 300 реальных секунд в каждой проверке. Отдельный Compose scenario с уменьшенным test deadline проверяет цепочку proxy/API/provider, timeout и отсутствие блокировки запросов.

## 3. Default и внешний режимы

```sh
make mvp-up
make mvp-smoke
```

Default mode остаётся offline/deterministic. Внешний режим включается оператором после выбора профиля:

```sh
docker compose -f deploy/compose/compose.yaml -f deploy/compose/compose.external-model.yaml up -d
```

До этой команды оператор задаёт exact endpoint/model/profile version, budget, поддерживаемые параметры, availability mode и secret reference согласно [contracts/README.md](contracts/README.md). Значение секрета не помещается в командную строку или tracked config. Создание/проверка реального вызова выполняется отдельным явно запущенным smoke, не startup/readiness.

## 4. Проверка реального endpoint — после выбора

1. Зафиксировать model profile/config digest, model ID/version если доступна, skill digest, engine/backend commits и suite version.
   Для клиентского подключения сначала подтвердить соответствие короткого названия из продуктовой базы точному checkpoint и фактическим serving/budget/JSON/reasoning параметрам. Предположительное соответствие карточке не подставлять в рабочую конфигурацию автоматически.
2. Выполнить optional `model-smoke` через тот же adapter/engine: валидный review и dialogue, endpoint options, budget boundary, JSON/anchors/coverage, фактические latency/usage:

```sh
uv run --frozen review-cli model-smoke \
  --profile /absolute/path/to/model-profile.json \
  --credential /absolute/path/to/model-api-key \
  --fixture tests/fixtures/ml-integration/primary.md \
  --skill skills/review-data-spec \
  --output /absolute/path/to/compatibility-evidence.json
```
3. Записать реальные результаты или явные unsupported/unknown. Fake gate не доказывает качество или совместимость конкретного endpoint; успешный health probe тоже.
4. Клиентские данные использовать только в согласованном контуре. Все клиентские прогоны и производные материалы сохранять в `ai-review-product`; synthetic evidence — в общей тестовой области платформы. Настроечные документы не объявлять независимым контролем.

До выбора endpoint эта проверка имеет статус «не проводилась». Документы не утверждают совместимость целого семейства моделей, экономию или подтверждённое качество замечаний.
