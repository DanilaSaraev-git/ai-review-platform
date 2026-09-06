# Tasks: Гостевой доступ

Вход: [spec.md](spec.md), [plan.md](plan.md). Отметка `[X]` означает выполненную работу; пройденные проверки перечислены отдельно в [evidence.md](evidence.md). Выпуск на реальный сервер не считается выполненным по результату локальных тестов.

## Реализация

- [X] T001 Зафиксировать отдельный guest-v1 контракт, generator `tools/contracts/build_guest_contract.py`, OpenAPI, README и changelog с сохранением canonical trusted v1.
- [X] T002 Добавить миграцию `20260906_0003_guest_sessions`, hash-based session store и 30-дневное rolling expiry в `packages/review-runtime/`.
- [X] T003 Подключить session bootstrap, same-origin проверки и request-scoped platform/runtime ко всем предметным API routes в `apps/api/`.
- [X] T004 Реализовать `PostgresReviewPlatform.for_guest`, registry с single-flight/idle cleanup, общий model client/semaphore и reconciliation зарегистрированных пространств.
- [X] T005 Вернуть 404 для foreign/unknown report ID; сохранить 409 для собственного неопубликованного отчёта.
- [X] T006 Добавить `guest_storage.py`: личные и общие квоты загрузок, резерв диска, сериализацию конкурентного сохранения.
- [X] T007 Настроить guest toggle gateway/API, приватный `/demo` и fail-closed проверку согласованности режимов в `deploy/compose/`.
- [X] T008 Добавить lifecycle unit tests и real PostgreSQL/gateway integration сценарии двух гостей в соответствующие test suites.
- [X] T009 Оформить ADR, глоссарий, AGENTS, README, spec/plan/tasks/evidence; связать опциональный guest-v1 с trusted default.

## Проверки и выпуск

- [X] T010 Пройти focused registry/coordinator tests, Ruff и Mypy по изменённым runtime файлам; сохранить результат в evidence.
- [X] T011 Пройти integration сценарии cookie, доступа, профилей/контекста, concurrency, restart и квот; записать точный итог в evidence.
- [X] T012 Пройти gateway и contract gates, проверить регенерацию guest OpenAPI и отсутствие изменения trusted-v1 DTO.
- [X] T013 Проверить Markdown-ссылки и `CLAUDE.md -> AGENTS.md`; зафиксировать результат.
- [ ] T014 Подготовить проверенную версию и резервную копию для выпуска, применить миграцию и обновить существующий сервис с сохранением runtime volumes.
- [ ] T015 Проверить реальный HTTPS-вход без кода, отдельные браузерные сессии, приватность `/demo` и persistence; записать release и результат, затем завершить срез.

T011–T013 предшествуют T014; T015 завершает работу. Runtime, session store, gateway tests и документация готовятся параллельно при раздельном владении файлами.

Общий локальный gate пройден: backend 378 passed / 7 skipped (opt-in Docker сценарии отдельно пройдены), Ruff, Mypy, contract tooling и web проверки. T014–T015 остаются незавершёнными до реального выпуска и проверки опубликованного сервиса; результаты ведутся в evidence.
