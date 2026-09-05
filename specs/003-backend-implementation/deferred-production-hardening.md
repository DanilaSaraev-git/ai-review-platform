# Deferred production-hardening backlog (historical 120-task plan)

> Статус: отложено решением пользователя 2026-09-05. Этот файл сохраняет прежний
> production-oriented план и его номера задач как историю. Он не является активным
> Definition of Done локального single-process MVP. В частности, оставшиеся T076–T120
> не считаются реализованными и должны быть заново приоритизированы отдельным поручением.

# Tasks: Рабочий backend платформы ревью

**Input**: design documents from `specs/003-backend-implementation/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: обязательны. Пользователь запросил полностью протестированный backend; внутри каждого slice применяется red-green-refactor, а failing test фиксируется до product code.

**Scope guard**: backend feature не меняет `apps/web/`, `client-materials/`, `specs/001-*`, `specs/002-*` или сохранённые PoC artifacts. Единственное разрешённое shared изменение — additive root contract preflight `contracts/review-platform/v1` v1.0.2 отдельным первым commit.

## Phase 1 — Setup and contract preflight

**Purpose**: создать новый backend workspace и исправить только additive дыры canonical contract до зависимого кода.

- [x] T001 Зафиксировать protected-path baseline и точный allowlist contract delta в `tools/contracts/check_protected_paths.py` и `tests/contract/test_protected_paths.py`
- [x] T002 Написать failing tests additive HTTP v1.0.2 delta до изменения root contract: `info.version`, upload `404`, profile `409`, list-cursor `400`, canonical `source_partial` gap semantics, extraction/profile/strong-ETag descriptions, offline docs assets и отсутствие иных breaking diff в `tests/contract/test_http_v1_0_2_delta.py`
- [x] T003 Сделать tests T002 зелёными: обновить root HTTP baseline/examples/README/CHANGELOG, документируя `{code: source_partial, reason: primary_source_partial}` без нового enum, и заменить runtime CDN Swagger dependencies локальными assets в `contracts/review-platform/v1/openapi.yaml`, `contracts/review-platform/v1/README.md`, `contracts/review-platform/v1/CHANGELOG.md` и `contracts/review-platform/v1/swagger/`
- [x] T004 [P] Написать failing duplicate-key-safe schema tests: job envelope строго различает `review_execution_id` и `generation_attempt_id` по kind, PoC reader возвращает только `poc-import-view.v1`, runtime config материализует/валидирует defaults и cross-field invariants, trusted fixture template закрыт schema, отвергает invalid ordinal/occurrence selectors и трактует placeholder-like text только буквально без substitution, в `tests/contract/test_job_envelope_schema.py`, `tests/contract/test_poc_import_view_schema.py`, `tests/contract/test_runtime_config_schema.py` и `tests/contract/test_trusted_fixture_output_schema.py`
- [x] T005 Сделать tests T004 зелёными: добавить OpenAPI/$ref/schema/example validator и isolated Orval generate+TypeScript typecheck consumer с exact Node/npm/TypeScript/Orval pins, lockfile и temp generated output; `make contracts` запускает оба gates через `tools/contracts/validate_contracts.py`, `tools/contracts/orval/package.json`, `package-lock.json`, `tsconfig.json`, `orval.config.ts` и `Makefile`, не читая и не меняя `apps/web/`; после green additive gate зафиксировать отдельный contract commit и annotated tag `review-platform-contract-v1.0.2` ровно на нём, а при breaking diff tag не создавать
- [ ] T006 Создать root uv workspace, exact Python/tool pins и общие dev/test dependencies в `pyproject.toml`, `uv.lock`, `.python-version` и `uv.toml`
- [ ] T007 [P] Создать package/app manifests для `packages/review-core/pyproject.toml`, `packages/review-runtime/pyproject.toml`, `apps/api/pyproject.toml`, `apps/worker/pyproject.toml` и `apps/cli/pyproject.toml`
- [ ] T008 [P] Создать backend source/test/deploy directory skeleton и package initializers под `packages/`, `apps/api/`, `apps/worker/`, `apps/cli/`, `tests/`, `skills/` и `deploy/compose/`
- [ ] T009 [P] Дополнить Python/Docker/local-artifact ignore patterns в `.gitignore` и `.dockerignore`, исключить `client-materials/` из Docker context и source distribution, добавить `/client export-ignore` в `.gitattributes`, не скрывая contract/spec files
- [ ] T010 Добавить исполняемые Make targets `lint`, `contracts`, `test-unit`, `test-integration`, `test-migration`, `test-security`, `test-e2e` с реальными package test paths и подключить их к backend-only locked CI и protected-path guard в `Makefile` и `.github/workflows/ci.yml`

**Checkpoint**: `make contracts` green; root v1.0.2 delta additive; workspace syncs; diff in feature 001/002, client and web is empty.

---

## Phase 2 — Foundational domain and test harness

**Purpose**: общие pure-domain seams, fixtures и boundaries, блокирующие все user stories.

- [ ] T011 [P] Создать organization-neutral synthetic Markdown/context/duplicate-quote/injection fixtures, closed `trusted-fixture-expected-output.v1` template и trusted SHA-256 manifest: expected finding разрешён только для exact document/config/resource digests, а не marker text из upload; dynamic resolution ограничена primary ordinal + exact quote occurrence, в `tests/fixtures/synthetic-review/`
- [ ] T012 [P] Добавить generated temporary MD/TXT/PDF builders для BOM, empty-page, split-table, partial/image-only/encrypted/corrupt/oversize и byte/page/fragment budgets, плюс 0/50/51-context request builders, в `tests/fixtures/builders/documents.py` и `tests/fixtures/builders/reviews.py`
- [ ] T013 Добавить failing client-data/secret/path/package scan и boundary-redaction tests до logging implementation: purpose-built content responses allow only canonical fields, а Problem/metadata/queue/log/metric/diagnostic paths reject content/canaries, в `tests/security/test_public_fixture_isolation.py`, `tests/security/test_safe_boundary_redaction.py` и `tools/security/scan_release.py`
- [ ] T014 [P] Написать failing unit tests server IDs, namespace values, run/extraction/turn state transitions и terminal invariants в `packages/review-core/tests/test_domain_states.py`, а также operator settings tests для ровно одного organization/workspace/actor, artifact/queue connection settings и полного seed-reference set в `packages/review-runtime/tests/test_settings.py`
- [ ] T015 [P] Написать failing JCS tests по официальным RFC 8785 vectors, включая ECMAScript number serialization, Unicode, `-0`, exponent boundaries, duplicate keys/non-finite values, digests и strong ETag, в `packages/review-core/tests/test_canonicalization.py`
- [ ] T016 [P] Написать failing unit tests profile family identity/server patch versioning, immutable system profiles, same-name distinct families, current-head/concurrent-head и exact missing/foreign `404`, system `400`, stale/unchanged `409` semantics в `packages/review-core/tests/test_profile_versioning.py`
- [ ] T017 Реализовать framework-independent IDs, entities, values, state machines и typed domain errors в `packages/review-core/src/review_core/domain/`
- [ ] T018 Реализовать canonicalizer/digest/ETag interfaces и framework-free wrapper над exact `rfc8785==0.1.4` codec в `packages/review-core/src/review_core/canonical.py`
- [ ] T019 [P] Определить coarse `ReviewApplication`, включая bootstrap/download, command/query types и ports UoW/repositories/artifact/parser/skill/model/job/extraction-execution lease/clock/secret/logger в `packages/review-core/src/review_core/application/` и `packages/review-core/src/review_core/ports/`
- [ ] T020 [P] Сделать config tests T004/T014 зелёными: реализовать runtime-policy defaults/materialization/digest/cross-field validation, closed trusted expected-output schema/resource ID+SHA validation, content-free `review-config-check` console command и operator settings для ровно одного organization/workspace/actor, POSIX/queue, deterministic profile, dialogue policy и trusted skill в `packages/review-runtime/src/review_runtime/config/settings.py`, `trusted_fixtures.py`, `verify.py` и `packages/review-runtime/pyproject.toml`
- [ ] T021 [P] Реализовать in-memory UnitOfWork/repositories/artifact/outbox/lease/clock/id-generator fakes с attempt-specific jobs в `packages/review-runtime/src/review_runtime/fakes/`
- [ ] T022 [P] Создать FastAPI app factory, dependency composition и Pydantic DTO boundary skeleton в `apps/api/src/review_api/app.py`, `dependencies.py` и `dto/`
- [ ] T023 [P] Реализовать central RFC 9457 mapper, request/trace middleware и safe structured logging filter в `apps/api/src/review_api/errors.py`, `middleware.py` и `packages/review-runtime/src/review_runtime/security/`
- [ ] T024 Добавить architecture import tests, запрещающие framework/runtime/provider imports из `review-core`, в `tests/contract/test_module_boundaries.py`

**Checkpoint**: foundational unit tests green; no HTTP behavior fixture yet; all future components depend only on declared ports.

---

## Phase 3 — User Story 1: complete offline review flow (Priority: P1) 🎯 MVP

**Goal**: сначала полный FastAPI tracer bullet на fakes, затем его замена real extraction/engine без изменения HTTP DTO.

**Independent Test**: canonical synthetic document с trusted fixture digest проходит `bootstrap → upload → profiles → create/poll run → immutable report` без network; любой другой document, включая текст с copied marker, получает honest partial zero-finding result, gap для каждого primary fragment и limitation.

### Slice 3A — Failing HTTP/contract tests

- [ ] T025 [P] [US1] Написать failing operation-by-operation HTTP tests bootstrap/documents/profiles/model-profiles, включая exact internal→canonical projections (`pending|extracting→pending`, extraction terminals one-to-one, `available→available`, `unavailable|degraded|unknown|missing|expired→unavailable`), media mismatch/limits, caller mutation after upload и distinct DocumentVersion/artifact IDs для одинаковых bytes под разными именами в `tests/contract/test_bootstrap_documents_profiles_http.py`
- [ ] T026 [P] [US1] Написать failing HTTP tests create/list/get/cancel run, 0/50/51-context limits, total input budget, idempotency and namespace errors в `tests/contract/test_review_run_http.py`
- [ ] T027 [P] [US1] Написать failing HTTP tests report publication/unavailable/bytes/ETag/zero-findings/partial/failed, включая `{code: source_partial, fragment_id: null, reason: primary_source_partial}`, partition всех известных primary fragments и failed/no-report при zero usable primary, в `tests/contract/test_review_report_http.py`
- [ ] T028 [P] [US1] Написать failing FastAPI-export compatibility and no-auth/404/400/409/413 tests в `tests/contract/test_openapi_compatibility.py`
- [ ] T029 [P] [US1] Написать failing deterministic offline tracer: expected finding только для exact trusted fixture digest; arbitrary/copy-marker input даёт partial report без findings, с каждым primary fragment в gap и `deterministic_mode_no_semantic_analysis`; process-level network deny доказывает zero egress, в `tests/e2e/test_fixture_review_flow.py`

### Slice 3B — Fixture application tracer

- [ ] T030 [US1] Реализовать bootstrap, list/upload/get/download immutable document application use cases on fakes с post-upload byte ownership и без content deduplication resource identity в `packages/review-core/src/review_core/application/bootstrap.py` и `documents.py`
- [ ] T031 [US1] Реализовать list/create review profiles, document extraction и model-profile HTTP projections on fakes с canonical enum mapping, logical family ID, immutable system scope, server patch/current-head и concurrent-head semantics в `packages/review-core/src/review_core/application/profiles.py` и `documents.py`
- [ ] T032 [US1] Реализовать create/list/get/cancel review use cases, immutable snapshot, initial ReviewExecution identity, attempt-specific outbox and idempotency on fakes в `packages/review-core/src/review_core/application/reviews.py`
- [ ] T033 [US1] Реализовать fixture review executor: exact trusted binding/resource даёт schema-valid expected report через closed ordinal/quote template, любой иной digest — partial zero-finding report со всеми primary gaps и explicit provenance/limitation, в `packages/review-runtime/src/review_runtime/fakes/review_executor.py`
- [ ] T034 [US1] Реализовать one-time canonical report publication, immutable representation read и eager creation одного FindingState и Dialogue на каждый finding в `packages/review-core/src/review_core/application/reports.py`
- [ ] T035 [US1] Реализовать bootstrap/document/profile/model-profile routes по canonical OpenAPI в `apps/api/src/review_api/routes/bootstrap.py`, `documents.py` и `profiles.py`
- [ ] T036 [US1] Реализовать review-run/report/finding-state routes по canonical OpenAPI в `apps/api/src/review_api/routes/reviews.py`
- [ ] T037 [US1] Подключить packaged offline API docs и serving canonical schema в `apps/api/src/review_api/docs.py` и `apps/api/src/review_api/static/docs/`
- [ ] T038 [US1] Прогнать все Slice 3A tests против fixture composition и сохранить checkpoint без semantic-engine claims в `tests/e2e/test_fixture_review_flow.py`

**Checkpoint**: весь US1 HTTP flow проходит на real FastAPI + fake application; model, parser, DB and queue ещё не требуются и это явно отражено provenance.

### Slice 3C — Real document/engine tests first

- [ ] T039 [P] [US1] Написать failing extraction tests MD/TXT/PDF, UTF-8 BOM, empty pages, split-page tables, stable retry fragments, distinct same-byte uploads, type mismatch, byte/page/fragment budgets и partial/scanned/encrypted/corrupt cases в `packages/review-runtime/tests/test_document_parsers.py`
- [ ] T040 [P] [US1] Написать failing exact/partial coverage, quote occurrence/offset, locator, missing/scope and primary-grounding tests, включая primary source-level `{code: source_partial, fragment_id: null, reason: primary_source_partial}` + exact partition известных fragments и zero-usable-primary rejection, в `packages/review-core/tests/test_review_validation.py`
- [ ] T041 [P] [US1] Написать failing prompt-boundary tests proving document/context/intermediate text only in untrusted input в `packages/review-core/tests/test_prompt_boundary.py`
- [ ] T042 [P] [US1] Написать failing deterministic gateway tests exact document/profile/skill/parser/engine + expected-resource ID/SHA binding, resource drift/schema/ordinal/quote negatives, arbitrary/copy-marker/error/capability/no-network в `packages/review-runtime/tests/test_deterministic_model.py`
- [ ] T043 [P] [US1] Написать failing engine tests exact partition/retry/primary-source and work-item gaps/synthesis/invalid-output/budget outcomes/cancellation checkpoints в `packages/review-core/tests/test_review_engine.py`

### Slice 3D — Real core behind same contract

- [ ] T044 [US1] Реализовать immutable text/pdfplumber extraction adapters, explicit budget outcomes, partial-primary diagnostics и stable table/page locators в `packages/review-runtime/src/review_runtime/documents/text.py` и `pdf.py`
- [ ] T045 [US1] Реализовать deterministic per-DocumentVersion extraction identity and retry-safe `ensure_extracted` port service в `packages/review-runtime/src/review_runtime/documents/service.py`
- [ ] T046 [US1] Реализовать target declarative review/dialogue skill package без client data в `skills/review-data-spec/`
- [ ] T047 [US1] Реализовать skill registry, manifest/schema loader and operation boundary validation в `packages/review-runtime/src/review_runtime/skills/registry.py` и `executor.py`
- [ ] T048 [US1] Реализовать review schema + semantic validator including exact known-fragment partition, primary source-level gaps, zero-usable-primary rejection, anchors/locators/provenance в `packages/review-core/src/review_core/review/validation.py`
- [ ] T049 [US1] Реализовать trusted/untrusted GenerationRequest builder, TrustedFixtureRegistry и deterministic ModelGateway, принимающий expected synthetic behavior только по exact binding + packaged resource SHA/schema, разрешающий dynamic primary ordinal/quote occurrence в текущие IDs/offsets и повторно validating `review-output.v1`, в `packages/review-core/src/review_core/review/prompt.py`, `packages/review-runtime/src/review_runtime/models/deterministic.py` и `config/trusted_fixtures.py`
- [ ] T050 [US1] Реализовать partition/work-item/retry/gap/synthesis ReviewEngine and cooperative checks в `packages/review-core/src/review_core/review/engine.py`
- [ ] T051 [US1] Заменить fixture executor real engine composition, сохранив те же routes/DTO, в `apps/api/src/review_api/dependencies.py`
- [ ] T052 [US1] Параметризовать Slice 3A contract tests для fixture и real-engine/deterministic compositions в `tests/contract/conftest.py`
- [ ] T053 [US1] Прогнать trusted-fixture expected report и arbitrary/copy-marker partial zero-finding flows через real engine, доказать all-primary gaps, stable report bytes/ETag и zero egress в `tests/e2e/test_real_engine_offline.py`

**Checkpoint**: US1 использует реальные upload/extraction/skill/engine/validation; deterministic adapter остаётся единственной fake boundary и делает zero egress.

---

## Phase 4 — User Story 2: dialogue and Human Decision (Priority: P1)

**Goal**: один ordered async turn на finding, retry attempts и separate optimistic Human Decision без мутации report.

**Independent Test**: synthetic finding проходит create/poll dialogue and decision; concurrent/stale calls conflict; report bytes/ETag unchanged.

### Tests first

- [ ] T054 [P] [US2] Написать failing eager-dialogue state/policy/blocked-reason/one-active-turn unit tests: каждый published finding сразу имеет ровно один Dialogue, в `packages/review-core/tests/test_dialogue_state.py`
- [ ] T055 [P] [US2] Написать failing dialogue output schema/anchor/proposed-resolution/human-only tests и prompt-injection boundary tests, доказывающие, что current member message, full member/assistant history и document evidence находятся только в `untrusted_input`, в `packages/review-core/tests/test_dialogue_validation.py` и `packages/review-core/tests/test_dialogue_prompt_boundary.py`
- [ ] T056 [P] [US2] Написать failing application concurrency/idempotency/retry/decision tests on fakes, включая atomic creation точного GenerationAttempt до attempt-specific outbox, в `packages/review-core/tests/test_dialogue_application.py`
- [ ] T057 [P] [US2] Написать failing HTTP tests get/create/retry dialogue and put decision including all `409` branches в `tests/contract/test_dialogue_decision_http.py`
- [ ] T058 [P] [US2] Написать failing E2E invariant test comparing exact report before/after turn/retry/decision и после появления более новых profile/model/skill/policy versions в `tests/e2e/test_dialogue_report_immutability.py`

### Implementation

- [ ] T059 [US2] Реализовать FindingState/HumanDecision CAS use cases and reset rules в `packages/review-core/src/review_core/application/findings.py`
- [ ] T060 [US2] Реализовать eager dialogue/turn/generation-attempt state machine: create/retry atomically создаёт точный GenerationAttempt до outbox, плюс policy projection and idempotent commands, в `packages/review-core/src/review_core/dialogue/state.py` и `application/dialogue.py`
- [ ] T061 [US2] Реализовать dialogue semantic validator and physically separated trusted/untrusted input builder for current message, ordered history and evidence в `packages/review-core/src/review_core/dialogue/validation.py` и `prompt.py`
- [ ] T062 [US2] Реализовать deterministic dialogue response and failure modes в `packages/review-runtime/src/review_runtime/models/deterministic.py`
- [ ] T063 [US2] Реализовать dialogue execution/retry orchestration, которое CAS-обрабатывает только `generation_attempt_id` из envelope, не выбирает newer attempt и не пишет Human Decision, в `packages/review-core/src/review_core/dialogue/engine.py`
- [ ] T064 [US2] Реализовать finding-states/dialogue/turn/retry/decision routes в `apps/api/src/review_api/routes/findings.py`
- [ ] T065 [US2] Добавить concurrent turn/decision and decision-during-generation tests against real engine composition в `tests/integration/test_dialogue_concurrency_in_memory.py`
- [ ] T066 [US2] Прогнать полный US2 offline E2E и зафиксировать identical canonical report/ETag в `tests/e2e/test_dialogue_report_immutability.py`

**Checkpoint**: оба P1 user stories работают end-to-end без PostgreSQL/external model; report and human state strictly separated.

---

## Phase 5 — User Story 3: durable self-hosted backend (Priority: P1)

**Goal**: заменить fakes PostgreSQL/POSIX/outbox/Procrastinate adapters, пережить restart и duplicate delivery.

**Independent Test**: полный synthetic flow сохраняется после restart; duplicate jobs do not duplicate business effects; foreign namespace is 404 and impossible at DB graph level.

### Tests first

- [ ] T067 [P] [US3] Написать failing POSIX tests staging/hash/promote/rollback/path-traversal, process kill at stage/promote/DB windows, cleanup both stale staging and unreferenced promoted objects, file fsync/parent-directory fsync и реальную concurrent collector-vs-publication race: общий transaction-scoped advisory fence, recheck/delete under lock и skip on DB uncertainty, в `packages/review-runtime/tests/test_posix_artifact_store.py` и `tests/integration/test_artifact_publication_fence.py`
- [ ] T068 [P] [US3] Написать failing Alembic empty-upgrade/downgrade/current-head/immutable tests и Procrastinate schema apply/current-version/healthchecks/absent-or-stale readiness tests в `tests/migration/test_migrations.py` и `tests/integration/test_queue_schema_health.py`
- [ ] T069 [P] [US3] Написать failing repository coverage for every entity, namespace composite FK/cursor order, eager dialogue creation и clean idempotent seed всех organization/workspace/actor/system-profile/model-profile/dialogue-policy/skill version+digest records в `tests/integration/test_postgres_repositories.py` и `tests/integration/test_bootstrap_seed.py`
- [ ] T070 [P] [US3] Написать failing PostgreSQL race tests: profile system/current/concurrent-head rules; same-key/same-body и same-key/different-body для concurrent create-run/create-turn/retry с ровно одним resource+outbox; decision/active-turn CAS; concurrent extraction workers с one-owner lease, stale takeover and deterministic fragments, в `tests/integration/test_postgres_concurrency.py`
- [ ] T071 [P] [US3] Написать failing business+attempt-specific-outbox atomicity, dispatcher claim lease/stale recovery, duplicate publish/delivery/rollback и stage-kill recovery tests в `tests/integration/test_outbox_delivery.py`, `tests/integration/test_execution_recovery.py` и `tests/e2e/test_duplicate_delivery.py`
- [ ] T072 [P] [US3] Написать failing cancellation checkpoint and cancel-vs-report-publication race tests в `tests/integration/test_review_cancellation.py`
- [ ] T073 [P] [US3] Написать failing restart/history/exact-artifact/ETag E2E: после новых profile/model/skill/policy versions старые snapshot/report bytes остаются readable и идентичными; незавершённые extraction/execution/outbox leases восстанавливаются, в `tests/e2e/test_restart_persistence.py`

### Artifact and schema before repositories

- [ ] T074 [US3] Реализовать POSIX ArtifactStore with opaque namespace keys, file+parent fsync, hash verification, atomic rename, collector и общий publisher/collector transaction-scoped PostgreSQL advisory fence от exact namespace/store-key/digest: publisher lock до promotion через reference commit, collector recheck+delete under same lock, DB uncertainty skips deletion, в `packages/review-runtime/src/review_runtime/artifacts/posix.py` и `packages/review-runtime/src/review_runtime/postgres/artifact_fence.py`
- [ ] T075 [US3] Создать SQLAlchemy metadata for all deployment/document/config/run/report/dialogue/idempotency/outbox entities, eager dialogues, execution attempts и extraction/execution/outbox lease owner/heartbeat/expiry fields в `packages/review-runtime/src/review_runtime/postgres/models/`
- [ ] T076 [US3] Создать полный Alembic runtime config/environment и initial business migration with composite namespace FKs, unique/partial indexes and immutable protections в `packages/review-runtime/alembic.ini`, `packages/review-runtime/migrations/env.py`, `script.py.mako` и `migrations/versions/`
- [ ] T077 [US3] Реализовать async engine/session/UnitOfWork и clean idempotent bootstrap seed/check полного configured set: organization/workspace/actor, immutable system review profile, deterministic model profile, dialogue policy и trusted skill version/package digest, в `packages/review-runtime/src/review_runtime/postgres/uow.py` и `bootstrap.py`
- [ ] T078 [US3] Реализовать document/artifact/fragment/diagnostic/profile/model/skill/policy repositories в `packages/review-runtime/src/review_runtime/postgres/repositories/configuration.py` и `documents.py`
- [ ] T079 [US3] Реализовать run/source/snapshot/work-item/model-attempt/idempotency/outbox repositories with atomic same/different-key conflict handling, attempt identities and lease CAS в `packages/review-runtime/src/review_runtime/postgres/repositories/reviews.py` и `jobs.py`
- [ ] T080 [US3] Реализовать report/finding/anchor/coverage/provenance/finding-state/eager-dialogue repositories and exact artifact read в `packages/review-runtime/src/review_runtime/postgres/repositories/reports.py`
- [ ] T081 [US3] Реализовать dialogue/turn/generation-attempt/HumanDecision repositories and CAS queries в `packages/review-runtime/src/review_runtime/postgres/repositories/dialogue.py`

### Durable jobs and composition

- [ ] T082 [US3] Реализовать kind-specific job envelope validation, atomic business+outbox writes and lease-based claim/publish state; `review_execution_id` или `generation_attempt_id` разрешает ровно одну execution attempt, в `packages/review-runtime/src/review_runtime/queue/outbox.py`
- [ ] T083 [US3] Реализовать exported `review_worker.procrastinate_app`, Procrastinate schema apply/version/healthchecks and adapter behind `JobQueue` в `packages/review-runtime/src/review_runtime/queue/procrastinate.py` и `apps/worker/src/review_worker/__init__.py`
- [ ] T084 [US3] Реализовать dispatcher with claim owner/expiry/heartbeat, bounded retry, stale-claim recovery and duplicate-safe publication в `apps/worker/src/review_worker/dispatcher.py`
- [ ] T085 [US3] Реализовать idempotent extraction/review/dialogue handlers с attempt-specific execution leases, heartbeat, concurrent-worker exclusion and stalled recovery в `apps/worker/src/review_worker/handlers.py` и `recovery.py`
- [ ] T086 [US3] Подключить PostgreSQL/POSIX/outbox runtime в API/worker composition roots в `apps/api/src/review_api/dependencies.py` и `apps/worker/src/review_worker/app.py`
- [ ] T087 [US3] Реализовать final report/cancel compare-and-set transaction and stage/promote/DB/outbox process-kill recovery without duplicate report/reference; report publisher удерживает artifact advisory fence от promotion до successful reference commit, в `packages/review-core/src/review_core/application/reports.py` и PostgreSQL adapters
- [ ] T088 [US3] Добавить process liveness и readiness, которая проверяет runtime-config/полный seed, current business migrations, artifact writes, Procrastinate schema version и `healthchecks`, в `apps/api/src/review_api/routes/health.py`
- [ ] T089 [US3] Создать non-secret operator configuration example, полный versioned `deploy/compose/config/runtime-config.synthetic.v1.json` с одной exact trusted binding и read-only `trusted-fixture-output.synthetic.v1.json`; вычислить/проверить document/profile/skill/parser/engine/resource digests, оставить root schema default bindings empty и документировать безопасное отключение demo binding в `deploy/compose/env.example` и `docs/operations/configuration.md`
- [ ] T090 [US3] Создать backend-only Dockerfiles, trusted-network proxy and PostgreSQL/API/worker Compose: mount selected runtime config + expected-output resource read-only and make drift fail readiness; one-off `uv run --frozen alembic`/`uv run --frozen procrastinate` commands run inside locked API/worker images after PostgreSQL health; mandatory deterministic profile uses internal no-egress networks, optional provider egress is a separate explicit profile restricted to configured endpoint, в `deploy/compose/`
- [ ] T091 [US3] Прогнать migrations + Procrastinate schema/health, clean packaged-config expected-finding flow, missing/drifted expected-resource readiness negatives, concurrent extraction/idempotency, stage-kill, restart, duplicate delivery, lease recovery, old-snapshot read and cancellation race suites в `tests/integration/` и `tests/e2e/`

**Checkpoint**: default composition durable and self-hosted; all state survives restart; no duplicate side effects; no external model required.

---

## Phase 6 — User Story 4: direct CLI and PoC v1 compatibility (Priority: P2)

**Goal**: тот же application/core без HTTP и read-only deterministic mapping старого PoC.

**Independent Test**: HTTP and direct CLI satisfy one semantic fixture; fresh synthetic PoC maps repeatably and legacy files/hashes/tests remain unchanged.

### Tests first

- [ ] T092 [P] [US4] Написать failing PoC precondition/hash/path/UUIDv5/coverage tests и typed `poc-import-view.v1` schema tests: реальный feature-001 run с отсутствующим context успешно даёт partial source `sha256=null`, `parser=null`, zero fragments + typed gap; available/partial sources без verified SHA/parser отвергаются; invalid finding/anchor/quote/location fails whole mapping with no view/output; legacy non-unreviewed state maps to revision-0 `unreviewed` plus `legacy_human_state_unrepresentable`, never configured actor, в `tests/contract/test_poc_v1_adapter.py`
- [ ] T093 [P] [US4] Написать failing CLI exit-code/safe-stderr/local-output and no-HTTP core tests в `apps/cli/tests/test_cli.py`
- [ ] T094 [P] [US4] Написать failing cross-channel semantic conformance test on one synthetic dataset в `tests/contract/test_channel_semantics.py`

### Implementation

- [ ] T095 [US4] Реализовать read-only PoC directory validator and deterministic identity mapper, возвращающий только schema-valid typed `poc-import-view.v1` либо safe typed failure без partial output, в `packages/review-runtime/src/review_runtime/poc_adapter/reader.py` и `mapping.py`
- [ ] T096 [US4] Реализовать all-or-nothing PoC finding/anchor/quote/location validation и explicit coverage/human-state loss diagnostics; non-unreviewed legacy state становится default `unreviewed` без actor attribution, в `packages/review-runtime/src/review_runtime/poc_adapter/validation.py`
- [ ] T097 [US4] Реализовать CLI app composition and `review`, `contract-smoke`, `read-poc-v1` commands в `apps/cli/src/review_cli/main.py` и `commands/`
- [ ] T098 [US4] Добавить API smoke/evidence/verification CLI commands used by quickstart в `apps/cli/src/review_cli/commands/api_smoke.py`
- [ ] T099 [US4] Выполнить fresh synthetic PoC golden mapping twice и отдельный feature-001 prepare/mapping с реально отсутствующим context; доказать stable typed view/IDs, nullable unavailable-source metadata, all-or-nothing invalid-input behavior and no legacy writes в `tests/contract/test_poc_v1_adapter.py`
- [ ] T100 [US4] Прогнать unchanged feature 001 suite через `uv run --project implementation/poc/review-data-spec --frozen --extra test pytest ...` и record no-diff/hash guard в `tests/contract/test_poc_v1_regression.py`
- [ ] T101 [US4] Прогнать direct/HTTP semantic suite and ensure no client paths/data in output в `tests/contract/test_channel_semantics.py`

**Checkpoint**: local channel and service share domain semantics; PoC remains immutable and readable only through explicit adapter.

---

## Phase 7 — User Story 5: optional free local/OpenAI-compatible model (Priority: P3)

**Goal**: provider adapter usable when explicitly configured; zero automatic install/download and zero impact on mandatory deterministic release.

**Independent Test**: fake OpenAI-compatible server exercises capabilities/results/errors; an already available local endpoint optionally passes or safely skips.

### Tests first

- [ ] T102 [P] [US5] Написать failing adapter tests capabilities/structured output/timeout/retry/rate/auth/content/context/error redaction against fake server в `packages/review-runtime/tests/test_openai_compatible_model.py`
- [ ] T103 [P] [US5] Написать failing server-side config/secret-ref/exact endpoint + redirect/DNS/outbound allowlist tests и availability projection matrix `available|unavailable|degraded|unknown|missing|expired`→canonical HTTP enum, совместимые с explicit optional-egress Compose profile, в `packages/review-runtime/tests/test_model_profile_config.py`
- [ ] T104 [P] [US5] Написать opt-in local endpoint smoke with explicit skip and no-download assertion в `tests/e2e/test_optional_local_model.py`

### Implementation

- [ ] T105 [US5] Реализовать OpenAI-compatible HTTP ModelGateway, normalized capabilities/results/errors and bounded timeout в `packages/review-runtime/src/review_runtime/models/openai_compatible.py`
- [ ] T106 [US5] Реализовать secret provider resolution and exact configured endpoint/redirect allowlist without fallback, DNS escape or telemetry в `packages/review-runtime/src/review_runtime/models/config.py`
- [ ] T107 [US5] Добавить operator-only optional model profile configuration and safe availability projection: only fresh internal `available` becomes HTTP `available`; `unavailable|degraded|unknown|missing|expired` becomes HTTP `unavailable`, в `packages/review-runtime/src/review_runtime/config/model_profiles.py`
- [ ] T108 [US5] Реализовать read-only local endpoint discovery/model-smoke CLI without install/download behavior в `apps/cli/src/review_cli/commands/model_smoke.py`
- [ ] T109 [US5] Прогнать fake-provider suite и optional existing-local-endpoint smoke/skip, сохранив deterministic gates unchanged в `tests/e2e/test_optional_local_model.py`

**Checkpoint**: optional adapter conforms technically; absence or low quality of local model never fails mandatory release.

---

## Phase 8 — Release hardening and complete verification

**Purpose**: собрать доказательства всех требований, а не добавлять новый product scope.

- [ ] T110 [P] Документировать business/Procrastinate schema lifecycle, startup/shutdown, extraction/execution/outbox leases, stalled/stage-kill recovery, staging/promoted orphan cleanup, model config and unresolved retention/backup/SLO в `docs/operations/backend.md`
- [ ] T111 [P] Добавить property/fuzz cases for duplicate JSON keys, hostile locators, traversal, invalid UTF-8 and concurrency seeds в `tests/security/test_hostile_inputs.py`
- [ ] T112 [P] Добавить log/Problem/queue/image/wheel canary scan across success/failure/retry/cancel/unexpected exception paths в `tests/security/test_redacted_outputs.py`
- [ ] T113 [P] Добавить application-socket и Compose-network tests: API/worker mandatory profile не имеет внешнего egress, а explicit optional profile достигает только configured endpoint без redirect/DNS bypass, в `tests/security/test_outbound_connections.py`
- [ ] T114 [P] Реализовать `make release-check` поверх owned Make targets, включая locked rebuild, scans, protected paths, isolated Compose smoke/restart/cleanup, dependency/image vulnerability and license inventory; отдельный sub-gate создаёт temporary `git archive` export, утверждает отсутствие `client-materials/` и запускает там locked package build + public unit/contract suites, в `.github/workflows/ci.yml`, `Makefile` и `tools/release/check_no_client_dependency.py`
- [ ] T115 Проверить каждый FR-001–FR-050 и SC-001–SC-014 against passing evidence matrix в `specs/003-backend-implementation/contracts/test-matrix.md`
- [ ] T116 Выполнить все команды `specs/003-backend-implementation/quickstart.md` в clean environment, включая business + Procrastinate schema setup/health, exact PoC path и real package unit paths, и исправить documentation/implementation drift
- [ ] T117 Выполнить `uv sync --locked`, lint/type checks, contract, unit, integration, migration, security and E2E suites via `make release-check`
- [ ] T118 Проверить git diff guards: zero change under `apps/web/`, `client-materials/`, `specs/001-*`, `specs/002-*` and PoC artifacts; only approved root contract v1.0.2 delta plus feature/backend files
- [ ] T119 Зафиксировать exact commands/results, JCS vectors, full seed/readiness, budget/partial-primary/idempotency/lease/stage-kill/egress evidence, optional local-model outcome and known production limitations в `docs/operations/release-evidence.md`
- [ ] T120 Обновить все завершённые checkboxes в `specs/003-backend-implementation/tasks.md` и убедиться, что незавершённых task markers нет

**Final Checkpoint**: all 120 tasks checked, all mandatory suites green, clean self-hosted deterministic flow works after restart, protected lanes intact. Product hypotheses remain unconfirmed.

---

## Dependencies and execution order

```text
Phase 1 contract/scaffold
  -> Phase 2 domain/ports/fakes
     -> US1 Slice 3A/3B fixture tracer
        -> US1 Slice 3C/3D real engine
           -> US2 dialogue/decision
              -> US3 POSIX + PostgreSQL + outbox + worker + Compose
                 -> US4 CLI/PoC
                 -> US5 optional provider
                    -> Phase 8 release verification
```

Hard gates:

- T002 MUST fail against v1.0.1 before T003 changes OpenAPI; T004 MUST fail before T005 changes the internal job contract/validator. T002–T005 complete before any route DTO or job producer is considered stable.
- T025–T038 fixture tracer completes before T039–T053 real engine.
- T067 POSIX tests/T074 implementation precede durable document/report DB references T075–T081.
- T068–T073, including queue schema/health, extraction/idempotency races, attempt-specific outbox, leases and stage-kill recovery, fail before T074–T091 durability code.
- T091 durable restart/duplicate-delivery gate completes before optional real provider T102–T109.
- T110–T120 do not waive a failed earlier checkpoint.

## Parallel opportunities

- In Phase 1, contract tooling, job schema tests and package manifests can run in parallel after T002/T003 ownership is clear.
- In Phase 2, fixture generation, domain/canonical/profile tests and config/API skeleton touch disjoint files.
- Within each user story, tasks explicitly marked `[P]` are tests in separate files and may be authored together; implementations sharing application files remain sequential.
- US4 PoC/CLI and US5 provider can start in parallel only after durable checkpoint T091, because both use final composition/config boundaries.
- Phase 8 security/docs tasks may run in parallel, but final evidence T115–T120 is sequential.

## Implementation strategy

### MVP first

Phase 1 + Phase 2 + US1 Slice 3A/3B produce the earliest web-integratable FastAPI tracer without pretending engine completeness. Immediately continue to real US1 because the user requested a fully working backend, not a fixture-only handoff.

### Autonomous continuation

The user pre-approved all listed slices and asked not to stop for intermediate confirmations. At each checkpoint: run tests, diagnose failures, record task completion and continue if scope/public contract has not expanded. Stop only for a genuine requirement of new authority such as a breaking HTTP v2 decision, destructive user-data action, paid credential or unavoidable external coordination.

### Definition of Done

- Every checkbox T001–T120 is `[x]` with corresponding diff/evidence.
- All backend-owned root OpenAPI v1.0.2 operations and skill schemas have passing tests; no undocumented breaking diff.
- Real parser/engine/deterministic adapter runs exact trusted-fixture flow and arbitrary partial/all-primary-gap flow without egress.
- Report bytes/ETag immutable across dialogue, decision and restart; invalid output never publishes.
- PostgreSQL/POSIX/outbox/worker survive restart, concurrent extraction/idempotency, attempt-specific duplicate delivery, lease expiry, stage-kill and cancellation race; full configuration/skill seed and both DB schemas are healthy.
- Direct CLI and all-or-nothing typed PoC reader conform; legacy non-unreviewed state is never attributed to configured actor; feature 001 tests/artifacts unchanged.
- Optional local model passes through common adapter or is safely skipped; mandatory gate remains independent.
- Clean Compose readiness/smoke and all locked test suites pass.
- No web implementation or client-materials/client content enters common fixtures, portable packages, release images or safe logs; explicitly content-bearing workspace API responses remain covered by namespace tests.
