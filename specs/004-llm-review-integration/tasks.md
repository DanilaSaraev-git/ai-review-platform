# Tasks: инженерная интеграция LLM

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [contracts](contracts/README.md).

**Статус**: Инженерные T001–T049 завершены на synthetic данных. Backend e0dd57e, checkpoint f96a0e3 и mypy-fix e2039a1 включены в историю рабочей ветки. Проверки с fake provider выполнены по FR-023; реальный endpoint остаётся отдельным подключением после выбора модели.

## Phase 1 — Setup

- [X] T001 Интегрировать окончательный commit backend 003, сверить его итоговый gate/Alembic head и изменения относительно hashes; обновить baseline и команды в `specs/004-llm-review-integration/research.md` и `quickstart.md` до реализации.
- [X] T002 Подготовить synthetic skill package и управляемый fake provider с barriers, scripted errors, usage/finish reason и счётчиком вызовов в `tests/fixtures/ml-integration/` и `tests/integration/fake_model_provider.py`; исключить реальные credentials/клиентские данные.

**Final engineering evidence — 2026-09-05**: Alembic 20260905_0002; mandatory fake-provider, migration, race, restart, CLI and Compose suites пройдены. Реальная модель не устанавливалась, не загружалась и не вызывалась. [Команды и результаты](quickstart.md).

## Phase 2 — Foundational

- [X] T003 Реализовать типизированный нормативный ModelAdapter/GenerationRequest/Result/Capabilities/Error в `packages/review-core/src/review_core/ports/models.py`; перевести `review/prompt.py` и `dialogue/prompt.py` на единый тип, сохранив trusted/untrusted boundary.
- [X] T004 Описать/валидировать immutable model profile payload и ML runtime options в `specs/004-llm-review-integration/contracts/model-profile.v1.schema.json` и `packages/review-runtime/src/review_runtime/config/settings.py`; optional ML config не ломает старый deterministic runtime config.
- [X] T005 Выделить sync admission/claim/prepare/publish/fail методы из `packages/review-runtime/src/review_runtime/postgres/platform.py` и их ports в `packages/review-core/src/review_core/application/execution.py`; connection не пересекает await, I/O не удерживает транзакцию во время модели.
- [X] T006 Добавить execution metadata, whole-document item, общий owner model_attempts и active generation pointer с CHECK/FK/unique constraints в `packages/review-runtime/src/review_runtime/postgres/models/__init__.py` и новой Alembic revision в `packages/review-runtime/migrations/versions/` по data-model.md.
- [X] T007 Проверить upgrade empty/003 history, сохранение report bytes и отказ downgrade с несовместимой ML-историей в `tests/migration/test_ml_migration.py`.
- [X] T008 Реализовать async coordinator, operation deadline, ownership/attempt guards и process-owned execution lifetime в `packages/review-core/src/review_core/application/execution.py`; terminal cleanup bounded, disconnect не равен cancel, специального model limiter нет.
- [X] T009 Реализовать единую retry/error policy с максимумом двух попыток и Retry-After в `packages/review-core/src/review_core/application/model_retry.py`; покрыть virtual clock, auth/context/timeout/invalid JSON и unknown outcome в `packages/review-core/tests/test_ml_execution.py`.
- [X] T010 Подключить exact skill inventory/manifest digest, engine requirements и capability validation в `packages/review-runtime/src/review_runtime/skills/registry.py` и `executor.py`; legacy skill snapshots остаются читаемыми.
- [X] T011 Реализовать и проверить immutable model/skill config seed и точный snapshot вместо deterministic hardcodes в `packages/review-runtime/src/review_runtime/postgres/platform.py` и `packages/review-runtime/src/review_runtime/models/config.py`; сохранить чтение прежних snapshots.
- [X] T012 Реализовать profile-driven non-generative probes, manual observations, expiry и outcome updates с базовыми unit tests в `packages/review-runtime/src/review_runtime/models/availability.py`; /models не обязателен, native structured output не угадывается.

**Checkpoint**: определены исполняемые типы/состояния и проверяемый synthetic input; ни один внешний вызов ещё не требуется.

## Phase 3 — US1: первоначальное ревью (P1)

**Independent test**: synthetic document → fake model → валидный immutable report; невалидный ответ → failed без report.

- [X] T013 [P] [US1] Написать adapter contract suite для exact URL, nullable parameters, response modes, max output, envelope/finish/usage/errors, нулевых SDK retries и отсутствия активного connection cap в `tests/contract/test_model_adapter_v1.py`.
- [X] T014 [P] [US1] Написать tests компактного review output, missing scope, ambiguous/context anchors и exact coverage в `tests/contract/test_ml_review_output.py`.
- [X] T015 [US1] Привести `packages/review-runtime/src/review_runtime/models/openai_compatible.py` к ModelAdapter v1: один async POST, raw text/metadata, profile options, bounded response bytes, typed errors; убрать hardcoded /v1/temperature/json_object и внутренние retries.
- [X] T016 [US1] Реализовать shared runtime factory/client lifetime и fixture async wrapper в `packages/review-runtime/src/review_runtime/composition.py`; внешний client max_connections=None, offline composition без сетевых вызовов.
- [X] T017 [US1] Подготовить immutable review input и полный prompt budget с output reserve в `packages/review-core/src/review_core/review/prompt.py` и `packages/review-runtime/src/review_runtime/skills/executor.py`; oversize не вызывает модель и не обрезает текст.
- [X] T018 [US1] Создать внутреннюю компактную response schema без служебных ID/offsets/provenance в `specs/004-llm-review-integration/contracts/model-output.review.v1.schema.json` и mapping в `packages/review-core/src/review_core/review/engine.py`.
- [X] T019 [US1] Реализовать серверные ID/unique exact quote resolution и полный validation pipeline в `packages/review-core/src/review_core/review/validation.py` и `packages/review-runtime/src/review_runtime/reports.py`; supporting context anchors не требуют membership в primary target, но сохраняют primary basis finding.
- [X] T020 [US1] Реализовать atomic same-key admission, single execution claim и guarded success/failure/cancel publication в `packages/review-runtime/src/review_runtime/postgres/platform.py`; сохранять attempt metadata по data-model.md.
- [X] T021 [US1] Перевести create-review route на await coordinator в `apps/api/src/review_api/routes/reviews.py`, настроить lifecycle в `apps/api/src/review_api/app.py`; сохранить 202/Location/polling/replay и DTO.
- [X] T022 [US1] Проверить durable review flow, invalid result, oversized input, optional context gaps и честную provenance в `tests/integration/test_ml_review_http.py`.
- [X] T023 [US1] Проверить concurrent same-key/different-body, duplicate executor entry, cancel/deadline-vs-publish, deadline внутри sync publish до CAS, задержку/unknown outcome commit после CAS и late result в `tests/integration/test_ml_review_races.py`.

**Checkpoint**: минимальный review tracer bullet работает end-to-end без ключа; старая fixture acceptance сохраняется.

## Phase 4 — US2: диалог и человеческое решение (P1)

**Independent test**: начать с опубликованного synthetic report; выполнить новый ход, ошибку, retry и решение без нового review.

- [X] T024 [P] [US2] Написать dialogue output contract tests для action/proposal/anchors и запрета human/service fields в `tests/contract/test_ml_dialogue_output.py`.
- [X] T025 [P] [US2] Написать regression tests same-turn retry, 128-symbol key, replay после successful retry и отсутствия дублирования message в `tests/integration/test_ml_dialogue_retry.py`.
- [X] T026 [US2] Реализовать immutable dialogue preparation с exact original model/skill versions, completed history и current message один раз в `packages/review-core/src/review_core/dialogue/prompt.py` и `packages/review-core/src/review_core/application/dialogue.py`.
- [X] T027 [US2] Создать компактную dialogue response schema в `specs/004-llm-review-integration/contracts/model-output.dialogue.v1.schema.json` и async execution/mapping в `packages/review-core/src/review_core/dialogue/engine.py`.
- [X] T028 [US2] Реализовать generation attempt admission/retry на том же turn, idempotency до state checks и сохранение provider attempts в `packages/review-runtime/src/review_runtime/postgres/platform.py`.
- [X] T029 [US2] Вынести сетевую генерацию из dialogue transaction, публиковать по точным turn/attempt ID и соблюдать общий lock order при Human Decision в `packages/review-runtime/src/review_runtime/postgres/platform.py`.
- [X] T030 [US2] Проверять assistant schema, exact evidence и безопасную фактическую provenance в `packages/review-core/src/review_core/dialogue/validation.py`; model response не меняет решение человека.
- [X] T031 [US2] Подключить await create/retry coordinator и offload коротких decision writes в `apps/api/src/review_api/routes/findings.py`; сохранить HTTP v1 и expected_revision semantics.
- [X] T032 [US2] Проверить live fake-provider dialogue success/failure/retry, deadlines и недоступность закреплённой старой profile version в `tests/integration/test_ml_dialogue_http.py`.
- [X] T033 [US2] Проверить concurrent turns/retry, decision during generation, stale attempt и отсутствие потери истории в `tests/integration/test_ml_dialogue_races.py`.
- [X] T034 [US2] Проверить идентичность canonical report bytes/hash/ETag после dialogue/decision/retry в `tests/e2e/test_ml_report_immutability.py`.

**Checkpoint**: review и dialogue имеют одинаковые гарантии попыток, сроков и публикации; предложение модели отделено от решения человека.

## Phase 5 — US3: операторская поставка и восстановление (P2)

**Independent test**: два fake profiles, смена версии, restart во время generation и direct CLI; нет обращений к реальному endpoint.

- [X] T035 [P] [US3] Написать profile/schema/manifest drift, nullable parameters, unsupported capabilities и secret-boundary tests в `packages/review-runtime/tests/test_ml_model_config.py`.
- [X] T036 [P] [US3] Написать availability freshness/probe/manual observation и separate compatibility tests в `packages/review-runtime/tests/test_model_availability.py`.
- [X] T037 [US3] Проецировать список реальных profile versions и свежую availability в `apps/api/src/review_api/routes/profiles.py`; readiness в `routes/health.py` проверяет локальные зависимости, а не генерирует ответ модели.
- [X] T038 [US3] Реализовать single-process deployment ownership, startup interrupted-state reconciliation и shutdown finalization в `packages/review-runtime/src/review_runtime/postgres/platform.py` и `apps/api/src/review_api/app.py`; network regeneration на старте запрещена.
- [X] T039 [US3] Написать process-kill/restart tests после accept, во время вызова, до и после report commit, плюс второй startup и ownership conflict в `tests/e2e/test_ml_restart.py`.
- [X] T040 [US3] Подключить direct CLI к общему engine/coordinator с одним anyio.run и изолированным локальным in-memory storage без БД/ownership/reconciliation API, сохранив команды/флаги/output/offline defaults, в `apps/cli/src/review_cli/commands/review.py`; проверить direct/HTTP equivalence и независимый запуск CLI при работающем API в `tests/contract/test_channel_semantics.py`.
- [X] T041 [US3] Проверить отсутствие model-call лимитера на трёх удерживаемых вызовах и работу health/polling/decision до их освобождения в `tests/integration/test_ml_concurrency.py`.
- [X] T042 [US3] Создать explicit external-model Compose override и non-secret config example, согласовать proxy timeout 330s с deadline/finalization в `deploy/compose/compose.external-model.yaml`, `deploy/compose/nginx.conf` и `deploy/compose/env.example`.
- [X] T043 [US3] Проверить default no-egress, opt-in fake-provider Compose flow и timeout proxy chain с коротким test deadline в `tests/e2e/test_ml_compose.py`.
- [X] T044 [US3] Адаптировать optional endpoint smoke к тому же ModelAdapter/engine в `apps/cli/src/review_cli/commands/model_smoke.py` и записать точные команды/evidence tuple в `specs/004-llm-review-integration/quickstart.md`; реальный запуск после выбора/подключения endpoint не выполнять автоматически.

**Checkpoint**: технический путь поставки готов без выбора модели; real-endpoint compatibility остаётся unverified до отдельного прогона.

## Phase 6 — Polish & cross-cutting verification

- [X] T045 [P] Проверить secrets/raw errors/prompt injection, untrusted profile/history, redaction и bounded response bytes в `tests/security/test_ml_boundary.py`.
- [X] T046 Проверить failure mapping, все canonical HTTP v1 examples и отсутствие breaking diff в `tests/contract/test_ml_http_compatibility.py` и `contracts/review-platform/v1/`; новые публичные поля/enum не добавлять.
- [X] T047 Выполнить полный locked 003+004 gate, включая migration, races, restart, CLI и legacy PoC, и сохранить точные результаты/коммиты в `specs/004-llm-review-integration/quickstart.md`.
- [X] T048 Обновить операционные инструкции, карту платформы и состояние feature в `docs/operations/configuration.md` и `README.md`; сохранить отдельный статус real endpoint/harness evidence в `ai-review-product`.
- [X] T049 Проверить согласованность spec/plan/tasks, локальные ссылки, источники, `git diff --check` и `CLAUDE.md → AGENTS.md`; сверить остаточные работы с `specs/004-llm-review-integration/backlog.md`.

## Dependencies & Execution Order

Setup → Foundation → US1 → US2 → US3 → full gate. US2 independently тестируется на готовом отчёте; US3 — на synthetic data, но их production composition опирается на common coordinator/adapter из US1. T011/T012 предшествуют первому ML review и проверке недоступной старой версии в dialogue; T006 предшествует T007/T020/T028/T038; T015/T016 предшествуют реальным fake HTTP flows; T026–T031 предшествуют dialogue races. T042 предшествует Compose T043.

Параллельные примеры: T013 и T014 (разные contract suites); T024 и T025 (contract/retry tests); T035 и T036 (расширенные profile/availability tests); T045 может выполняться после готовности потоков параллельно документации T048. Задачи изменения общего postgres/platform.py выполняются последовательно. Маркер [P] не разрешает обойти зависимости фаз.

MVP tracer bullet — Foundation + US1. Полная инженерная feature включает все US1–US3 и gate; отдельно утверждённый запуск реализации не считается завершённым после одного tracer bullet.

## Coverage Summary

| Requirement | Tasks |
| --- | --- |
| FR-001 | T015, T017, T018, T022 |
| FR-002 | T004, T017, T022, T026 |
| FR-003 | T014, T018, T019, T022 |
| FR-004 | T018, T019, T027, T030 |
| FR-005 | T026, T027, T032 |
| FR-006 | T025, T028, T032 |
| FR-007 | T020, T023, T025, T028 |
| FR-008 | T008, T020, T023, T029, T033 |
| FR-009 | T029, T030, T033, T034 |
| FR-010 | T009, T015, T022, T032 |
| FR-011 | T008, T009, T023, T032, T042, T043 |
| FR-012 | T016, T041 |
| FR-013 | T005, T008, T021, T029, T031, T041 |
| FR-014 | T038, T039 |
| FR-015 | T008, T025, T028, T039 |
| FR-016 | T003, T004, T013, T015, T035, T011 |
| FR-017 | T006, T010, T015, T020, T030, T011 |
| FR-018 | T036, T012, T037, T044 |
| FR-019 | T003, T010, T035, T045 |
| FR-020 | T007, T034, T011, T040, T046, T047 |
| FR-021 | T016, T040, T043 |
| FR-022 | T042, T043, T045 |
| FR-023 | T002, T013, T022, T032, T041, T044, T047 |
| FR-024 | T001, T002, T047, T048, T049 |
| SC-001 | T014, T022, T024, T032 |
| SC-002 | T023, T025, T033, T034 |
| SC-003 | T007, T011, T039 |
| SC-004 | T041 |
| SC-005 | T009, T022, T032, T043 |
| SC-006 | T013, T035, T036, T011, T040 |

Итого: 49 задач; Setup 2, Foundation 10, US1 11, US2 11, US3 10, Polish 5. Все 24 FR и 6 SC имеют задачи; это покрытие планом, не доказательство выполнения.
