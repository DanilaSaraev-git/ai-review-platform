# Implementation Plan: инженерная интеграция LLM

**Branch**: `codex/004-llm-review-integration` | **Date**: 2026-09-05 | **Spec**: [spec.md](spec.md)

## Summary

Подключить ML-путь к backend 003 через нормативный `ModelAdapter v1`. Один review-вызов обрабатывает полный допустимый вход; отдельный dialogue-вызов отвечает на ход. Async coordinator связывает короткие фазы хранения, проверенный навык, модель, валидацию и публикацию. HTTP ждёт результат и возвращает существующие v1 DTO. Очередь и worker не добавляются.

Содержание harness разрабатывается отдельно. Для инженерной приёмки используется синтетический декларативный пакет с двумя операциями. [Контрактная граница](contracts/README.md), [изменения хранения](data-model.md), [baseline и альтернативы](research.md).

## Technical Context

**Language/Version**: Python 3.14; точные версии и `uv.lock` наследуются от финального 003 без обновления стека.

**Primary Dependencies**: FastAPI, AnyIO, HTTPX async; psycopg 3 для существующего sync runtime; SQLAlchemy metadata, Alembic, JSON Schema Draft 2020-12, прежний canonical JSON codec.

**Storage**: нормализованный PostgreSQL и POSIX artifact store из 003, существующие versioned config и execution/attempt tables.

**Testing**: pytest unit/contract/integration/migration/security/E2E; fake HTTP provider и реальный PostgreSQL; проверка реального endpoint отдельно.

**Target Platform**: один локальный API-процесс и прямой CLI, Docker Compose с loopback proxy.

**Performance Goals**: review=300s, dialogue=60s; это предел операции, не обещание скорости модели. Просмотр состояния доступен во время генерации. Лимита числа model calls нет.

**Constraints**: один смысловой вызов; максимум две сетевые попытки только для разрешённых временных отказов. Auth, multi-replica, очередь, worker, автоматическое production recovery и выбор провайдера вне среза.

## Constitution Check

| Правило | Проверка до и после дизайна |
| --- | --- |
| AGENTS.md — единственные общие инструкции | AGENTS/CLAUDE не меняются; симлинк проверяется |
| Код по отдельному поручению | S-32 разрешает начало реализации; текущий срез Setup T001–T002, дальнейшие фазы остаются невыполненными |
| Клиентские материалы отделены | Только synthetic fixtures в общем runtime; клиентские результаты остаются в `ai-review-product` |
| Факты отделены от решений | Ответы пользователя в Clarifications; осмотр кода в research; качество модели не заявляется |
| Числа имеют основание | 300/60 и retry приняты пользователем; параметры endpoint требуют его выбора |
| Сохранение оригиналов | Backend-worktree только читается; отчёты и публичный v1 сохраняются |

Gate пройден до и после дизайна. Исключений из правил нет.

## Архитектура исполнения

```text
HTTP route (await)                     CLI (один anyio.run на команду)
           \                           /
                Async application coordinator
                 1. accept / claim / prepare → sync storage в threadpool
                 2. async engine            → verified skill → ModelAdapter.generate
                 3. validate / publish      → sync validation/storage в threadpool
```

- Общая composition factory находится в review-runtime. API и CLI используют один engine/coordinator с разными storage adapters: API — PostgreSQL/artifact store deployment, direct CLI — прежнее изолированное локальное in-memory хранение с экспортом файлов. CLI не подключается к БД API, не выполняет её startup reconciliation и не требует её ownership lock; может работать одновременно с API. Существующий sync fixture executor подключается через async wrapper и сохраняет offline semantics.
- PostgreSQL connection/transaction создаётся и закрывается внутри одной sync-функции в worker thread, не пересекает await. Парсинг, hashing, validation и файловое I/O также не блокируют event loop; сетевых вызовов под DB-транзакцией нет.
- ML executor напрямую await-ит ModelAdapter. HTTPX client живёт в ASGI lifespan либо в единственном CLI loop; вложенного anyio.run нет.
- Для model transport: `max_connections=None`, `retries=0`, `follow_redirects=False`. Idle keep-alive pool может быть ограничен. Semaphore и очередь слотов отсутствуют; прежний `max_parallel_model_calls=2` не применяется. Обычные ограничения ОС/коротких I/O-фаз не объявляются модельной квотой.
- Принятая операция принадлежит process-lifetime task group; handler ждёт её результат. Disconnect не отменяет генерацию. Это владение coroutine, а не durable очередь. Shutdown ждёт до 30s, затем отменяет текущие задачи с ограниченной записью ошибки; startup закрывает остаточные состояния.

## Review flow

1. Короткая транзакция сериализует idempotency key, проверяет digest/ссылки, сохраняет run, snapshot, источники и execution identity. Replay возвращает ресурс без генерации. Атомарный claim переводит execution в активное состояние ровно один раз.
2. Вне транзакции подготавливаются immutable fragments и точные версии зависимостей. До model call сохраняются prepared input и digest. Полный prompt с резервом ответа проверяется по бюджету профиля. Недоступный основной документ — ошибка; недоступный необязательный контекст — явный gap.
3. Формируется один `GenerationRequest(purpose=review)`. Адаптер возвращает raw text и фактическую metadata; retries принадлежат engine.
4. Проверяются JSON и компактный ответ; сервер назначает ID и вычисляет offsets точных цитат. Ноль или несколько совпадений внутри указанного fragment — validation error, не выбор первого совпадения. Для missing применяется scope, без выдуманной цитаты.
5. После преобразования в skill output и ReviewReport выполняются JSON Schema, semantic validation и канонизация. Coverage — точное разбиение target set; отправка текста модели не означает его проверку и не заполняет coverage автоматически.
6. Artifact подготавливается вне длинной DB-транзакции. Короткая публикация проверяет execution ID, состояние, отсутствие cancel и deadline, затем фиксирует единственный report и terminal status. Failure writes имеют тот же guard. Неуспех единственного вызова означает failed без отчёта; валидный partial допускается только с явными gaps.

## Dialogue flow

1. Сначала idempotency lookup, затем блокировки в порядке `dialogue → finding_state → turn/attempt`: актуальные revision, решение человека и отсутствие другого активного хода читаются внутри транзакции.
2. Новый ход создаёт одну реплику. Retry создаёт generation attempt на прежнем turn_id: ordinal/message/turn_count не меняются. Idempotency scope включает действие и ресурс; префикс `retry:` к user key не добавляется.
3. Вход содержит выбранное замечание, источники, профиль, завершённую историю и текущую реплику ровно один раз. Документы, профиль и реплики — данные. Вся история учитывается в бюджете; скрытой обрезки нет.
4. Генерация и валидация вне транзакции. Публикация адресует точные turn_id и generation_attempt_id, не `turns[-1]`. Ответ модели не пишет Human Decision.
5. Решение человека во время генерации сохраняется. Валидный ответ можно дописать в тот же ход как предложение; can_send_message/blocked_reason пересчитываются по актуальному состоянию, диалог не открывается безусловно.

## Ошибки, сроки и перезапуск

- Автоповтор — после HTTP 429/502/503/504 либо подтверждённого connection failure до отправки. Retry-After принимает секунды и HTTP-date; отсутствующий/невалидный означает 1s. При исчерпании остатка срока повтор не начинается. Иные 5xx без установленной политики безопасного повтора по умолчанию завершают операцию.
- Timeout/разрыв после возможной отправки, invalid envelope/JSON, semantic error, auth/model/context/content error не повторяются автоматически. Публичный retryable обозначает возможность ручного повтора, а не разрешение на auto retry.
- Monotonic deadline начинается при принятии операции; wall-clock deadline сохраняется для DB guard. Подготовка, вызов, delay, validation и подготовка публикации используют единый остаток 300/60s. Внутри sync publish-фазы остаток проверяется между блокирующими участками; lock/statement timeouts пересчитываются по нему. Последнее действие перед commit — guarded terminal CAS с проверкой актуальных owner/state/cancel и DB clock_timestamp() < deadline_at. Если guard не прошёл, вся success-транзакция откатывается.
- Точная граница срока — допуск terminal CAS, а не момент доставки ответа клиенту. Уже допущенный CAS + commit либо запись ошибки завершаются в отдельно ограниченной фазе до 10s; успешный CAS после deadline не разрешён. После CAS до commit нет файлового I/O, model call или дополнительных writes. При неизвестном исходе commit нельзя заявлять rollback: coordinator перечитывает terminal state; при недоступной БД возвращает безопасную ошибку, а startup сверяет durable state. Отмена coroutine не останавливает sync thread: внутри него обязательны deadline/owner guards; зависший поток не считается доказательством failed. Проверяются истечение срока внутри publish до CAS и задержка/потеря ответа commit после CAS.
- До readiness startup помечает нетерминальные executions/generation attempts ошибкой `process_interrupted`; публичная проекция — существующий `internal_error`, безопасное сообщение, retryable=true. Генераций и переписывания terminal records нет.
- Повтор review — новый create-run с новым ключом. Повтор dialogue — существующий retry на том же ходе. Старые reports и completed/failed/cancelled resources остаются доступны.
- Session advisory lock по deployment при старте исключает случайный второй API-процесс. Он защищает startup reconciliation; это ownership guard, не лимитер model calls и не реализация multi-replica recovery.

## Профили и происхождение результатов

Профиль задаёт точный chat URL, provider/model, secret reference, capabilities, structured-output mode, budget и разрешённые параметры; `/v1` не дописывается. Configuration validation, свежая доступность и endpoint compatibility — разные проверки. Детали — в [contracts/README.md](contracts/README.md).

Readiness зависит от локальной конфигурации/БД/артефактов, не от платной генерации. Сетевой availability probe разрешён только при наличии заданного профилем несгенеративного endpoint. Неизвестные version/usage остаются unknown/null.

Attempt history хранит request IDs, hashes, timestamps, safe errors, usage и фактические параметры. Дополнительного журналирования raw prompt/ответов нет; версии и immutable input позволяют восстановить запрос. Старые snapshots/report bytes не пересчитываются при смене профиля.

## Project Structure

### Documentation

В этой feature: spec.md, plan.md, research.md, data-model.md, contracts/README.md, quickstart.md, tasks.md, backlog.md и checklists/requirements.md.

### Source Code

Backend 003 принят из e0dd57e. Ниже — целевая структура ML-реализации; наличие исходного backend не означает готовности перечисленных ML-изменений.

```text
packages/review-core/src/review_core/
  application/execution.py         # async coordinator и storage phase ports
  ports/models.py                  # нормативные ModelAdapter Python types
  review/{engine,prompt,validation}.py
  dialogue/{engine,prompt,validation}.py
packages/review-runtime/src/review_runtime/
  composition.py
  models/{openai_compatible,config,availability}.py
  config/settings.py
  skills/{registry,executor}.py
  postgres/{platform,models/__init__}.py
packages/review-runtime/migrations/versions/
apps/api/src/review_api/
apps/cli/src/review_cli/
deploy/compose/
tests/{contract,integration,e2e,security}/
```

## Порядок реализации

1. Интегрировать окончательный 003, обновить baseline и проверить прежний gate. Затем типы, storage-phase seam, запись попыток и точные versioned config/snapshots/availability; deterministic hardcodes не доживают до первого ML tracer bullet.
2. US1: adapter, fake HTTP provider, один review path и guarded publication.
3. US2: async dialogue, same-turn retry, решения и immutable reports.
4. US3: операторские profile routes и расширенные проверки availability, startup reconciliation, изолированная CLI composition, opt-in egress.
5. Полный gate; реальный endpoint и предметный harness проверяются отдельно.

Задачи и трассировка: [tasks.md](tasks.md). Проверки: [quickstart.md](quickstart.md). Во время подготовки документов runtime и endpoint tests не выполнялись.
