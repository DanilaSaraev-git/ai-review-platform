# Implementation Plan: MVP launch

**Branch**: `codex/mvp-launch-20260905` | **Date**: 2026-09-05 | **Spec**: [spec.md](spec.md)

## Summary

Развить интегрированный baseline `2a61354`: упростить web, закрыть функциональные пробелы и подготовить существующий VPS. Модель остаётся внешней зависимостью. Программирование — GPT-5.6 Sol High; координатор ведёт SpecKit, проверку результата и интеграцию.

## Дополнение 2026-09-06 — OpenAI

Минимальные изменения: отдельный профиль, параметры OpenAI и транспортная проекция schema
в существующем адаптере; `./dev start` выбирает OpenAI, `--model kimi` сохраняет Kimi.
Полная валидация и engines остаются существующими. Файловый секрет и активация описаны в
[operations](../../docs/operations/configuration.md#профиль-openai-для-mvp).
По поручению тесты, бенчмарки, probes, API-вызовы и deployment не выполняются;
прежняя стратегия ниже не применяется к этому дополнению. Новый дизайн не требуется.

## Technical Context

Дополнение Yandex от 2026-09-06: отдельный выпуск от установленного production commit;
изменяются только HTTP-заголовки model transport/probe, конфигурация и operator helpers.
Штатные профиль/секрет и model-enable применяются после сборки. Проверки ограничены offline
transport, GET каталога и инфраструктурой; model smoke и прогоны документов не выполняются.

Диагностика после пользовательского запуска: закрытые коды semantic validation сохраняются
в существующем безопасном `error.message`, публичный `error.code` остаётся `validation_failed`.
UI продолжает выбирать тексты по публичному коду. Проверки — синтетические mapper fixtures,
локальный fake provider с отдельной PostgreSQL и UI tests; реальная модель не вызывается.
Потеря диагностики воспроизводится отдельно от неизвестной причины исходного ответа.

- **Language/Version**: TypeScript 6.0.3, React 19.2.8, Node 24; Python 3.14.7.
- **Primary Dependencies**: Vite 8, TanStack Query, Orval, Radix, FastAPI, existing runtime adapters.
- **Storage**: PostgreSQL, POSIX artifacts; изменение схемы не запланировано.
- **Testing**: Vitest/Testing Library/Playwright, pytest, ruff, mypy, contracts, Docker smoke, visual QA.
- **Target Platform**: Ubuntu 24.04 VPS, 2 GiB RAM + 2 GiB swap, 40 GiB disk; desktop/mobile browser.
- **Project Type**: web service, single-process trusted deployment.
- **Performance Goals**: сохранить deadlines/лимиты, проверить admission bounds. Массовая нагрузка и SLA не заявляются.
- **Constraints**: HTTP v1 неизменен; один workspace/shared actor; no accounts/roles; synthetic fixtures; mounted-file secrets.
- **Scale/Scope**: одна доверенная группа на deployment, один VPS.

## Constitution Check

| Принцип AGENTS.md | До дизайна | После дизайна |
| --- | --- | --- |
| I contract first | PASS | PASS — public v1 не меняется |
| II generated client | PASS | PASS — Orval, no hand DTO |
| III independent tests | PASS | PASS — MSW/fake provider плюс live smoke |
| IV trusted deployment | PASS | PASS — gateway вне API, actor не авторизация |
| V immutable report | PASS | PASS — отдельные regression gates |
| VI no customer data | PASS | PASS — клиентские assets не копируются |
| VII ownership | PASS | PASS — web/backend/deploy разделены |

Нарушений нет. Изменение публичного контракта при необходимости выделяется до зависимого кода. Прямое поручение разрешает автономные этапы; checkpoint фиксируется проверками и коммитом.

## Project Structure

- `specs/006-mvp-launch/`: spec, research, data model, contracts, quickstart, tasks, evidence.
- `apps/web/`: shell, документ/правая панель, диалог, решение, web tests.
- `apps/api/`, `packages/review-core/`, `packages/review-runtime/`: необходимые runtime fixes.
- `deploy/`, `tools/ops/`, `docs/operations/`: web/API поставка, gateway, backup, restore, rollback.
- `tests/`: runtime/deployment проверки.

## Slice 1: Визуальное упрощение

**Goal**: классический интерфейс с аккуратной современной типографикой.
**Included**: shell/navigation, один primary action, раскрываемые детали, стабильные панели, responsive/focus.
**Not included**: новые сущности/API.
**Test decision / Verification**: web tests, typecheck/lint/build, визуальная проверка 1440/1280/390; новые tests только на поведение.
**Checkpoint / Stop condition**: отдельный visual commit, работающие interaction tests.

## Slice 2: Завершённый сценарий MVP

**Goal**: review/dialogue/decision и честно неподключённая модель.
**Included**: постоянный документ, hooks/refetch, retry/conflicts/drafts; unconfigured launch runtime; ограничение admission/upload/context/dialogue по runtime settings.
**Not included**: общий чат, RAG, accounts, автоприменение решений, chunking.
**Test decision / Verification**: regression перед fixes; unit/contract/integration/Playwright, immutable report/restart.
**Checkpoint / Stop condition**: отдельные web-functional и runtime коммиты; provider smoke отложен до выбора модели.

## Slice 3: Защищённая воспроизводимая поставка

**Goal**: release/gateway/storage/model settings и эксплуатационные команды.
**Included**: web build из repo, TLS/gateway, persistent volumes, ограниченные logs, backup/restore/rollback, автоматическое renewal/backup где доступно.
**Not included**: покупки, cluster, accounts, реальные LLM запросы.
**Test decision / Verification**: Compose config/build, shell checks, negative access probes, isolated restore drill.
**Checkpoint / Stop condition**: deployment commit; публичные данные только после TLS+gateway. Без сертификата loopback остаётся закрытым, независимая работа продолжается.

## Slice 4: Выпуск и приёмка

**Goal**: установить проверенную версию на VPS и оставить точную инструкцию.
**Included**: predeploy backup, release directory, предыдущая версия, внешний/локальный smoke, model unavailable, evidence/rollback/connect instructions.
**Not included**: качество реальной модели, SLA, изоляция компаний в одном workspace.
**Test decision / Verification**: integrated gates + restart/restore; ссылки, symlink, чистота Git.
**Checkpoint / Stop condition**: recorded release hash; внешние блокеры остаются незавершёнными; рабочие volumes не удаляются.

## Dependencies and coordination

Spec/checklist → visual, backend diagnosis, deployment preparation parallel. Web visual precedes web functional. Release waits for integrated tests. Agents own disjoint paths and stage explicit files. No force push/reset. Existing server overlay inventoried before replacement. Coordinator updates task state from evidence.
