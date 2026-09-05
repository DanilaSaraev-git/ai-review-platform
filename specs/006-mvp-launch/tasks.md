# Tasks: 006 MVP launch

Input: [spec](spec.md), [plan](plan.md), [research](research.md), [data-model](data-model.md), [contracts](contracts/README.md), [quickstart](quickstart.md).
Tests обязательны по FR-014. Координатор отмечает задачи только по evidence. Пользователь разрешил все этапы автономно; внешний блокер не останавливает независимые задачи. Программирование — GPT-5.6 Sol High.

## Phase 1 — Setup / SpecKit

- [X] T001 Определить актуальный baseline и раздельное владение в specs/006-mvp-launch/research.md.
- [X] T002 Оформить spec, plan и quality checklist в specs/006-mvp-launch/.
- [X] T003 Описать контракты, модель, проверки и задачи в specs/006-mvp-launch/; зафиксировать этап отдельным коммитом.

## Phase 2 — Foundational baseline

- [X] T004 [P] Проверить исходные web typecheck/lint/unit/build/Playwright в apps/web/ и записать результат в specs/006-mvp-launch/evidence.md.
- [X] T005 [P] Проверить backend/runtime baseline и существующий unconfigured/model admission в packages/review-runtime/ и tests/; записать диагностированные дефекты.
- [X] T006 [P] Проверить существующий сервер/overlay/access/backups и записать план поставки в docs/operations/.

## Phase 3 — US1 / Slice 1 / visual commit

- [X] T007 [US1] Упростить навигацию, типографику, surfaces и hierarchy в apps/web/src/app/layout/ и apps/web/src/styles/index.css, убрать fake controls.
- [X] T008 [US1] Упростить подготовку и историю в apps/web/src/features/new-review/ и apps/web/src/features/review-run/, context оставить выдвижным.
- [X] T009 [US1] Обеспечить стабильный document/right-panel layout и раскрываемые детали в apps/web/src/features/review-report/; адаптивность, loading/empty/error/focus состояния.
- [X] T010 [US1] Проверить visual slice web gates и визуально 1440/1280/390; обновить apps/web/README.md, сделать отдельный visual commit.

## Phase 4 — US2 / Slice 2 / functional commits

- [X] T011 [US2] Проверить и исправить реальные dialogue/decision/refetch/retry/conflict/draft paths в apps/web/src/features/finding-dialogue/, apps/web/src/features/finding-decision/ и связанные e2e.
- [X] T012 [P] [US2] Реализовать честный unconfigured runtime/model unavailable в packages/review-runtime/ и regression tests; fixture оставить явным тестовым режимом.
- [X] T013 [P] [US2] Проверить и обеспечить runtime-config limits для admission/upload/context/dialogue в apps/api/, packages/review-core/, packages/review-runtime/ и tests/.
- [X] T014 [US2] Пройти synthetic flow, conflicts/retry и report immutability/reload/restart в apps/web/e2e/ и tests/; отдельные functional web и backend коммиты, results в evidence.

## Phase 5 — US3 / Slice 3 / gateway and release

- [X] T015 [P] [US3] Перенести web/API production build и Compose setup в deploy/ без неучтённого серверного overlay; unconfigured production default, persistent volumes и ограниченные logs.
- [X] T016 [US3] Подготовить TLS/gateway для всех data routes, private API/DB, secret-file config и renewal в deploy/ и tools/ops/; публичный plaintext не принимает документы/пароли.
- [X] T017 [US3] Подготовить operator model connection и unavailable preflight в tools/ops/ и docs/operations/; не вызывать реальную модель.
- [X] T018 [US3] Проверить build/config, отрицательный/положительный gateway доступ, сертификат и unavailable model; deployment commit и ops evidence.

## Phase 6 — US4 / Slice 3–4 / recovery and deployment

- [X] T019 [P] [US4] Реализовать согласованные backup/retention/schedule, isolated restore и rollback в tools/ops/, deploy/ и docs/operations/.
- [X] T020 [US4] Пройти изолированное восстановление и проверить сохранность синтетических документов/отчёта/диалога; результат в specs/006-mvp-launch/evidence.md.
- [X] T021 [US4] Создать predeploy backup и установить проверенный release на существующий сервер с сохранением предыдущей версии; записать release hash в evidence.
- [ ] T022 [US4] Проверить внешний доступ, health, model unavailable, persistence/restart и renewal/backup timers; записать результаты и инструкцию отката в docs/operations/.

## Phase 7 — Final validation

- [ ] T023 Проверить spec/plan/tasks consistency через SpecKit analyze и convergence, закрыть реальные gaps и обновить specs/006-mvp-launch/evidence.md.
- [ ] T024 Проверить локальные ссылки и CLAUDE.md -> AGENTS.md; включить 006 и operator guide в README.md, зафиксировать финальный документационный коммит.
- [ ] T025 Зафиксировать итог: URL и способ доступа, commits/rollback, подключение модели и явные блокеры в specs/006-mvp-launch/evidence.md и ответе пользователю.

## Dependencies

T001–T004 выполнены на baseline. T005/T006 параллельны. T007–T010 visual precedes T011 web integration; T012/T013 backend independent. T015/T016/T019 preparation parallel to web/backend; T017 зависит от T012. T018 зависит от готовой конфигурации. T020 не трогает production data. T021 ждёт T010/T014/T018 и backup. T022 затем T023–T025. Только coordinator редактирует этот файл; agents report task IDs.

## Commit strategy

SpecKit baseline → visual → backend semantics → functional web → deployment/recovery → validation/docs. Параллельные commits могут поменяться местами; каждый содержит только свою область. Индекс общий, staging строго явный. Откат приложения не означает восстановление БД; рабочие volumes не удаляются.

## Phase 8: Convergence

- [X] T026 Исправить переход unconfigured→ML с внешним model profile в packages/review-runtime/src/review_runtime/postgres/platform.py и regression tests: исключить immutable identity drift и доступный fixture profile в production ML, проверить operator configuration без реального provider request per FR-008, FR-013, SC-008 (contradicts, HIGH).

## Phase 9: Convergence

- [X] T027 Замкнуть operator model availability в packages/review-runtime/, apps/cli/ и tools/ops/: declared non-generative probe сохраняет наблюдение и обновляет его до истечения; model-enable не требует ручного SQL и не вызывает генерацию; failed/missing probe возвращает понятное недоступное состояние. Проверить configure→probe→available→review admission на fake provider, failure/expiry и отсутствие генерации в readiness per FR-008, FR-013, SC-008 (missing, HIGH).

## Phase 10: Convergence

- [X] T028 Восстановить публикацию канонической схемы по `/openapi.json` в apps/api/ для существующей API docs, проверить маршрут и закрытый gateway доступ per FR-009, FR-014 (missing, MEDIUM).

## Phase 11: Convergence

- [X] T029 Согласовать CI protected-path gate с принятым web stage в tools/contracts/check_protected_paths.py: проверить неизменность остальных защищённых каталогов, закрепить одобренный полный commit SHA интерфейса как baseline и выполнить стандартную проверку без временных allow-path per FR-014, FR-015 (missing, HIGH).

## Phase 12: Convergence

- [ ] T030 Исправить обнаруженный при фактическом promotion drift deployment labels в tools/ops/: capture полного legacy environment, согласование labels до seed новой/старой версии, восстановление прежнего состояния при failure; пройти existing→new→legacy→new без потери данных per FR-011, FR-012, FR-015 (contradicts, HIGH).
