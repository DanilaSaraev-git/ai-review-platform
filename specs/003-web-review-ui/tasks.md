---

description: "Задачи реализации веб-интерфейса AI Review v1"
---

# Tasks: Веб-интерфейс AI Review v1

**Input**: Design documents from `specs/003-web-review-ui/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: тесты включены. План фиксирует Vitest + Testing Library для модульных и компонентных проверок и Playwright для E2E; [quickstart.md](quickstart.md) задаёт обязательные позитивные и негативные сценарии.

**Organization**: задачи сгруппированы по User Story спецификации, чтобы каждую историю можно было реализовать и проверить независимо.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: можно выполнять параллельно (разные файлы, нет зависимости от незавершённых задач)
- **[Story]**: к какой User Story относится задача (US1–US5)
- Каждая задача содержит точный путь внутри `apps/web/`

## Path Conventions

Все пути даны от корня репозитория. Единственный изменяемый каталог фичи — `apps/web/` (принцип VII). Каталоги `apps/api/`, `apps/worker/`, `packages/review-core/`, `skills/`, `apps/cli/` этими задачами не создаются и не изменяются.

Каталог `apps/web/src/api/generated/` создаётся только генератором Orval и никогда не правится руками. Задачи, относящиеся к генерации, отделены от задач в `apps/web/src/features/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: инициализация проекта `apps/web/` и инструментов

- [X] T001 Создать каркас `apps/web/` с `apps/web/package.json` (npm, точные версии без диапазонов: TypeScript 6.0.3, React 19.2.8, Vite 8.2.2, React Router 7.18.3, TanStack Query 5.102.8, Orval 8.28.1, MSW 2.15.0; версии Tailwind CSS 4, Radix UI, React Hook Form, Zod, PDF.js, Vitest, Testing Library и Playwright зафиксировать значениями, полученными при установке, по решению R-01) и `apps/web/index.html`
- [X] T002 [P] Настроить TypeScript в `apps/web/tsconfig.json` со строгим режимом и алиасом путей на `src/`
- [X] T003 [P] Настроить сборку и dev-сервер в `apps/web/vite.config.ts`
- [X] T004 [P] Подключить Tailwind CSS 4 в `apps/web/src/styles/index.css` и конфигурации Vite-плагина
- [X] T005 [P] Настроить Vitest в `apps/web/vitest.config.ts` и общую подготовку тестов в `apps/web/src/test/setup.ts`
- [X] T006 [P] Настроить Playwright в `apps/web/playwright.config.ts` с запуском dev-сервера и выбором сценария моков
- [X] T007 [P] Создать `apps/web/.gitignore`, исключив `src/api/generated/` и оставив `package-lock.json` под версионным контролем
- [X] T008 [P] Настроить линтер и форматтер в `apps/web/eslint.config.js` с запретом импорта из каталога `client-materials/` (принцип VI)
- [X] T009 Добавить в `apps/web/package.json` скрипты `api:generate`, `dev`, `build`, `typecheck`, `test`, `test:e2e` (зависит от T001)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: сгенерированный клиент, слой моков и каркас приложения — всё, без чего ни одна User Story не начинается

**⚠️ CRITICAL**: ни одна задача User Story не начинается до завершения этой фазы

### Генерация клиента из зафиксированного контракта

Задачи ниже не затрагивают `apps/web/src/features/`.

- [X] T010 Создать `apps/web/orval.config.ts` с единственным входом `contracts/review-platform/v1/openapi.yaml` и тремя выходами в `apps/web/src/api/generated/`: типы и клиент, query hooks для TanStack Query, MSW handlers — по правилам [contracts/orval.md](contracts/orval.md)
- [X] T011 Реализовать mutator в `apps/web/src/api/http-client.ts`: базовый URL, заголовок `Idempotency-Key` для создающих операций, разбор `application/problem+json`, приведение ответов к внутреннему типу ошибки
- [X] T012 Выполнить `npm run api:generate` и убедиться, что повторный запуск не даёт diff в `apps/web/src/api/generated/`; зафиксировать порядок в `apps/web/README.md`
- [X] T013 [P] Описать внутренний тип ошибки и разбор `Problem` в `apps/web/src/api/errors.ts`: различение `404`, `409 revision_conflict`, `409` повтора идемпотентного ключа и `409` неопубликованного отчёта (решение R-11)
- [X] T014 [P] Реализовать правила наблюдения в `apps/web/src/api/polling.ts`: интервал 2000 мс, признак терминальности запуска и диалога, отключение опроса в терминальном состоянии (решение R-02, SC-012)
- [X] T015 [P] Определить раздельные ключи кэша в `apps/web/src/api/query-keys.ts`: ключ отчёта отделён от ключей `finding-states` и `dialogue`, ключ отчёта не инвалидируется ни одной мутацией (решение R-06, принцип V)
- [X] T016 [P] Реализовать выработку ключа идемпотентности по намерению пользователя в `apps/web/src/api/idempotency.ts` (решение R-05, FR-012)

### Слой моков

- [X] T017 [P] Создать точки входа MSW в `apps/web/src/mocks/browser.ts` и `apps/web/src/mocks/server.ts` поверх сгенерированных handlers
- [X] T018 [P] Добавить синтетические документы для загрузки в `apps/web/src/mocks/fixtures/` (Markdown, обычный текст, PDF); материалы `client-materials/` не используются (принцип VI, FR-038)
- [X] T019 Создать реестр сценариев и выбор по переменной окружения в `apps/web/src/mocks/scenarios/index.ts` по [contracts/msw-scenarios.md](contracts/msw-scenarios.md) (зависит от T017)
- [X] T020 Реализовать сценарий `happy-path` в `apps/web/src/mocks/scenarios/happy-path.ts` на канонических примерах `contracts/review-platform/v1/examples/http/`, включая смену состояний запуска при повторных запросах (зависит от T019)

### Каркас приложения

- [X] T021 [P] Настроить провайдеры в `apps/web/src/app/providers.tsx`: QueryClient с политикой повторов и обработкой ошибок из `src/api/errors.ts`
- [X] T022 Описать маршруты в `apps/web/src/app/router.tsx` по [contracts/routes.md](contracts/routes.md); экранов входа, регистрации, ролей и выбора рабочего пространства нет (FR-002, принцип IV)
- [X] T023 [P] Реализовать каркас страницы в `apps/web/src/app/layout/AppLayout.tsx` без элементов аккаунта и выхода
- [X] T024 Подключить приложение и worker моков в `apps/web/src/main.tsx`: моки включаются только по переменной окружения, прикладной код о них не знает (принцип III)
- [X] T025 [P] Реализовать экран «не найдено» в `apps/web/src/app/NotFoundPage.tsx` без упоминания входа, прав и доступа (FR-003)
- [X] T026 [P] Создать обёртки над Radix UI primitives в `apps/web/src/components/ui/` (диалог, поле, кнопка, вкладки) с подписями и управлением фокусом (FR-041, FR-042)
- [X] T027 [P] Реализовать форматирование дат, длительности и чисел для локали ru-RU в `apps/web/src/lib/format.ts` с явным указанием часового пояса (решение R-14)
- [X] T028 [P] Собрать человекочитаемые тексты по кодам в `apps/web/src/lib/error-messages.ts`: все значения `AsyncError.code`, `CoverageGap.code`, `DialogueError.code` и `blocked_reason` (FR-015, FR-032)

**Checkpoint**: клиент сгенерирован, моки отвечают, каркас маршрутов работает — можно начинать User Story

---

## Phase 3: User Story 1 — Запустить проверку загруженного ТЗ (Priority: P1) 🎯 MVP

**Goal**: аналитик видит рабочее пространство и лимиты, загружает документ, выбирает профили, запускает фоновую проверку и наблюдает её состояние до терминального.

**Independent Test**: открыть интерфейс на сценарии `happy-path`, загрузить синтетический документ, запустить проверку и довести её до терминального состояния, наблюдая смену состояний без обновления страницы.

### Тесты User Story 1

> Написать до реализации и убедиться, что они падают

- [X] T029 [P] [US1] Компонентный тест сводки рабочего пространства и лимитов в `apps/web/src/features/new-review/components/WorkspaceSummary.test.tsx` (FR-001, отсутствие элементов входа)
- [X] T030 [P] [US1] Компонентный тест проверки файла до загрузки в `apps/web/src/features/new-review/lib/validate-upload.test.ts` (FR-006)
- [X] T031 [P] [US1] Компонентный тест доступности запуска по состоянию извлечения в `apps/web/src/features/new-review/lib/run-readiness.test.ts` (FR-040: `failed` запрещает, `partial` разрешает с предупреждением, `pending` ждёт)
- [X] T032 [P] [US1] Компонентный тест отображения всех семи состояний запуска в `apps/web/src/features/review-run/components/RunStatePanel.test.tsx` (FR-013, FR-015)
- [X] T033 [P] [US1] Тест признака «идёт дольше обычного» в `apps/web/src/features/review-run/lib/stall-detector.test.ts` (FR-039, SC-013)

### Реализация User Story 1

- [X] T034 [P] [US1] Реализовать запрос стартовых данных в `apps/web/src/features/new-review/api/use-bootstrap.ts` с кэшированием на сессию вкладки
- [X] T035 [US1] Реализовать сводку рабочего пространства, организации, действующего лица и лимитов в `apps/web/src/features/new-review/components/WorkspaceSummary.tsx` (зависит от T034)
- [X] T036 [P] [US1] Реализовать проверку размера и формата файла по публичным лимитам в `apps/web/src/features/new-review/lib/validate-upload.ts`
- [X] T037 [US1] Реализовать загрузку основного документа в `apps/web/src/features/new-review/components/DocumentUpload.tsx` с показом имени, формата, размера и состояния извлечения (FR-005, зависит от T036)
- [X] T038 [P] [US1] Реализовать правило допуска к запуску по `extraction_state` в `apps/web/src/features/new-review/lib/run-readiness.ts` (FR-040)
- [X] T039 [P] [US1] Реализовать выбор профиля проверки в `apps/web/src/features/new-review/components/ReviewProfileSelect.tsx` с показом назначения и версии (FR-009)
- [X] T040 [P] [US1] Реализовать выбор профиля модели в `apps/web/src/features/new-review/components/ModelProfileSelect.tsx`, делая `availability: unavailable` невыбираемым с причиной (FR-010)
- [X] T041 [US1] Реализовать создание запуска в `apps/web/src/features/new-review/api/use-create-review-run.ts` с ключом идемпотентности из `src/api/idempotency.ts` (FR-011, FR-012, зависит от T016, T038, T039, T040)
- [X] T042 [P] [US1] Реализовать вычисление длительности и признака застревания в `apps/web/src/features/review-run/lib/stall-detector.ts` (порог 15 минут без смены состояния)
- [X] T043 [US1] Реализовать наблюдение за запуском в `apps/web/src/features/review-run/api/use-review-run.ts` с опросом из `src/api/polling.ts` и отключением на терминальном состоянии (FR-014, SC-012)
- [X] T044 [US1] Реализовать экран состояния запуска в `apps/web/src/features/review-run/components/RunStatePanel.tsx`: все семь состояний, пояснение, причина неудачи, признак повтора, зафиксированные версии из `execution_snapshot`, предупреждение о долгом запуске (FR-013, FR-015, FR-017, FR-039; зависит от T042, T043)
- [X] T045 [P] [US1] Реализовать список запусков в обратном хронологическом порядке в `apps/web/src/features/review-run/components/RunList.tsx` (FR-016, US1-8)
- [X] T046 [P] [US1] Добавить сценарии `run-failed`, `run-stalled` и `document-extraction-failed` в `apps/web/src/mocks/scenarios/` по [contracts/msw-scenarios.md](contracts/msw-scenarios.md)
- [X] T047 [US1] Написать E2E-проверку истории в `apps/web/e2e/us1-run-review.spec.ts`: путь от стартовых данных до терминального состояния, повторное нажатие запуска не создаёт второй запуск, неудача показывает причину без отчёта, документ с неудачным извлечением не запускается (SC-002, SC-009, SC-012, SC-013)

**Checkpoint**: User Story 1 работает и проверяется независимо

---

## Phase 4: User Story 2 — Разобрать замечания в неизменяемом отчёте (Priority: P1)

**Goal**: аналитик открывает неизменяемый отчёт, видит замечания с приоритетом и охват проверки и переходит от замечания к процитированному фрагменту документа.

**Independent Test**: открыть отчёт заранее завершённого запуска и для каждого замечания перейти к процитированному фрагменту либо получить явное сообщение о несопоставленном фрагменте.

### Тесты User Story 2

- [X] T048 [P] [US2] Тест неизменяемости кэша отчёта в `apps/web/src/features/review-report/api/use-review-report.test.ts`: мутации решения и диалога не инвалидируют ключ отчёта (FR-018, принцип V)
- [X] T049 [P] [US2] Компонентный тест охвата и пропусков в `apps/web/src/features/review-report/components/CoveragePanel.test.tsx` (FR-022, все коды `CoverageGap`)
- [X] T050 [P] [US2] Компонентный тест пустого отчёта в `apps/web/src/features/review-report/components/FindingList.test.tsx` (FR-023)
- [X] T051 [P] [US2] Тест сопоставления привязки с фрагментом в `apps/web/src/components/document-viewer/use-anchor-highlight.test.ts`: `PdfLocation`, `TextLocation` и случай несопоставленного фрагмента (FR-021, SC-003)

### Реализация User Story 2

- [X] T052 [P] [US2] Реализовать запрос отчёта в `apps/web/src/features/review-report/api/use-review-report.ts` с бесконечным `staleTime` и без инвалидации (решение R-06)
- [X] T053 [P] [US2] Реализовать запрос состояний замечаний в `apps/web/src/features/review-report/api/use-finding-states.ts` отдельным ключом кэша
- [X] T054 [P] [US2] Реализовать сводку и ограничения отчёта в `apps/web/src/features/review-report/components/ReportSummary.tsx` (FR-019)
- [X] T055 [P] [US2] Реализовать панель охвата и пропусков в `apps/web/src/features/review-report/components/CoveragePanel.tsx` (FR-022)
- [X] T056 [P] [US2] Реализовать перечень источников с ролью и статусом в `apps/web/src/features/review-report/components/SourceList.tsx`; ни один источник не исчезает из списка (FR-022)
- [X] T057 [US2] Реализовать список замечаний в устойчивом порядке `ordinal` и содержательное пустое состояние в `apps/web/src/features/review-report/components/FindingList.tsx` (FR-019, FR-023; зависит от T052, T053)
- [X] T058 [US2] Реализовать карточку замечания в `apps/web/src/features/review-report/components/FindingCard.tsx`: тип, заголовок, проблема, причина, вопрос, приоритет с обоснованием (FR-020)
- [X] T059 [P] [US2] Реализовать общий интерфейс просмотрщика документа в `apps/web/src/components/document-viewer/index.tsx` с выбором представления по `location.kind`; представление доступно только для чтения, редактирования исходного документа и создания его новой версии интерфейс не предлагает (FR-007)
- [X] T060 [P] [US2] Реализовать просмотр PDF в `apps/web/src/components/document-viewer/PdfViewer.tsx` на PDF.js с переходом на страницу и подсветкой по нормализованным `rects` (решение R-09)
- [X] T061 [P] [US2] Реализовать текстовое представление в `apps/web/src/components/document-viewer/TextViewer.tsx` с адресацией по строкам и символам `TextLocation`
- [X] T103 [P] [US2] Реализовать безопасный вывод содержимого документа в `apps/web/src/components/document-viewer/sanitize.ts` и подключить его в `TextViewer.tsx`: разметка и скрипты выводятся как текст, HTML не исполняется (FR-043)
- [X] T104 [P] [US2] Тест вывода документа с разметкой и скриптом как текста в `apps/web/src/components/document-viewer/sanitize.test.ts` (FR-043)
- [X] T062 [US2] Реализовать связывание замечания с фрагментом в `apps/web/src/components/document-viewer/use-anchor-highlight.ts`, включая явное сообщение о несопоставленном фрагменте и замечание вида `missing` без привязок (FR-021, SC-003; зависит от T059, T060, T061)
- [X] T063 [P] [US2] Добавить сценарии `report-partial`, `empty-report` и `not-found` в `apps/web/src/mocks/scenarios/`
- [X] T064 [US2] Написать E2E-проверку истории в `apps/web/e2e/us2-review-report.spec.ts`: переход от каждого замечания к фрагменту, частичный охват с причинами пропусков, пустой отчёт, отсутствие отчёта у незавершённого запуска, чужой идентификатор как «не найдено» (SC-003, SC-004, SC-010)
- [X] T105 [P] [US2] Реализовать показ происхождения результата в `apps/web/src/features/review-report/components/ProvenancePanel.tsx`: провайдер, модель, версия модели, безопасные параметры и расход токенов; никакие иные значения конфигурации провайдера не выводятся (FR-004, принцип IV)
- [X] T106 [P] [US2] Тест состава отображаемых сведений о модели в `apps/web/src/features/review-report/components/ProvenancePanel.test.tsx`: показываются только безопасные поля (FR-004)

**Checkpoint**: User Stories 1 и 2 работают независимо

---

## Phase 5: User Story 3 — Сохранить своё решение по замечанию (Priority: P2)

**Goal**: аналитик сохраняет статус, обоснование и резолюцию по замечанию, а конфликт версии не приводит к потере введённого текста.

**Independent Test**: сохранить решение по одному замечанию, обновить страницу и убедиться, что решение сохранено и отделено от текста отчёта.

### Тесты User Story 3

- [X] T065 [P] [US3] Тест правил формы решения в `apps/web/src/features/finding-decision/lib/decision-schema.test.ts`: обязательность обоснования при статусе, отличном от «не рассмотрено», и очистка полей при сбросе (FR-025, FR-026)
- [X] T066 [P] [US3] Компонентный тест конфликта ревизии в `apps/web/src/features/finding-decision/components/DecisionForm.test.tsx`: введённый текст сохраняется, актуальное значение показано, повтор доступен одним действием (FR-027, SC-005)

### Реализация User Story 3

- [X] T067 [P] [US3] Описать схему и правила валидации решения на Zod в `apps/web/src/features/finding-decision/lib/decision-schema.ts` (FR-024 — FR-026)
- [X] T068 [US3] Реализовать сохранение решения в `apps/web/src/features/finding-decision/api/use-put-decision.ts` с передачей `expected_revision` и инвалидацией только `finding-states` и `dialogue` (FR-027, FR-028, принцип V; зависит от T015)
- [X] T069 [P] [US3] Реализовать состояние конфликта ревизии в `apps/web/src/features/finding-decision/lib/conflict.ts` (решение R-07)
- [X] T070 [US3] Реализовать форму решения на React Hook Form в `apps/web/src/features/finding-decision/components/DecisionForm.tsx`: выбор статуса, обоснование, резолюция, сброс в «не рассмотрено» (зависит от T067, T068, T069)
- [X] T071 [US3] Реализовать показ конфликта в `apps/web/src/features/finding-decision/components/RevisionConflictNotice.tsx`: актуальное сохранённое решение рядом с введённым и повтор одним действием (FR-027)
- [X] T072 [P] [US3] Реализовать показ сохранённого решения с автором и временем в `apps/web/src/features/finding-decision/components/DecisionSummary.tsx` (FR-028)
- [X] T073 [P] [US3] Реализовать счётчик разобранных и оставшихся замечаний в `apps/web/src/features/finding-decision/components/DecisionProgress.tsx` (US3-6)
- [X] T074 [P] [US3] Добавить сценарий `decision-conflict` в `apps/web/src/mocks/scenarios/decision-conflict.ts`
- [X] T075 [US3] Написать E2E-проверку истории в `apps/web/e2e/us3-finding-decision.spec.ts`: сохранение решения и его переживание перезагрузки, отказ сохранить без обоснования, конфликт ревизии без потери ввода, сброс решения, неизменность отчёта после решений (SC-005, SC-006)

**Checkpoint**: User Stories 1–3 работают независимо

---

## Phase 6: User Story 4 — Уточнить одно замечание диалогом (Priority: P2)

**Goal**: аналитик задаёт один вопрос по выбранному замечанию, видит ход выполнения и переносит предложенную резолюцию в решение отдельным действием.

**Independent Test**: отправить один вопрос по замечанию и убедиться, что следующий ход недоступен до завершения предыдущего, а причина недоступности названа.

### Тесты User Story 4

- [X] T076 [P] [US4] Компонентный тест доступности отправки в `apps/web/src/features/finding-dialogue/components/TurnComposer.test.tsx`: все значения `blocked_reason` дают текстовую причину (FR-032, SC-008)
- [X] T077 [P] [US4] Компонентный тест переноса предложенной резолюции в `apps/web/src/features/finding-dialogue/components/ProposedResolutionCard.test.tsx`: без отдельного действия решение остаётся «не рассмотрено» (FR-029, SC-007)

### Реализация User Story 4

- [X] T078 [P] [US4] Реализовать запрос диалога с опросом в `apps/web/src/features/finding-dialogue/api/use-finding-dialogue.ts`, включённым только при генерации хода (FR-033, SC-012)
- [X] T079 [US4] Реализовать отправку хода в `apps/web/src/features/finding-dialogue/api/use-create-turn.ts` с `expected_revision` и ключом идемпотентности (FR-031, FR-036; зависит от T016)
- [X] T080 [P] [US4] Реализовать повтор неудавшегося хода в `apps/web/src/features/finding-dialogue/api/use-retry-turn.ts` без повторного ввода вопроса (FR-035)
- [X] T081 [US4] Реализовать панель диалога, привязанную к одному замечанию, в `apps/web/src/features/finding-dialogue/components/DialoguePanel.tsx` (FR-030, зависит от T078)
- [X] T082 [P] [US4] Реализовать историю ходов в порядке отправки в `apps/web/src/features/finding-dialogue/components/TurnList.tsx` с состояниями `queued`, `generating`, `completed`, `failed`
- [X] T083 [US4] Реализовать поле отправки хода в `apps/web/src/features/finding-dialogue/components/TurnComposer.tsx`: доступность строго по `can_send_message`, текстовая причина по `blocked_reason` (FR-031, FR-032; зависит от T028, T079)
- [X] T084 [P] [US4] Реализовать показ ответа в `apps/web/src/features/finding-dialogue/components/AssistantResponseCard.tsx`: текст, вид ответа, привязки, ошибка с признаком повтора (FR-034, FR-035)
- [X] T085 [P] [US4] Реализовать карточку предложенной резолюции в `apps/web/src/features/finding-dialogue/components/ProposedResolutionCard.tsx`: текст и обоснование показаны отдельно от решения, решение остаётся «не рассмотрено» (FR-029)
- [X] T107 [US4] Связать действие «использовать предложение» с полем резолюции формы решения в `apps/web/src/features/finding-dialogue/lib/apply-proposed-resolution.ts`: текст подставляется без сохранения (FR-029, зависит от T070 из US3)
- [X] T086 [US4] Реализовать состояние конфликта ревизии диалога в `apps/web/src/features/finding-dialogue/lib/conflict.ts` с сохранением введённого вопроса (FR-036)
- [X] T087 [P] [US4] Добавить сценарии `dialogue-generating`, `dialogue-failed` и `dialogue-conflict` в `apps/web/src/mocks/scenarios/`
- [X] T088 [US4] Написать E2E-проверку истории в `apps/web/e2e/us4-finding-dialogue.spec.ts`: один ход с блокировкой следующего и названной причиной, повтор неудавшегося хода, перенос резолюции только отдельным действием, конфликт ревизии без потери текста вопроса (SC-007, SC-008)

**Checkpoint**: User Stories 1–4 работают независимо

---

## Phase 7: User Story 5 — Подключить контекстные материалы (Priority: P3)

**Goal**: аналитик подключает контекстные материалы в пределах лимита и видит в отчёте, какие источники учтены, а какие нет.

**Independent Test**: создать запуск с основным и несколькими контекстными синтетическими документами, один из которых недоступен, и убедиться, что отчёт получен и явно отмечает неучтённый источник.

### Тесты User Story 5

- [X] T089 [P] [US5] Тест лимита числа контекстных материалов в `apps/web/src/features/new-review/lib/context-limit.test.ts` (FR-008, US5-2)

### Реализация User Story 5

- [X] T090 [P] [US5] Реализовать правило лимита контекстных документов в `apps/web/src/features/new-review/lib/context-limit.ts` на основе `limits.max_context_documents`
- [X] T091 [US5] Реализовать панель контекстных материалов в `apps/web/src/features/new-review/components/ContextDocuments.tsx`: отдельно от основного документа, с остатком лимита и отказом при его достижении (FR-008, US5-1, US5-2; зависит от T090)
- [X] T092 [US5] Подключить выбранные контекстные документы к созданию запуска в `apps/web/src/features/new-review/api/use-create-review-run.ts` через `context_document_ids` (зависит от T041, T091)
- [X] T093 [P] [US5] Добавить сценарий `context-partial` в `apps/web/src/mocks/scenarios/context-partial.ts`: недоступный контекстный источник даёт частичный отчёт, а не неудачный запуск
- [X] T094 [US5] Написать E2E-проверку истории в `apps/web/e2e/us5-context-documents.spec.ts`: подключение контекста в пределах лимита, отказ при превышении, частичный отчёт с причиной пропуска, неудача запуска при недоступном основном документе (SC-004, US5-4, US5-5)

**Checkpoint**: все User Story работают независимо

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: сквозные свойства, проверяемые только на собранном сценарии

- [X] T095 [P] Написать сквозную проверку неизменяемости отчёта в `apps/web/e2e/report-immutability.spec.ts`: после решений и хода диалога отчёт совпадает по сводке, составу замечаний, охвату и происхождению результата (FR-018, FR-037, SC-006, принцип V)
- [X] T096 [P] Написать проверку прохождения всего сценария с клавиатуры в `apps/web/e2e/a11y-keyboard.spec.ts` (FR-041, SC-014)
- [X] T097 [P] Проверить различимость состояний не только цветом и наличие подписей у полей в `apps/web/src/components/ui/ui.a11y.test.tsx` (FR-042)
- [X] T098 [P] Проверить отсутствие экранов входа, регистрации и управления аккаунтами в `apps/web/e2e/no-auth-surface.spec.ts` (FR-002, SC-010, принцип IV)
- [X] T099 [P] Проверить, что фикстуры и тесты не содержат материалов клиента, в `apps/web/src/mocks/fixtures/fixtures.test.ts` (FR-038, SC-011, принцип VI)
- [X] T100 Добавить проверку генерации без diff в CI в `.github/workflows/web-ci.yml`: `npm ci`, `npm run api:generate`, проверка отсутствия изменений, `typecheck`, `test`, `test:e2e` (принцип II)
- [X] T101 [P] Описать запуск, сценарии моков и переключение на реальный backend в `apps/web/README.md` со ссылкой на [quickstart.md](quickstart.md)
- [X] T102 Пройти проверку по [quickstart.md](quickstart.md) целиком, замерив время первого прохода от загрузки документа до сохранённого решения по одному замечанию (SC-001), и зафиксировать расхождения как задачи, а не как правки сгенерированного клиента

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: без зависимостей
- **Foundational (Phase 2)**: зависит от Setup; блокирует все User Story
- **User Stories (Phase 3–7)**: зависят от завершения Phase 2; далее параллельно или последовательно в порядке приоритета
- **Polish (Phase 8)**: зависит от завершения нужных User Story

### User Story Dependencies

- **US1 (P1)**: начинается сразу после Phase 2, ни от чего не зависит — MVP
- **US2 (P1)**: начинается после Phase 2; для сквозной проверки удобен готовый US1, но история проверяется на сценарии с заранее завершённым запуском
- **US3 (P2)**: начинается после Phase 2; проверяется на отчёте из сценария, независимо от US1
- **US4 (P2)**: начинается после Phase 2. Задача T107 — единственная точка стыка с US3: до её выполнения история проверяется полностью, поскольку независимый тест US4 не затрагивает перенос резолюции
- **US5 (P3)**: начинается после Phase 2; задача T092 расширяет создание запуска из US1

### Внутри User Story

- Тесты пишутся до реализации и сначала падают
- Правила и вычисления (`lib/`) до компонентов, которые их используют
- Запросы и мутации (`api/`) до компонентов, которые их отображают
- E2E-проверка — последняя задача истории

### Parallel Opportunities

- Setup: T002–T008 параллельны
- Foundational: T013–T016 параллельны между собой; T017, T018, T021, T023, T025–T028 параллельны
- US1: T029–T033 параллельны; T034, T036, T038, T039, T040, T042, T045, T046 параллельны
- US2: T048–T051 параллельны; T052–T056, T059–T061, T063, T103–T106 параллельны
- US3: T065, T066 параллельны; T067, T069, T072, T073, T074 параллельны
- US4: T076, T077 параллельны; T078, T080, T082, T084, T085, T087 параллельны
- Polish: T095–T099, T101 параллельны
- После Phase 2 разные User Story могут вестись разными разработчиками

---

## Parallel Example: User Story 1

```bash
# Тесты истории — вместе:
Task: "Компонентный тест сводки рабочего пространства в apps/web/src/features/new-review/components/WorkspaceSummary.test.tsx"
Task: "Тест проверки файла до загрузки в apps/web/src/features/new-review/lib/validate-upload.test.ts"
Task: "Тест доступности запуска по состоянию извлечения в apps/web/src/features/new-review/lib/run-readiness.test.ts"
Task: "Тест отображения состояний запуска в apps/web/src/features/review-run/components/RunStatePanel.test.tsx"
Task: "Тест признака долгого запуска в apps/web/src/features/review-run/lib/stall-detector.test.ts"

# Независимые правила и запросы — вместе:
Task: "Запрос стартовых данных в apps/web/src/features/new-review/api/use-bootstrap.ts"
Task: "Проверка размера и формата файла в apps/web/src/features/new-review/lib/validate-upload.ts"
Task: "Правило допуска к запуску в apps/web/src/features/new-review/lib/run-readiness.ts"
Task: "Вычисление длительности и застревания в apps/web/src/features/review-run/lib/stall-detector.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1: Setup
2. Phase 2: Foundational — блокирует все истории
3. Phase 3: User Story 1
4. **Остановиться и проверить**: весь путь до терминального состояния запуска на сценариях `happy-path`, `run-failed`, `run-stalled`, `document-extraction-failed`
5. Демонстрировать при готовности

### Incremental Delivery

1. Setup + Foundational → основа готова
2. US1 → проверка независимо → демонстрация (MVP)
3. US2 → проверка независимо → демонстрация
4. US3 → проверка независимо → демонстрация
5. US4 → проверка независимо → демонстрация
6. US5 → проверка независимо → демонстрация
7. Polish → сквозные проверки неизменяемости, доступности и отсутствия экранов входа

### Parallel Team Strategy

После Phase 2 истории распределяются между разработчиками. Единственные точки согласования — T107 (перенос резолюции использует форму решения из US3) и T092 (контекст расширяет создание запуска из US1); их владельцы договариваются об очерёдности.

---

## Notes

- `[P]` означает разные файлы и отсутствие зависимости от незавершённых задач
- Каталог `apps/web/src/api/generated/` создаётся только генератором и никогда не правится руками; задачи генерации отделены от задач в `apps/web/src/features/`
- Несоответствие контракта потребности интерфейса исправляется контрактным PR в `codex/002-target-review-platform`, а не локальной правкой типа (принцип I)
- Фикстуры, тесты и демонстрации используют только синтетические данные; материалы `client-materials/` не переносятся (принцип VI)
- Коммит после каждой задачи или логической группы; на каждом checkpoint историю можно проверить отдельно
