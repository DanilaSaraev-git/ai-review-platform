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

Гостевые загрузки обрабатываются параллельно с атомарным резервированием квоты.
Исправление и миграция `20260906_0005` проверены локально; результаты и границы —
в [evidence параллельной загрузки](specs/008-guest-access/evidence.md#локальное-исправление-параллельной-загрузки--2026-09-06).
Правка включена в продовый выпуск `2fca13f`; [результаты выкладки](docs/operations/deployment.md#продовый-выпуск-объединённых-правок--2026-09-06).

[Доступность LLM-провайдеров из России](docs/operations/provider-availability.md): обзор официальных каталогов и условий на 2026-09-06, ограничения внешних моделей и непроверенные параметры подключения.

Объединённые текущие правки проверены на [локальном стенде](http://localhost:18101/new). Состав, результаты и статус удалённой выкладки — в [журнале интеграции](docs/operations/deployment.md#объединённое-локальное-обновление--2026-09-06).

## Локальная разработка

Из корня технического checkout выполните `./dev start`, затем откройте [http://localhost:5173](http://localhost:5173). Web работает с Vite HMR, API — с `uvicorn --reload`, PostgreSQL хранит данные в отдельном локальном volume. `./dev stop` останавливает этот стенд и сохраняет документы и отчёты; `./dev status` и `./dev logs` показывают состояние и журналы.

По умолчанию выбран OpenAI `gpt-5.4-mini`; явный выбор — `./dev start --model openai`, Kimi K2 — `./dev start --model kimi`. Перед сменой выполните `./dev stop`. Ключ OpenAI нужно добавить через локальный редактор в приватный `~/.config/ai-analytics-review/openai.token`; точный порядок, зависимости, хранение данных и особенности reload: [руководство локальной разработки](docs/operations/local-development.md). Объём работ: [SpecKit 007](specs/007-local-dev-loop/spec.md), [план](specs/007-local-dev-loop/plan.md), [задачи](specs/007-local-dev-loop/tasks.md) и [результаты прежних проверок](specs/007-local-dev-loop/evidence.md).

## Ветки реализации

- `main` — общий архитектурный и контрактный baseline;
- `codex/003-backend-implementation` — backend MVP;
- `codex/004-llm-review-integration` — инженерный слой LLM-интеграции; real endpoint и предметный harness подключаются отдельно;
- `codex/005-web-review-ui` — web v1;
- `codex/mvp-launch-20260905` — упрощённый интерфейс и выпуск MVP.

Инженерная feature 004 интегрирована: review, dialogue, same-turn retry, immutable report, restart reconciliation, mounted-file secrets, direct CLI и opt-in Compose проверены на synthetic gate. На проде через Yandex AI Studio подключены GPT-OSS 20B (по умолчанию), Qwen3.6 35B и DeepSeek V4 Flash; [результаты подключения](docs/operations/deployment.md#дополнение-каталога-моделей--2026-09-07) отделены от предметной оценки. Chunking и auto-repair остаются в [backlog](specs/004-llm-review-integration/backlog.md).

## Цикл документа и PDF

Основа цикла реализована по [SpecKit 009](specs/009-document-review-cycle/spec.md). Рабочий интерфейс объединён по [SpecKit 010](specs/010-unified-review/spec.md), [плану](specs/010-unified-review/plan.md) и [задачам](specs/010-unified-review/tasks.md): одна карточка «Проверка», история внутри результата, новая версия через диалог загрузки. Статус показывает следующий шаг, завершение подтверждает пользователь. В диалог замечания можно прикрепить источники; первое сообщение содержит вопрос из отчёта. PDF содержит снимок текущих решений и ограничений. Результаты локальной проверки и её границы — в [evidence 010](specs/010-unified-review/evidence.md).

Локальная приёмка завершена; фактические результаты и границы собраны в [evidence](specs/009-document-review-cycle/evidence.md). Удалённая выкладка требует отдельной команды пользователя. Точность на реальных документах этим не подтверждается.

Активную проверку можно отменить кнопкой «Отменить проверку» на её экране. После подтверждения сервером статус «Отменена» отображается в результате, истории и списке; отчёт не публикуется. Готовый отчёт отменить нельзя. Локальные проверки функции описаны в [evidence 010](specs/010-unified-review/evidence.md#отмена-запуска-проверки).

## Подготовка MVP

Срез [006 MVP launch](specs/006-mvp-launch/spec.md) реализован и развёрнут: упрощён веб-интерфейс, завершены диалоги по замечаниям и подготовлен защищённый сервис для одной доверенной группы. Работа выполнена по [плану](specs/006-mvp-launch/plan.md) и [задачам SpecKit](specs/006-mvp-launch/tasks.md), отдельными коммитами. DeepSeek подключена с успешным GET probe, без пробных генераций по поручению пользователя. Исторический smoke Kimi не подтверждает совместимость ответов DeepSeek. Фактически пройденные проверки и ограничения собраны в [evidence](specs/006-mvp-launch/evidence.md). Предметная оценка модели выполняется отдельно.

Сборка, установка, доступ, резервные копии, восстановление, откат и подключение модели описаны в [руководстве оператора](docs/operations/deployment.md).

Отдельный `/demo/new` показывает заранее подготовленный разбор документа без вызовов модели. Материалы примера подключаются приватным runtime-пакетом; в код и образ входят только универсальный сценарий и синтетические проверки. Порядок подключения описан в [разделе деморежима](docs/operations/deployment.md#отдельный-демонстрационный-разбор).

## DeepSeek через Яндекс

Для Yandex AI Studio подключён профиль DeepSeek V4 Flash, добавлены сохранение API-ключа вне Git и
renderer профиля с ID каталога. [Настройка подключения](docs/operations/configuration.md#deepseek-через-yandex-ai-studio).
По поручению пользователя эта интеграция включена без пробных генераций; GET списка моделей
и readiness не считаются проверкой качества ревью.

Подключение OpenAI подготовлено в коде и локальных настройках; серверная выкладка этого изменения не выполнялась. По поручению пользователя для него тесты не добавлялись и не запускались, бенчмарки, probes и платные вызовы не выполнялись. Работоспособность OpenAI реальным запросом не проверялась.

## Лицензирование

Корневая лицензия намеренно отсутствует. Публичная доступность исходного кода не предоставляет разрешения на его использование, копирование, изменение или распространение и не делает проект open source. Лицензии встроенных сторонних материалов перечислены в [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) и применяются только к соответствующим материалам.

## Безопасность

Не коммитьте клиентские документы, реальные credentials, `.env`, журналы с содержимым документов и локальные абсолютные пути. Порядок сообщения о проблемах описан в [SECURITY.md](SECURITY.md).
