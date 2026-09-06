# Quickstart validation: 006

## OpenAI для MVP — дополнение 2026-09-06

Подготовьте через локальный редактор приватный файл
`~/.config/ai-analytics-review/openai.token`: только значение ключа без `OPENAI_API_KEY=`,
права файла 600 и каталога 700. Затем из технического checkout выберите
`./dev start --model openai` (эквивалентно `./dev start`). Для Kimi выполните `./dev stop`,
затем `./dev start --model kimi`; для возврата к OpenAI тоже нужен `stop`/`start`.
Профиль и ограничения: [configuration.md](../../docs/operations/configuration.md#профиль-openai-для-mvp);
зависимости и секрет: [local-development.md](../../docs/operations/local-development.md).

Это инструкция будущей активации: при запуске launcher обращается к каталогу моделей
негенеративным probe. В ходе подключения сервисы не запускались. По поручению пользователя
тесты не добавлялись и не запускались, бенчмарки, probes, пробные API-запросы и платные
вызовы не выполнялись. Работоспособность OpenAI реальным запросом не проверялась.
Команды проверок ниже сохранены для прежних этапов и не входят в текущее поручение.

## Продолжить работу через SpecKit

В новом checkout явно выберите feature directory; локальная `.specify/feature.json` намеренно не коммитится:

```sh
SPECIFY_FEATURE_DIRECTORY=specs/006-mvp-launch \
  .specify/scripts/bash/check-prerequisites.sh --json --require-spec --require-tasks --include-tasks
```

## Web

Из apps/web:

```sh
npm ci
npm run api:generate
npm run typecheck
npm run lint
npm test
npm run test:e2e
npm run build
```

Проверить synthetic happy-path: загрузка и контекст → запуск → отчёт → выбранное замечание → диалог → human decision → reload. Проверить retry/conflict без потери текста и отсутствие изменения отчёта. Визуально проверить 1440, 1280, 390 пикселей, keyboard focus и длинный текст.

Отдельный сценарий без MSW выполняется против изолированного durable runtime с синтетической моделью. `LIVE_WRITE=1` явно разрешает создавать тестовые документы, ревью, диалоги и решения в этой базе:

```sh
LIVE_WRITE=1 VITE_API_PROXY_TARGET=http://127.0.0.1:18081 npm run test:e2e:live
```

Не направлять этот тест на рабочую базу или платный endpoint.

## Backend

Из корня:

```sh
uv sync --frozen
make lint
make contracts
make test-unit
make test-security
```

Для PostgreSQL integration/migration/restart использовать изолированный Compose project по root Makefile. Не выполнять mvp-reset против рабочего VPS. Production unconfigured profile должен быть unavailable, create-run должен отвергать запуск; fixture gate запускается отдельно.

## Deployment

Точные команды приведены в [руководстве оператора](../../docs/operations/deployment.md). Проверки обязательны: воспроизводимая сборка, config validation, gateway negative/positive HTTP probes, доверенный TLS, private API/DB, health, unavailable model, backup manifest и изолированное восстановление. Перед обновлением сохранить DB+artifacts и прежнюю release directory. После установки проверить startup/restart и отсутствие lost records.

## Evidence

Команды, результаты, commit IDs и оставшиеся блокеры записываются в [evidence.md](evidence.md). Синтетическое исполнение не подтверждает предметное качество реального endpoint.
