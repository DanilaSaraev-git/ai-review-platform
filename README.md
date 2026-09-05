# AI Review Platform

Технический репозиторий платформы предварительного ревью технических заданий на потоки и витрины данных. Здесь находятся web, backend, worker, CLI, review engine, переносимые навыки, машинные контракты и инфраструктура запуска.

Продуктовые гипотезы, интервью, материалы заказчиков и результаты клиентских экспериментов хранятся отдельно в `ai-review-product`. В этот репозиторий разрешены только синтетические fixtures.

## Карта репозитория

| Каталог | Назначение |
| --- | --- |
| `apps/` | Web, API, worker и CLI |
| `packages/` | Python-модули предметного ядра и runtime adapters |
| `skills/` | Версионируемые переносимые навыки |
| `contracts/review-platform/` | Канонические OpenAPI и JSON Schema |
| `deploy/` | Локальная и self-hosted поставка |
| `tests/` | Общие contract, integration и end-to-end проверки |
| `docs/architecture/` | Целевая архитектура и порядок совместной разработки |
| `docs/adr/` | Принятые технические решения |
| `docs/operations/` | Настройка и эксплуатационные границы runtime |
| `specs/` | Spec Kit-спецификации реализационных срезов |
| `implementation/poc/` | Сохранённый generic PoC и compatibility baseline |

Доменная терминология: [docs/domain-glossary.md](docs/domain-glossary.md). Архитектурный baseline: [docs/architecture/target-product.md](docs/architecture/target-product.md). Публичный контракт: [contracts/review-platform/v1/README.md](contracts/review-platform/v1/README.md). Настройка model runtime: [docs/operations/configuration.md](docs/operations/configuration.md).

## Ветки реализации

- `main` — общий архитектурный и контрактный baseline;
- `codex/003-backend-implementation` — backend MVP;
- `codex/004-llm-review-integration` — инженерный слой LLM-интеграции; real endpoint и предметный harness подключаются отдельно;
- `codex/005-web-review-ui` — web v1;
- `codex/mvp-launch-20260905` — упрощённый интерфейс и выпуск MVP.

Инженерная feature 004 интегрирована: review, dialogue, same-turn retry, immutable report, restart reconciliation, mounted-file secrets, direct CLI и opt-in Compose проверены на synthetic gate. Реальная модель и endpoint не выбраны и не проверялись; chunking и auto-repair остаются в [backlog](specs/004-llm-review-integration/backlog.md).

## Подготовка MVP

Текущий срез [006 MVP launch](specs/006-mvp-launch/spec.md) объединяет упрощение веб-интерфейса, диалоги по замечаниям и подготовку защищённого развёртывания для одной доверенной группы. Работа ведётся через [план](specs/006-mvp-launch/plan.md) и [задачи SpecKit](specs/006-mvp-launch/tasks.md), отдельными коммитами. Фактически пройденные проверки и ограничения собраны в [evidence](specs/006-mvp-launch/evidence.md). Подключение реального endpoint и предметная оценка модели выполняются отдельно.

Сборка, установка, доступ, резервные копии, восстановление, откат и подключение модели описаны в [руководстве оператора](docs/operations/deployment.md).

## Лицензирование

Корневая лицензия намеренно отсутствует. Публичная доступность исходного кода не предоставляет разрешения на его использование, копирование, изменение или распространение и не делает проект open source. Лицензии встроенных сторонних материалов перечислены в [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) и применяются только к соответствующим материалам.

## Безопасность

Не коммитьте клиентские документы, реальные credentials, `.env`, журналы с содержимым документов и локальные абсолютные пути. Порядок сообщения о проблемах описан в [SECURITY.md](SECURITY.md).
