# Tasks: локальный restart-safe backend MVP

**Input**: [spec.md](spec.md), [plan.md](plan.md), [data-model.md](data-model.md), [internal contracts](contracts/README.md)
**Tests**: обязательны; незавершённые tasks следуют test-first порядку.
**Deferred**: исторический production scope сохранён в [deferred-production-hardening.md](deferred-production-hardening.md).

## Phase 1: Preserved foundation

**Purpose**: зафиксировать уже проверенный baseline до rebaseline.

- [X] T001 Сохранить накопленную backend-реализацию checkpoint-коммитом после `git diff --check`, Ruff и unit/contract sanity suites и зафиксировать границу в `specs/003-backend-implementation/deferred-production-hardening.md`
- [X] T002 Сохранить canonical HTTP v1.0.2 compatibility tests без новых public contract changes в `tests/contract/`
- [X] T003 Создать locked Python workspace, package boundaries и deterministic fixtures в `pyproject.toml`, `uv.lock`, `packages/`, `apps/` и `tests/fixtures/`
- [X] T004 Создать frozen explicit Alembic migration нормализованной PostgreSQL schema с namespace FKs и immutable guards в `packages/review-runtime/migrations/`
- [X] T005 Реализовать deterministic executor, exact trusted fixture, arbitrary partial coverage и canonical report validation в `packages/review-core/` и `packages/review-runtime/`

**Checkpoint**: preserved foundation is committed at `a4aed47`.

---

## Phase 2: Foundational MVP composition

**Purpose**: подключить уже созданное durable ядро как единственный default runtime.

- [X] T006 Написать failing durable-composition/readiness tests без `runtime_state` и queue health в `tests/integration/test_mvp_composition.py`
- [X] T007 Подключить `PostgresReviewPlatform` через `OperatorSettings` и исправить exact seed/readiness/artifact probe в `apps/api/src/review_api/dependencies.py` и `apps/api/src/review_api/routes/health.py`
- [X] T008 Убрать `DurableReviewPlatform` из default runtime imports и явно пометить queue/recovery composition deferred в `packages/review-runtime/src/review_runtime/postgres/durable.py` и `apps/worker/`

**Checkpoint**: API starts only against migrated normalized PostgreSQL and writable POSIX artifacts.

---

## Phase 3: User Story 1 — Получить отчёт без внешней модели (Priority: P1) 🎯 MVP

**Goal**: clean local HTTP upload/review/report flow returns the exact synthetic finding.

**Independent Test**: public API synthetic flow completes with one expected finding and arbitrary input returns explicit partial coverage.

- [X] T009 [US1] Написать failing PostgreSQL-backed HTTP synthetic/arbitrary/idempotency tests в `tests/integration/test_mvp_review_http.py`
- [X] T010 [US1] Исправить synchronous normalized upload/create-run/report path и exact envelope-independent execution в `packages/review-runtime/src/review_runtime/postgres/platform.py`
- [X] T011 [US1] Создать clean default Compose topology с init ownership, one-shot migration, healthy API/proxy, loopback bind и deferred worker profile в `deploy/compose/`

**Checkpoint**: US1 works through `127.0.0.1` without worker, secrets or egress.

---

## Phase 4: User Story 2 — Диалог и решение человека (Priority: P1)

**Goal**: dialogue/decision flow persists separately and leaves report bytes unchanged.

**Independent Test**: HTTP turn plus decision succeeds; stale revision conflicts; report bytes/hash/ETag are unchanged.

- [X] T012 [US2] Написать failing PostgreSQL-backed dialogue/decision/report-immutability test в `tests/integration/test_mvp_dialogue_http.py`
- [X] T013 [US2] Исправить synchronous dialogue, idempotency, revision and Human Decision persistence в `packages/review-runtime/src/review_runtime/postgres/platform.py`

**Checkpoint**: US2 preserves human authority and immutable report.

---

## Phase 5: User Story 3 — Штатный restart (Priority: P1)

**Goal**: real Compose restart preserves all durable data and exact report representation.

**Independent Test**: restart API and PostgreSQL without volume removal, then compare bytes, SHA-256 and ETag.

- [X] T014 [US3] Написать real Compose smoke/restart verifier using public HTTP in `tools/mvp_smoke.py` and `tests/e2e/test_mvp_compose.py`
- [X] T015 [US3] Добавить `mvp-up`, `mvp-smoke`, `mvp-restart`, `mvp-down` targets and isolated project/volume handling в `Makefile`
- [X] T016 [US3] Исправить container startup, health ordering, writable uv cache and restart persistence until clean Compose E2E passes в `deploy/compose/`

**Checkpoint**: US3 proves restart-safe local operation.

---

## Phase 6: Verification and handoff

**Purpose**: закрыть только active MVP scope и честно отделить deferred work.

- [X] T017 Добавить deterministic no-egress/minimal security assertions и актуализировать active evidence mapping в `tests/security/` и `specs/003-backend-implementation/contracts/test-matrix.md`
- [X] T018 Прогнать locked contract, unit, migration, integration, security and Compose E2E gates; воспроизвести `quickstart.md`; выполнить protected-path check в `Makefile`
- [X] T019 Провести final code/spec review, устранить Critical/High findings, отметить все active tasks `[X]` в `specs/003-backend-implementation/tasks.md` и закоммитить готовый MVP

---

## Phase 7: Convergence findings

**Purpose**: закрыть High-gap между заявленной операторской конфигурацией и фактическим deterministic runtime.

- [X] T020 [US1] Написать failing integration/unit tests, доказывающие загрузку exact trusted binding из `REVIEW_RUNTIME_CONFIG_PATH` и отказ readiness при missing/drifted expected-output resource в `tests/integration/test_mvp_composition.py` и `packages/review-runtime/tests/`
- [X] T021 [US1] Подключить `REVIEW_EXPECTED_OUTPUT_PATH` к `OperatorSettings`, production executor composition и exact-resource readiness validation в `packages/review-runtime/src/`, `apps/api/src/` и `deploy/compose/`
- [X] T022 Обновить карту feature 003 и фактические locked dependency versions в `README.md` и `specs/003-backend-implementation/plan.md`
- [X] T023 [US1] Написать failing contract/integration assertions для обязательных `Location` headers create-run/create-turn и исправить response composition в `apps/api/src/review_api/routes/`
- [X] T024 [US1] Перенести smoke/restart verifier внутрь app image, чтобы documented MVP flow требовал на host только Docker Compose и `make`, в `Makefile`, `deploy/compose/compose.yaml` и `specs/003-backend-implementation/quickstart.md`
- [X] T025 [US1] Написать failing integration assertion об отсутствии outbox/lease записей в synchronous request path и удалить queue/lease dependency из review/dialogue execution в `packages/review-runtime/src/review_runtime/postgres/platform.py`
- [X] T026 Стабилизировать существующий in-memory dialogue CAS gate после воспроизведённой гонки в `packages/review-core/src/review_core/application/platform.py`
- [X] T027 Согласовать оставшиеся internal HTTP/data-model пояснения с synchronous MVP и перенести execution-attempt/outbox формулировки в deferred boundary в `specs/003-backend-implementation/contracts/http-v1-clarifications.md` и `data-model.md`
- [X] T028 Обновить статус feature 003 и корневой карты: технический локальный MVP реализован и проверен, продуктовые исследования и client pilot не заявлены завершёнными, в `specs/003-backend-implementation/spec.md` и `README.md`
- [X] T029 [US1] Добавить failing negative test и full canonical `ReviewReport` JSON Schema validation до publication в `packages/review-core/` или `packages/review-runtime/`
- [X] T030 [US1] Привести `Idempotency-Key` validation и contract tests к canonical 8–128 символам для create-run/create-turn в `apps/api/src/review_api/routes/` и runtime facades
- [X] T031 Документировать `make release-check` как полный contributor gate, отделив его от сокращённого локального gate, в `specs/003-backend-implementation/quickstart.md`
- [X] T032 Разделить безопасный `mvp-down` и явно разрушительный `mvp-reset`, описать два named volumes и границы их содержимого в `Makefile` и `specs/003-backend-implementation/quickstart.md`
- [X] T033 Убрать персональный test DSN и сделать `make release-check` воспроизводимым через автоматически мигрируемый и очищаемый isolated PostgreSQL project в `Makefile`, `deploy/compose/compose.release.yaml` и test fixtures

---

## Dependencies & Execution Order

```text
T001–T005 preserved foundation
  → T006 test → T007–T008 composition
    → T009 test → T010–T011 US1
      → T012 test → T013 US2
        → T014 test → T015–T016 US3
          → T017–T018 verification
            → T020 test → T021 convergence fix
              → T022–T025 review fixes
              → T026–T033 convergence, operator UX and release-gate fixes
              → T019 final review and commit
```

## Implementation Strategy

Все три P1 story входят в MVP. Queue/worker hardening не является скрытой зависимостью. Каждый новый тест должен сначала воспроизвести реальный gap, после чего исправляется минимальный production path. Existing experimental code сохраняется, но не расширяет claims первой поставки.
