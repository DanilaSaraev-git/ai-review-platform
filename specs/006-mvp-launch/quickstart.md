# Quickstart validation: 006

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
