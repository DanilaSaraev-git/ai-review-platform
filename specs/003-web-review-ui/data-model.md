# Phase 1. Data model: веб-интерфейс AI Review v1

**Дата**: 2026-09-04. **План**: [plan.md](plan.md). **Исследование**: [research.md](research.md).

Web не владеет доменной моделью. Все сущности ниже приходят по HTTP из [контракта v1](../../contracts/review-platform/v1/openapi.yaml); их типы генерирует Orval, поэтому этот документ описывает не объявление типов, а то, как web их читает, где проходит граница неизменяемого и изменяемого и какие правила проверяются на клиенте.

Ручных копий DTO нет: имена полей ниже приведены как ориентир по контракту, а в коде используются только сгенерированные типы.

## Границы владения

| Слой | Что содержит | Источник | Кто меняет |
| --- | --- | --- | --- |
| Неизменяемые данные запуска | документ, снимок версий, отчёт, замечания, привязки, охват | HTTP, только чтение | никто после публикации |
| Изменяемые состояния | решение человека, диалог и его ходы | HTTP, чтение и мутации | аналитик через отдельные операции |
| Состояние интерфейса | выбранное замечание, черновики ввода, признак «идёт дольше обычного», выбранный сценарий MSW | клиент | компоненты, не сохраняется на сервере |

Разделение первых двух слоёв — реализация принципа V: отчёт и `finding-states` лежат в разных ключах кэша, и ни одна мутация не инвалидирует ключ отчёта (см. [research.md](research.md), R-06).

## Сущности только для чтения

### Bootstrap

Поля: `actor` (id, display_name), `workspace` (id, organization_id, organization_name, name), `limits` (`document_upload_max_bytes`, `max_context_documents`).

Правила на клиенте:

- `workspace.id` — единственный источник `workspaceId` во всех URL. Пользователь его не вводит и не выбирает (FR-002).
- `limits` применяются к формам до отправки: размер файла проверяется до загрузки, число контекстных документов — до подключения очередного (FR-006, FR-008, US5-2).
- `actor` показывается только как атрибуция и никогда как признак входа в систему (FR-001, принцип IV).

Загружается один раз при старте приложения; кэшируется на время сессии вкладки.

### Document

Поля: `id`, `workspace_id`, `filename`, `media_type` (`application/pdf` | `text/markdown` | `text/plain`), `size_bytes`, `sha256`, `extraction_state` (`pending` | `completed` | `partial` | `failed`), `created_by`, `created_at`.

Правила на клиенте:

- Роль документа — основной или контекстный — принадлежит форме запуска, а не документу: один и тот же `id` попадает либо в `document_id`, либо в `context_document_ids`.
- `extraction_state` управляет доступностью запуска (FR-040): `failed` — запуск запрещён с указанием причины; `pending` — запуск недоступен, документ ещё готовится; `partial` — запуск доступен с предупреждением о непрочитанной части; `completed` — запуск доступен.
- Документ неизменяем: интерфейс не редактирует его и не создаёт новую версию (FR-007).
- Байты запрашиваются отдельно (`.../content`) и используются только просмотрщиком.

### ReviewProfile и ModelProfile

`ReviewProfile`: `id`, `scope` (`system` | `workspace`), `version`, `digest`, `name`, `role`, `goal`, `checks`, `supersedes`, `created_at`.
`ModelProfile`: `id`, `version`, `name`, `description`, `capabilities`, `availability` (`available` | `unavailable`).

Правила на клиенте:

- В запуск отправляется пара `{id, version}`, а не только идентификатор: версия участвует в воспроизводимости результата (FR-009, FR-017).
- `availability: unavailable` делает профиль модели невыбираемым с указанием причины (FR-010).
- Создание профилей в интерфейсе v1 не реализуется (раздел Out of Scope спецификации), хотя контракт такую операцию содержит.

### ReviewRun

Поля: `id`, `workspace_id`, `state`, `progress` (`percent`, `message`), `document_id`, `context_document_ids`, `execution_snapshot`, `created_by`, `created_at`, `started_at`, `finished_at`, `cancel_requested_at`, `report_available`, `error`.

Состояния и их трактовка интерфейсом:

| `state` | Терминальное | Что показывает интерфейс |
| --- | --- | --- |
| `queued` | нет | поставлен в очередь, опрос активен |
| `preparing` | нет | подготовка источников, опрос активен |
| `reviewing` | нет | идёт проверка, опрос активен |
| `validating` | нет | проверка результата, опрос активен |
| `completed` | да | успешно завершён, отчёт доступен |
| `failed` | да | причина из `error`, признак `retryable`, отчёта нет |
| `cancelled` | да | отменён, отчёта нет |

Правила на клиенте:

- Опрос включён только в нетерминальных состояниях и выключается при переходе в терминальное (FR-014, SC-012).
- Признак «идёт дольше обычного» вычисляется клиентом: 15 минут без смены `state` и `progress`. Это состояние интерфейса, а не поле контракта; оно не подменяет `state` и не останавливает опрос (FR-039, SC-013).
- `report_available` и `state: completed` вместе открывают доступ к отчёту; при любом другом состоянии переход к отчёту не предлагается (FR-015, FR-018).
- `error.code` отображается человекочитаемым текстом по значению кода, а не по серверной строке: `invalid_document`, `unsupported_document`, `extraction_failed`, `context_limit`, `model_unavailable`, `model_output_invalid`, `validation_failed`, `cancelled`, `internal_error`.
- `execution_snapshot` показывается как зафиксированные версии профиля, модели, навыка, политики диалога и движка (FR-017).

Создание: `POST .../review-runs` с телом `CreateReviewRun` (`document_id`, `context_document_ids`, `profile`, `model_profile`, `locale`) и обязательным заголовком `Idempotency-Key`, привязанным к намерению пользователя (FR-012, R-05).

### ReviewReport

Поля: `id`, `run_id`, `created_at`, `summary`, `coverage`, `findings`, `limitations`, `provenance`.

Правила на клиенте:

- Ресурс считается неизменяемым на всё время жизни запуска: бесконечный `staleTime`, отсутствие инвалидации при любых мутациях (FR-018, FR-037, принцип V).
- `findings` ограничены контрактом 500 элементами; список рендерится целиком в порядке `ordinal` (R-13).
- `limitations` показываются рядом с результатом, а не прячутся за раскрытием: это часть честности результата (FR-019).
- Пустой `findings` — содержательный результат, отображается вместе с охватом и ограничениями (FR-023).
- Из `provenance.model` показываются только `provider`, `model`, `model_version`, безопасные параметры и расход токенов; никаких значений секретов (FR-004).

### Coverage и CoverageGap

`Coverage`: `status` (`complete` | `partial`), `target_fragment_ids`, `reviewed_fragment_ids`, `gaps`.
`CoverageGap`: `source_id`, `fragment_id` (может быть `null`), `code`, `reason`.

Правила на клиенте:

- `status: partial` показывается как заметный признак неполного результата, а не как мелкая пометка (FR-022, US5-4).
- Каждый `gap` отображается с причиной и привязкой к источнику; коды: `source_unavailable`, `source_partial`, `context_budget`, `context_limit`, `processing_failed`, `unsupported_content`, `other`.
- Перечень источников из `provenance.sources` показывается целиком с ролью (`document` | `context`) и статусом (`available` | `partial` | `unavailable`): ни один источник не исчезает из представления (FR-022).

### Finding и EvidenceAnchor

`Finding`: `id`, `ordinal`, `kind` (`ambiguity` | `contradiction` | `missing` | `inconsistency` | `other`), `title`, `problem`, `reason`, `question`, `priority` (`level`, `rationale`), `anchors`, `scope`.
`EvidenceAnchor`: `source_id`, `document_id`, `source_name`, `fragment_id`, `quote`, `quote_start`, `quote_end`, `location`.
`location` — `PdfLocation` (`kind: pdf`, `page`, `rects` в нормализованных координатах, необязательные `table`, `row`) либо `TextLocation` (`kind: text`, `line_start`, `line_end`, `char_start`, `char_end`).

Правила на клиенте:

- Замечание с `kind: missing` может не иметь привязок и содержать только `scope` — это штатный случай, а не ошибка данных. Интерфейс показывает проверенную область и явно сообщает об отсутствии цитаты (FR-021, SC-003).
- Выбор просмотрщика — по `location.kind`, а не по расширению файла (R-09).
- Если фрагмент не удалось сопоставить, показывается сообщение о несопоставленном фрагменте; произвольное место документа не подсвечивается (краевой случай спецификации).
- Все поля замечания — только чтение; интерфейс не предлагает их править (FR-018).

## Изменяемые сущности

### HumanDecision

Поля: `status` (`unreviewed` | `confirmed` | `rejected` | `needs_context`), `revision`, `actor`, `reason`, `resolution`, `decided_at`.

Правила проверки на клиенте до отправки:

| Правило | Основание |
| --- | --- |
| При `status ≠ unreviewed` поле `reason` обязательно и непусто (до 4000 символов) | FR-025, схема `PutFindingDecision` |
| При `status = unreviewed` поля `reason` и `resolution` отправляются как `null` | FR-026, схема контракта |
| `resolution` необязательна, до 8000 символов | FR-025 |
| `expected_revision` берётся из последнего прочитанного состояния и отправляется всегда | FR-027, принцип V |

Мутация: `PUT .../findings/{findingId}/decision`. Ответ `409` с `code: revision_conflict` переводит форму в состояние конфликта: актуальное значение перезагружается и показывается, введённый текст сохраняется, повтор доступен одним действием уже с новой ревизией (FR-027, SC-005, R-07).

Инвалидация после успеха: только `finding-states` этого запуска и `dialogue` этого замечания — сохранение решения может закрыть диалог с `blocked_reason: human_decision_recorded`. Ключ отчёта не трогается.

### FindingDialogue и DialogueTurn

`FindingDialogue`: `id`, `run_id`, `finding_id`, `revision`, `state` (`open` | `generating` | `closed`), `turn_count`, `can_send_message`, `blocked_reason`, `policy`, `turns`.
`DialogueTurn`: `id`, `ordinal`, `state` (`queued` | `generating` | `completed` | `failed`), `actor`, `member_message`, `created_at`, `assistant_response`, `error`, `finished_at`.
`AssistantResponse`: `action` (`clarify` | `propose_resolution` | `escalate`), `content`, `proposed_resolution` (`text`, `rationale`), `anchors`, `provenance`.

Правила на клиенте:

- Доступность отправки берётся только из `can_send_message`; клиент её не вычисляет (FR-031, R-08).
- `blocked_reason` всегда сопровождает недоступную отправку человекочитаемым текстом: `generation_in_progress`, `turn_limit_reached`, `human_decision_recorded`, `dialogue_not_supported`, `model_unavailable` (FR-032).
- Опрос диалога включён, пока `state: generating` либо есть ход в состоянии `queued` или `generating`; завершение хода видно не позднее 2 секунд (FR-033, SC-012).
- Ход в состоянии `failed` показывает `error.code` и, при `retryable: true`, предлагает повтор через `POST .../turns/{turnId}/retry` без повторного ввода вопроса (FR-035).
- `expected_revision` отправляется и при создании хода, и при повторе; `409` обрабатывается как конфликт с сохранением введённого текста (FR-036).
- `proposed_resolution` не является решением. Действие «использовать предложение» подставляет `text` в поле `resolution` формы решения; сохранение остаётся вторым, отдельным действием аналитика (FR-029, SC-007, принцип V).

## Состояние интерфейса

Не приходит с сервера и на сервер не отправляется:

| Состояние | Где живёт | Зачем |
| --- | --- | --- |
| Выбранное замечание | параметр маршрута | возврат по ссылке и восстановление после обновления страницы |
| Черновик обоснования, резолюции и текста вопроса | состояние формы | сохранение ввода при конфликте ревизии (SC-005) |
| Признак «идёт дольше обычного» | вычисляется из истории состояний запуска | FR-039 |
| Страница и позиция просмотрщика документа | состояние компонента | переход к фрагменту замечания |
| Выбранный сценарий MSW | переменная окружения запуска | воспроизводимые негативные случаи в разработке и E2E |

## Связи

```text
Bootstrap ──> Workspace ──> Document* ──┐
                                        ├──> ReviewRun ──> ReviewReport ──> Finding* ──> EvidenceAnchor*
                          ReviewProfile ─┤                     │
                          ModelProfile ──┘                     │ (по finding_id, отдельный ресурс)
                                                               ├──> HumanDecision
                                                               └──> FindingDialogue ──> DialogueTurn*
```

Сплошная линия от отчёта к замечаниям — неизменяемая часть. Ветка `HumanDecision` и `FindingDialogue` связана с замечанием по `finding_id`, приходит отдельными запросами и меняется независимо, не затрагивая отчёт.
