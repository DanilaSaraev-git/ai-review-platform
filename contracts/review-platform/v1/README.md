# Review Platform contracts v1

Статус: проверяемый additive baseline `v1.2.0` для параллельной реализации web, backend и навыков. Контракты описывают выбранные интерфейсы, но не подтверждают продуктовую ценность.

## Web ↔ Backend

[openapi.yaml](openapi.yaml) — design-first источник истины для HTTP v1. [Swagger UI](swagger/README.md) даёт визуальную интерактивную документацию поверх этого же файла без копирования схемы. Web работает только с ресурсами HTTP и не читает файлы PoC или `review-output.v1` напрямую. [deployment-boundary.md](deployment-boundary.md) фиксирует границу доверенного deployment: один настроенный actor, одна organization и один workspace.

Patch v1.0.2 не меняет URL или payload shape: он добавляет недостающие negative responses, уточняет immutable profile/extraction semantics и strong ETag, а Swagger assets теперь поставляются локально для offline deployment. Частично извлечённый primary использует существующий `source_partial` с `reason=primary_source_partial`; это не новый public enum.

System profile является deployment-scoped release data, а не workspace-owned mutable version. Create-run сначала фиксирует requested source identity/order/role, затем preparation append-once сохраняет terminal extraction outcome. Только свежая внутренняя доступность модели `available` отображается как public `available`; degraded/unknown/missing/expired становятся `unavailable`. Timestamp опубликованного отчёта канонизируется как `YYYY-MM-DDTHH:mm:ss.ffffffZ`.

Основной frontend-flow:

1. `GET /v1/bootstrap` — получить настроенного actor, workspace и публичные лимиты.
2. `POST /v1/workspaces/{workspaceId}/documents` — загрузить основной документ или контекст.
3. `GET /profiles` и `GET /model-profiles` — выбрать точные версии настроек проверки.
4. `POST /review-runs` с `Idempotency-Key` — создать фоновый запуск.
5. `GET /review-runs/{runId}` — polling до терминального состояния.
6. `GET /review-runs/{runId}/report` — получить валидный неизменяемый отчёт.
7. `GET /review-runs/{runId}/finding-states` — наложить изменяемые решения и состояние диалога.
8. `GET /findings/{findingId}/dialogue` и `POST /dialogue/turns` — провести один асинхронный ход; следующий ход доступен только при `can_send_message=true`.
9. `PUT /findings/{findingId}/decision` — сохранить решение человека с optimistic concurrency.

Отчёт не содержит `HumanDecision` и не меняет тело/ETag после диалога. Ответ навыка может вернуть `Proposed Resolution`, но его принятие всегда является отдельным human action.

Примеры для mock и smoke-тестов находятся в [examples/http](examples/http/).

## Версии документа и цикл проверки

`Document` и `ReviewRun.document_id` по-прежнему идентифицируют неизменяемую версию исходника. `DocumentFamily` объединяет версии в постоянную карточку. Старый `uploadDocument` создаёт карточку с v1; прежние загрузки мигрируют в отдельные карточки без объединения по имени. `getDocumentVersionFamily` разрешает старый ID в семейство, номер версии и прежний `Document` DTO.

| Действие | Operation ID |
| --- | --- |
| Список и карточка документа | `listDocumentFamilies`, `getDocumentFamily` |
| История версий и проверок | `listDocumentFamilyVersions`, `listDocumentFamilyRuns` |
| Следующая версия | `uploadDocumentVersion` |
| Сравнение выбранного запуска | `getReviewCycle`, `compareReviewCycle` |
| Исправление связи | `putReviewCycleLink` |
| Подтверждение исправления или пересмотр | `putIssueResolution` |
| PDF выбранного запуска | `downloadReviewPdf` |

Загрузка следующей версии требует `Idempotency-Key`. Совпадение семейства, имени, типа и байтов возвращает прежнюю версию без повторного расходования квоты; несовпадение с тем же ключом — `409`. Новый ключ с теми же байтами создаёт версию с `unchanged_from_previous=true`. Проверка начинается отдельным `createReviewRun` с сохранённым ID версии; `ReviewRun.locale` необязателен для совместимости старых записей, для которых web использует `ru-RU`.

`ReviewCycle.baseline_run_id` фиксируется при приёме запуска и указывает на последнюю уже опубликованную проверку семейства. Изменения параллельных запусков не меняют эту базу. `issue_id` сохраняется между появлениями проблемы; отсутствующие проблемы остаются в цикле, чтобы распознавать возвращение через несколько версий. `previous_run_id` и `previous_finding_id` указывают на последнее фактическое появление, которое может предшествовать базе сравнения.

Состояние сравнения (`new`, `persisting`, `not_detected`, `uncertain`, `not_checked`, `reappeared`), прежняя оценка обоснованности и подтверждение исправления (`open`, `resolved`) независимы. Неполный охват или изменённые условия не подтверждают исчезновение проблемы, а `not_detected` никогда не означает `resolved`. Модель и алгоритм сопоставления не подтверждают исправление.

Перенесённая оценка сохраняет исходные автора, дату и revision; `previous_decision` фиксируется при первом успешном сравнении. Более поздняя правка старого решения не меняет этот снимок. Повтор сравнения не перезаписывает текущую человеческую оценку, ручные связи или подтверждения исправления. Ручная связь один-к-одному не переносит решение автоматически; занятое соответствие и stale cycle revision возвращают `409`. У подтверждения исправления собственная ревизия; подтверждение и пересмотр требуют пояснения.

`report.pdf` формируется из одного согласованного снимка отчёта, решений и цикла; содержит все замечания выбранного запуска, время выгрузки, исходную версию и ограничения. Фильтры интерфейса и несохранённые черновики не входят в снимок. Экспорт не вызывает модель и не меняет байты или ETag `getReviewReport`; ответ PDF использует `Cache-Control: no-store`.

## Engine ↔ Review Skill

- [review-input.schema.json](schemas/review-input.schema.json) — неизменяемый снимок источников, фрагментов и профиля, передаваемый навыку.
- [review-output.schema.json](schemas/review-output.schema.json) — только смысловой результат навыка. Модель не устанавливает решение человека и не публикует HTTP-отчёт.
- [finding-dialogue-input.schema.json](schemas/finding-dialogue-input.schema.json) и [finding-dialogue-output.schema.json](schemas/finding-dialogue-output.schema.json) — один пользовательский ход по неизменяемому замечанию и только ответ навыка.
- [skill-manifest.schema.json](schemas/skill-manifest.schema.json) — декларативный пакет навыка с операциями `review` и `finding_dialogue`, без исполняемого сетевого кода.
- [model-adapter.md](model-adapter.md) — внутренний порт сменяемых LLM.

Проверка JSON Schema не заменяет семантическую валидацию. Движок дополнительно проверяет существование source/fragment ID, вхождение цитаты и offsets, точное разбиение `review_scope.target_fragment_ids`, правила `missing`, принадлежность истории конкретному finding и отсутствие инструкций из входных материалов в управляющем контексте.

`review_scope.target_fragment_ids` содержит объект проверки. По умолчанию это все фрагменты основного документа; fragments контекста являются supporting material. Большие документы движок делит на внутренние work units, но work units не входят ни в HTTP, ни в итоговый skill output.

Недоступный основной документ завершает run ошибкой. Optional context со статусом `partial|unavailable` и исчерпанный work item отражаются source/fragment gaps и дают partial report; никакой источник не исчезает из provenance молча.

Примеры находятся в [examples/skill](examples/skill/). Они синтетические и не содержат клиентские материалы.

## Версионирование

- HTTP использует путь `/v1`. Добавление необязательного поля или нового endpoint допустимо в v1 и отмечается minor/patch baseline tag; удаление, новое обязательное поле и изменение смысла требуют `/v2`.
- Skill-контракты имеют строковые версии `review-input.v1`, `review-output.v1`, `finding-dialogue-input.v1` и `finding-dialogue-output.v1`. Они меняются независимо от HTTP.
- Manifest имеет версию `review-skill.v1`; версия самого навыка задаётся SemVer.
- Сохранённые артефакты PoC с `schema_version: 1` не меняются. Их читает отдельный адаптер.

Любое изменение baseline обновляет схемы, OpenAPI, примеры и [CHANGELOG.md](CHANGELOG.md) в одном коммите.

## Integration gate

- OpenAPI lint и локальные `$ref` проходят; backend export не содержит несовместимого diff.
- Orval заново генерирует client/query hooks/MSW без ручной правки generated DTO.
- Все пять skill examples проходят Draft 2020-12 schemas и semantic invariants.
- HTTP examples проходят соответствующие component schemas.
- Общий synthetic tracer bullet выполняется через MSW, real HTTP и local skill/CLI.
- Configured-workspace namespace mismatch, stale revision, duplicate idempotency и immutable-report cases являются обязательными негативными тестами.

GitHub-порядок, владельцы каталогов и merge sequence описаны в [parallel-development.md](../../../docs/architecture/parallel-development.md).

## Замечания без привязки

В v1.2.0 `Finding.anchors` может быть пустым и для замечаний о присутствующем тексте.
Неверная цитата удаляет привязку, но сохраняет замечание, его вопрос и приоритет.
Интерфейс не показывает неподтверждённую цитату и не добавляет метку об отсутствии связи.
Пример: [отчёт без привязки](examples/http/report.unlinked.json). Непроверенная область `scope` также может быть пустой. Отсутствие привязки не является решением человека.
