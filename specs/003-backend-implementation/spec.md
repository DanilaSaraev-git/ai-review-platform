# Feature Specification: локальный restart-safe backend MVP

**Feature Branch**: `codex/003-backend-implementation`
**Created**: 2026-09-05
**Rebaselined**: 2026-09-05
**Status**: Implemented and verified as a local technical MVP

Feature 003 реализует первый локальный backend-срез Review Platform. [Feature 002](../002-target-review-platform/spec.md) и публичный [HTTP v1](../../contracts/review-platform/v1/README.md) остаются неизменяемым baseline. Реализация не подтверждает качество AI-замечаний, продуктовый эффект, коммерческий статус или результаты пилота client.

## Clarifications

### Session 2026-09-05

- Q: Каков обязательный runtime первой итерации? → A: локальный single-process Docker Compose MVP с синхронным deterministic executor; очередь и внешний доступ отложены.

## User Scenarios & Testing

### User Story 1 — Получить отчёт без внешней модели (Priority: P1)

Аналитик локально загружает поддерживаемый документ через публичный API, запускает проверку и получает валидный неизменяемый отчёт. Чистый запуск не требует API-ключей, платных сервисов или скачивания модели.

**Independent Test**: в чистом Compose выполнить `bootstrap → upload → create run → report`; exact synthetic fixture должен вернуть ровно одно ожидаемое замечание.

**Acceptance Scenarios**:

1. **Given** чистые volumes, **When** оператор запускает документированную команду, **Then** PostgreSQL мигрируется, API становится ready, а proxy доступен только на `127.0.0.1`.
2. **Given** exact synthetic fixture и release seed, **When** создаётся run, **Then** синхронный deterministic executor публикует completed report с ровно одной ожидаемой finding.
3. **Given** произвольный поддерживаемый документ, **When** его digest не входит в trusted fixture binding, **Then** публикуется честный zero-finding partial report с gap для каждого primary fragment.
4. **Given** одинаковые idempotency key и body, **When** запрос повторяется последовательно, **Then** возвращается тот же run; другой body с тем же key получает conflict.
5. **Given** чужой workspace ID, **When** вызывается workspace-scoped endpoint, **Then** API отвечает обычным `404`.

---

### User Story 2 — Обсудить замечание и сохранить решение (Priority: P1)

Аналитик отправляет последовательный ход диалога по finding и отдельно фиксирует решение человека. Эти действия не изменяют опубликованный отчёт.

**Independent Test**: создать dialogue turn и Human Decision, затем доказать неизменность report bytes, SHA-256 и strong ETag.

**Acceptance Scenarios**:

1. **Given** finding из завершённого отчёта, **When** принят dialogue turn, **Then** deterministic ответ завершается в том же API-процессе и история читается в исходном порядке.
2. **Given** повтор хода с тем же key и body, **When** запрос повторяется, **Then** новый turn не создаётся; stale revision либо иной body возвращают conflict.
3. **Given** сохранённое Human Decision, **When** читаются finding state и dialogue, **Then** решение принадлежит actor, дальнейшая отправка согласована с `can_send_message`, а исходный report не изменён.

---

### User Story 3 — Пережить штатный перезапуск (Priority: P1)

Оператор перезапускает API и PostgreSQL через Docker Compose. Документы, отчёты, диалоги и решения остаются доступными и побайтово идентичными.

**Independent Test**: пройти synthetic flow, перезапустить API и PostgreSQL без удаления volumes и сравнить report bytes, SHA-256 и ETag до и после restart.

**Acceptance Scenarios**:

1. **Given** завершённый flow, **When** API пересоздан, **Then** `PostgresReviewPlatform` восстанавливает состояние из нормализованного PostgreSQL и POSIX artifact volume без `runtime_state` snapshot.
2. **Given** сохранённый report, **When** перезапущены API и PostgreSQL, **Then** тело, SHA-256 и strong ETag совпадают, а dialogue/decision history читается.
3. **Given** неверная схема, drift release seed или unwritable artifact store, **When** вызывается readiness, **Then** ответ имеет статус `503` и безопасно называет проваленную проверку.

## Edge Cases

- Zero-byte, неподдерживаемый media type и невалидный UTF-8 отклоняются безопасной ошибкой.
- Повреждённый или не содержащий текста PDF не публикует выдуманный semantic result.
- Текст документа считается недоверенными данными и не меняет правила deterministic executor.
- Мутация исходного файла после upload не меняет сохранённые bytes.
- Compose из чистого checkout не зависит от локального `.env`, ранее созданной базы или очереди.
- Optional local-model smoke может быть skipped и никогда не является gate.

## Functional Requirements

- **FR-001**: backend MUST сохранить без breaking changes все backend-owned операции canonical HTTP v1.
- **FR-002**: default durable composition MUST использовать `PostgresReviewPlatform`, нормализованные PostgreSQL relations и POSIX artifact storage; `runtime_state` MUST NOT быть runtime dependency.
- **FR-003**: MVP MUST выполнять extraction, deterministic review и dialogue синхронно в одном API process и поддерживать одну replica.
- **FR-004**: exact trusted fixture MUST выбираться только по versioned digest selectors и возвращать ровно одну packaged expected finding.
- **FR-005**: arbitrary deterministic input MUST возвращать zero-finding partial report и отдельный gap для каждого primary fragment.
- **FR-006**: published report MUST пройти structural и semantic validation до регистрации и храниться как canonical RFC 8785 bytes со strong ETag.
- **FR-007**: document bytes, report graph, findings, anchors, coverage, provenance и Human Decision history MUST сохраняться в нормализованных relations с namespace foreign keys.
- **FR-008**: report bytes MUST оставаться неизменными после dialogue, decision и штатного restart.
- **FR-009**: create-run и create-turn MUST поддерживать последовательную idempotency; concurrent multi-replica semantics deferred.
- **FR-010**: dialogue и decision updates MUST проверять expected revision и не изменять published report.
- **FR-011**: configured organization, workspace, actor, deployment, system profile, model profile, dialogue policy и skill digest MUST seed-иться идемпотентно и проверяться на exact drift.
- **FR-012**: default Compose MUST состоять из PostgreSQL, one-shot Alembic migration, API и loopback proxy; API MUST стартовать после успешной migration.
- **FR-013**: worker, Procrastinate, outbox dispatch, leases и recovery MAY оставаться в репозитории как deferred/experimental, но MUST NOT входить в default runtime или readiness.
- **FR-014**: `/health/live` MUST проверять процесс, а `/health/ready` MUST проверять PostgreSQL, Alembic head, exact seed и writable artifact store без `runtime_state` и `procrastinate_jobs`.
- **FR-015**: artifact volume MUST создаваться с ownership, позволяющим непривилегированному container user `review` читать и записывать artifacts.
- **FR-016**: proxy MUST публиковаться только на `127.0.0.1`; domain, TLS и внешний доступ находятся вне scope.
- **FR-017**: default deterministic path MUST не делать network egress и MUST не требовать secrets.
- **FR-018**: Docker image MUST использовать locked dependencies; one-off `uv run` MUST иметь writable `UV_CACHE_DIR=/tmp/uv-cache`.
- **FR-019**: clean quickstart MUST запускаться одной documented command/Make target; обычный operator shutdown MUST сохранять named volumes, а их удаление MUST быть отдельной явно разрушительной reset-командой. Изолированный E2E teardown MAY удалять только volumes своего test project.
- **FR-020**: contract, unit, migration, integration, minimal security и Compose E2E gates MUST быть зелёными; optional local-model smoke не входит в них.

## Key Entities

- **Configured Deployment Context**: один configured Organization, Workspace, Actor и Deployment.
- **Document Version / Extraction / Fragment**: immutable uploaded bytes и адресуемое extracted content.
- **Review Profile / Model Profile / Skill / Dialogue Policy Version**: exact execution dependencies.
- **Review Run / Execution Snapshot**: синхронно выполненная review operation и снимок входов.
- **Review Report / Finding / Anchor / Coverage / Provenance**: immutable validated result.
- **Finding State / Dialogue / Dialogue Turn / Human Decision**: отдельная versioned human-review history.
- **Idempotency Record**: защита последовательных create requests.
- **Artifact**: opaque immutable bytes в POSIX volume.

## Scope and Boundaries

### In Scope

- Локальный Docker Compose на Mac: PostgreSQL, migration, один API process и loopback proxy.
- Публичный HTTP v1 flow: bootstrap, upload, profiles, run/report, dialogue и decision.
- Синхронный deterministic executor, exact synthetic fixture и arbitrary partial behavior.
- Restart persistence нормализованного PostgreSQL и POSIX artifacts.
- Воспроизводимый quickstart, тесты и безопасный teardown.

### Deferred Production Hardening

Полный исторический план сохранён в [deferred-production-hardening.md](deferred-production-hardening.md). Отложены: обязательный worker/Procrastinate, transactional outbox delivery, leases/heartbeats/recovery, concurrent multi-replica claims, process-kill artifact collection, public domain/TLS, external access, optional provider productionization, full egress firewalling, production SLO/backup/retention и расширенный release compliance.

### Out of Scope

- Изменения `apps/web/`, feature 001, feature 002 или canonical public v1 contract.
- Authentication/authorization, multi-organization runtime и публикация API в недоверенную сеть.
- client-materials/client materials в common fixtures, packages или images.
- Платная/внешняя модель и автоматическое скачивание model weights.
- Product validation, экспертная оценка findings и коммерческие выводы.

## Success Criteria

- **SC-001**: одна documented command/Make target из чистого checkout поднимает default Compose и применяет Alembic migration.
- **SC-002**: `/health/live` и `/health/ready` через `127.0.0.1` возвращают `200` после запуска.
- **SC-003**: реальный HTTP synthetic flow `upload → review → report → dialogue → decision` завершается успешно и даёт ровно одну expected finding.
- **SC-004**: report body, SHA-256 и strong ETag совпадают до и после реального restart API и PostgreSQL.
- **SC-005**: обязательные unit, contract, migration, integration, minimal security и Compose E2E suites завершаются успешно из locked dependency state.
- **SC-006**: deterministic path фиксирует 0 external connection attempts и не использует secrets.
- **SC-007**: quickstart воспроизводим из чистого checkout; обычный shutdown сохраняет operator data, а documented reset и E2E teardown удаляют только volumes своего изолированного project.
- **SC-008**: все активные MVP-задачи в `tasks.md` отмечены `[X]`; deferred backlog явно не заявлен готовым.

## Assumptions

- Пользователь запускает MVP локально на Mac с Docker Desktop или Colima и Docker Compose v2.
- Одновременный production traffic и несколько API replicas в первой итерации не поддерживаются.
- Synchronous completion внутри create request приемлем для локальной демонстрации.
- Existing worker/queue/repository prototypes сохраняются для будущего hardening, но не доказывают production readiness.
