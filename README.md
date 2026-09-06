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

Опциональный гостевой доступ без регистрации описан в [SpecKit 008](specs/008-guest-access/spec.md), [плане](specs/008-guest-access/plan.md), [задачах](specs/008-guest-access/tasks.md) и [evidence](specs/008-guest-access/evidence.md). [Guest-v1](contracts/review-platform/guest-v1/README.md) сохраняет форматы данных trusted v1 и отдельно задаёт cookie, изоляцию и лимиты хранения; [ADR-0002](docs/adr/0002-optional-guest-workspaces.md) уточняет границу deployment. Статус реального выпуска ведётся в evidence.

## Локальная разработка

Из корня технического checkout выполните `./dev start`, затем откройте [http://localhost:5173](http://localhost:5173). Web работает с Vite HMR, API — с `uvicorn --reload`, PostgreSQL хранит данные в отдельном локальном volume. `./dev stop` останавливает этот стенд и сохраняет документы и отчёты; `./dev status` и `./dev logs` показывают состояние и журналы.

Зависимости, credential Kimi K2, хранение данных и особенности reload: [руководство локальной разработки](docs/operations/local-development.md). Объём работ: [SpecKit 007](specs/007-local-dev-loop/spec.md), [план](specs/007-local-dev-loop/plan.md) и [задачи](specs/007-local-dev-loop/tasks.md) и [результаты проверок](specs/007-local-dev-loop/evidence.md).

## Ветки реализации

- `main` — общий архитектурный и контрактный baseline;
- `codex/003-backend-implementation` — backend MVP;
- `codex/004-llm-review-integration` — инженерный слой LLM-интеграции; real endpoint и предметный harness подключаются отдельно;
- `codex/005-web-review-ui` — web v1;
- `codex/mvp-launch-20260905` — упрощённый интерфейс и выпуск MVP.

Инженерная feature 004 интегрирована: review, dialogue, same-turn retry, immutable report, restart reconciliation, mounted-file secrets, direct CLI и opt-in Compose проверены на synthetic gate. Сейчас подключена DeepSeek V4 Flash через Yandex AI Studio; [конфигурация](docs/operations/configuration.md#deepseek-через-yandex-ai-studio) и [серверные результаты](specs/006-mvp-launch/evidence.md) отделены от предметной оценки. Chunking и auto-repair остаются в [backlog](specs/004-llm-review-integration/backlog.md).

## Цикл документа и PDF

Функция реализована по [SpecKit 009](specs/009-document-review-cycle/spec.md), [плану](specs/009-document-review-cycle/plan.md) и [задачам](specs/009-document-review-cycle/tasks.md). Документ объединяет неизменяемые версии и отдельные запуски. Сохранённую версию можно проверить повторно; новую версию загружают в ту же карточку. Сопоставление сохраняет историю замечаний, а исправление подтверждает аналитик. PDF содержит согласованный снимок текущих решений и ограничений выбранной проверки.

Локальная приёмка завершена; фактические результаты и границы собраны в [evidence](specs/009-document-review-cycle/evidence.md). Удалённая выкладка требует отдельной команды пользователя. Точность на реальных документах этим не подтверждается.

## Подготовка MVP

Срез [006 MVP launch](specs/006-mvp-launch/spec.md) реализован и развёрнут: упрощён веб-интерфейс, завершены диалоги по замечаниям и подготовлен защищённый сервис для одной доверенной группы. Работа выполнена по [плану](specs/006-mvp-launch/plan.md) и [задачам SpecKit](specs/006-mvp-launch/tasks.md), отдельными коммитами. DeepSeek подключена с успешным GET probe, без пробных генераций по поручению пользователя. Исторический smoke Kimi не подтверждает совместимость ответов DeepSeek. Фактически пройденные проверки и ограничения собраны в [evidence](specs/006-mvp-launch/evidence.md). Предметная оценка модели выполняется отдельно.

Сборка, установка, доступ, резервные копии, восстановление, откат и подключение модели описаны в [руководстве оператора](docs/operations/deployment.md).

Отдельный `/demo/new` показывает заранее подготовленный разбор документа без вызовов модели. Материалы примера подключаются приватным runtime-пакетом; в код и образ входят только универсальный сценарий и синтетические проверки. Порядок подключения описан в [разделе деморежима](docs/operations/deployment.md#отдельный-демонстрационный-разбор).

## DeepSeek через Яндекс

Для Yandex AI Studio подключён профиль DeepSeek V4 Flash, добавлены сохранение API-ключа вне Git и
renderer профиля с ID каталога. [Настройка подключения](docs/operations/configuration.md#deepseek-через-yandex-ai-studio).
По поручению пользователя эта интеграция включена без пробных генераций; GET списка моделей
и readiness не считаются проверкой качества ревью.

## Лицензирование

Корневая лицензия намеренно отсутствует. Публичная доступность исходного кода не предоставляет разрешения на его использование, копирование, изменение или распространение и не делает проект open source. Лицензии встроенных сторонних материалов перечислены в [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) и применяются только к соответствующим материалам.

## Безопасность

Не коммитьте клиентские документы, реальные credentials, `.env`, журналы с содержимым документов и локальные абсолютные пути. Порядок сообщения о проблемах описан в [SECURITY.md](SECURITY.md).
