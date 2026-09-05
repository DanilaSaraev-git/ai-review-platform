# AI Review — веб-интерфейс v1

Интерфейс предварительного ревью ТЗ на данные для аналитика: загрузка документа,
фоновая проверка, разбор адресных замечаний, диалог по замечанию и решение
человека.

Спецификация, план и задачи: [`specs/003-web-review-ui/`](../../specs/003-web-review-ui/).
Контракт HTTP: [`contracts/review-platform/v1/`](../../contracts/review-platform/v1/).

## Требования

- Node.js 24.20.0 LTS (проект собирается и на 22.21.0, целевой версией остаётся 24.20.0)
- npm

## Установка и генерация клиента

```bash
npm ci
npm run api:generate
```

Генерация обязательна перед сборкой, типизацией и тестами: каталог
`src/api/generated/` не хранится в репозитории. Единственный источник — 
`contracts/review-platform/v1/openapi.yaml`. Ручные копии DTO запрещены; если
повторный запуск генерации даёт diff, значит сгенерированный файл правили
руками либо он разошёлся с контрактом — исправление вносится в источник
(принцип II, [contracts/orval.md](../../specs/003-web-review-ui/contracts/orval.md)).

## Запуск против моков

Сценарий обязателен: без `VITE_MSW_SCENARIO` worker моков не запускается и
приложение уходит в реальный backend, которого в v1 ещё нет.

```bash
VITE_MSW_SCENARIO=happy-path npm run dev          # основной сценарий
VITE_MSW_SCENARIO=report-partial npm run dev      # частичный отчёт
VITE_MSW_SCENARIO=decision-conflict npm run dev   # конфликт ревизии решения
```

В PowerShell переменная задаётся отдельной командой:

```powershell
$env:VITE_MSW_SCENARIO='happy-path'; npm run dev
```

Доступные сценарии перечислены в
[contracts/msw-scenarios.md](../../specs/003-web-review-ui/contracts/msw-scenarios.md)
и собраны в `src/mocks/scenarios/`. Все данные синтетические: материалы кейса
в интерфейс не переносятся (принцип VI).

## Проверки

```bash
npm run typecheck
npm run lint
npm test          # Vitest + Testing Library
npm run test:e2e  # Playwright против MSW
npm run build
```

## Переключение на реальный backend

```bash
VITE_API_BASE_URL=https://<host>/api npm run dev
```

Если `VITE_MSW_SCENARIO` не задан, worker моков не запускается и приложение идёт
в реальный API. Меняется только транспорт: компоненты, hooks и DTO остаются
теми же (принцип III).

## Структура

| Каталог | Назначение |
| --- | --- |
| `src/api/` | mutator, разбор ошибок, правила опроса, ключи кэша, идемпотентность |
| `src/api/generated/` | Orval: типы, клиент, query hooks, MSW handlers (не коммитится) |
| `src/app/` | провайдеры, маршруты, каркас страницы |
| `src/features/new-review/` | подготовка запуска: документ, контекст, профили |
| `src/features/review-run/` | список запусков и наблюдение за состоянием |
| `src/features/review-report/` | отчёт, замечания, охват, источники |
| `src/features/finding-decision/` | решение человека и конфликт ревизии |
| `src/features/finding-dialogue/` | диалог по одному замечанию |
| `src/components/document-viewer/` | просмотр PDF и текста, переход к фрагменту |
| `src/mocks/` | сценарии и синтетические фикстуры |
| `e2e/` | сквозные проверки Playwright |
