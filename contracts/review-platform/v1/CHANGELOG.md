# Changelog

## 2026-09-07 — v1.2.0: замечание без привязки

- Неверная цитата больше не требует удаления замечания: `Finding.anchors` допускает пустой массив для present-text kinds. Непроверенные элементы `scope` тоже удаляются; остальные поля сохраняются.
- Добавлен синтетический пример `report.unlinked.json`, обновлены static OpenAPI, guest-v1 и генерация клиента.
- Привязки, которые остались, проходят прежнюю проверку по источнику; выдуманные цитаты не публикуются. UI не добавляет предупреждений о пустом anchors.

## 2026-09-06 — unified review cycle

- Добавлен POST review-cycle/complete с expected_revision. Завершение требует полного анализа и разрешённых вопросов; actor/time и digest состояния сохраняются отдельно от отчёта в optional completion. Изменение решений делает завершение неактуальным.
- CreateDialogueTurn и DialogueTurn поддерживают optional attachment_document_ids (до 10 уникальных документов своего workspace). Исходники входят в контекст диалога, сохраняются при retry и не меняют опубликованный отчёт.
- Старые запросы и snapshots без новых полей остаются допустимыми. Guest-v1 и static OpenAPI обновлены из канонического контракта.

## 2026-09-06 — v1.1.0 document review cycle

- Добавлены ресурсы `document-families`: карточка документа, список версий и запусков, разрешение прежнего `document_id` в семейство. `document_id` по-прежнему обозначает неизменяемую версию; прошлые загрузки не объединяются по имени.
- Добавлена идемпотентная загрузка следующей версии в семейство; повтор запроса не расходует квоту второй раз, намеренная загрузка тех же байтов допустима.
- Добавлен отдельный `review-cycle` с фиксированной базой сравнения, историей проблем, ручными связями один-к-одному и собственным подтверждением исправления. Прежние `HumanDecision` и `ReviewReport` не изменены.
- Прежние решения фиксируются при первом успешном сравнении; повтор сравнения сохраняет человеческие решения, связи и подтверждения исправлений. Отсутствие замечания не подтверждает исправление.
- Добавлен `report.pdf`: согласованный снимок всех замечаний выбранной проверки и сохранённых статусов, независимо от фильтров интерфейса, без вызова модели.
- `ReviewRun.locale` добавлен как необязательное поле для предзаполнения повтора; старые записи без языка сохраняют совместимость.
- Существующие обязательные поля, ID, endpoints, перечисления статусов, skill JSON и байты опубликованных отчётов не изменены. Guest-v1 наследует новые операции и действующие квоты/границы доступа.

## 2026-09-05 — v1.0.2 additive backend preflight

- Добавлены документированные `400` для invalid cursors, `404` для namespace mismatch upload и `409` для profile head/content conflicts.
- Уточнены immutable profile family/version, asynchronous extraction projection и quoted strong SHA-256 ETag exact bytes.
- Зафиксирована семантика partial primary через существующий `source_partial` и `reason=primary_source_partial` без расширения enum.
- Swagger UI переведён на локальные version-pinned assets, чтобы документация работала offline.
- Обязательные поля, URL и существующие enum не менялись.

## 2026-09-04 — v1.0.1 handoff baseline

- Согласованы Spec Kit-артефакты, архитектура и задачи с no-auth deployment boundary.
- В Git baseline добавлена зарезервированная папка `apps/web/` для ветки коллеги.
- HTTP и skill payload semantics относительно опубликованного `v1.0.0` не изменились.

## 2026-09-04 — v1 baseline

- Зафиксирован асинхронный HTTP-flow загрузки, запуска, polling, отчёта и решения человека.
- Отчёт сделан неизменяемым; `finding-states`, диалог и решение человека вынесены в отдельные ресурсы.
- Добавлен последовательный асинхронный диалог по finding: create, poll и retry failed generation; лимит задаёт versioned policy, а не web.
- Зафиксированы `review-input.v1`, `review-output.v1`, `finding-dialogue-input.v1`, `finding-dialogue-output.v1` и `review-skill.v1`.
- Добавлены `review_scope.target_fragment_ids`, structured source diagnostics и source-level coverage gaps для больших документов и недоступного контекста.
- Снимок запуска фиксирует точные версии/digests профиля, skill package, model profile, dialogue policy и engine.
- Решение человека отделено от вывода навыка; конкурентные обновления диалога и решения защищены `expected_revision`.
- Выбор поставщика LLM скрыт за версионированным профилем модели и внутренним портом backend; web больше не выбирает skill ID.
- Добавлены точные display locators и quote offsets, deployment boundary для одного настроенного actor/workspace и synthetic mock examples.
- HTTP bootstrap не моделирует identity/access-control runtime: `organization_id` сохранён только как namespace и будущий seam.
- Добавлен статический Swagger UI для просмотра канонического OpenAPI без генерации отдельной схемы.
