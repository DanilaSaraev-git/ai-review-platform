# Контрактная граница инженерного слоя

Нормативные источники: [ModelAdapter v1](../../../contracts/review-platform/v1/model-adapter.md), [публичный HTTP v1](../../../contracts/review-platform/v1/openapi.yaml), [skill contracts](../../../contracts/review-platform/v1/README.md). Этот документ уточняет реализацию первого ML-среза; не создаёт второй порт модели и не меняет HTTP v1.

## Владение

| Сторона | Отвечает за |
| --- | --- |
| Harness / пакет навыка | Предметные инструкции review/finding_dialogue, методику и тексты вопросов; согласование версии смыслового результата |
| Engine | Полный подготовленный вход, budget, retries, JSON/semantic checks, преобразование результата и provenance |
| ModelAdapter | Одну транспортную попытку по профилю; provider envelope, finish reason, usage, безопасные типизированные ошибки |
| Application / storage | Idempotency, попытки, snapshots, решения человека и атомарную публикацию |

Для приёмки 004 достаточно synthetic skill package с существующими операциями review-input/output.v1 и finding-dialogue-input/output.v1. UI дерева, общая память ответов между замечаниями и новые публичные graph DTO сюда не входят. Если harness потребует иной контракт, он версионируется отдельно; 004 не создаёт заранее свободное JSON-поле состояния дерева.

## Python-порт

`ModelAdapter.capabilities()` и `generate(GenerationRequest) → GenerationResult` реализуются по полям нормативного документа без Any-заглушек. Существующие prompt builders переиспользуют общий тип из `review_core.ports.models`, а не собственный несовместимый GenerationRequest.

GenerationRequest содержит trusted_instructions только из engine/verified package; untrusted_input содержит profile, fragments, context, history и текущую реплику. Response schema — схема конкретного вызова, не обязательно полный skill output. Один generate означает один сетевой POST: SDK/transport retries отключены.

GenerationResult сохраняет text, request ID, фактический provider/model/version, finish_reason, usage, latency, provider_request_id и применённые безопасные параметры. Отсутствующие usage поля — null, версия — unknown. Reasoning/chain-of-thought не используется как финальный text. JSON смыслового ответа проверяет engine, не adapter.

## Компактный model output и публичная проекция

Для первого review-вызова модель возвращает смысловые поля существующего review-output.v1: summary, findings, coverage и limitations. У finding остаются kind/title/problem/reason/question/priority, anchors и scope; модель не возвращает run/report/finding ID, timestamps, provenance, human state или offsets. Anchor в этом внутреннем результате — source_id + fragment_id + exact quote. Схему оформляет задача реализации в отдельном внутреннем `model-output.review.v1.schema.json`.

Dialogue возвращает смысловой assistant_message из finding-dialogue-output.v1 с action/content/proposed_resolution и такими же компактными anchors; service IDs, offsets и provenance добавляет engine. Внутренняя схема — `model-output.dialogue.v1.schema.json`. Служебные поля во входящем ответе отвергаются через additionalProperties=false.

После проверки engine назначает идентификаторы, вычисляет позиции по сохранённому Unicode-тексту и преобразует результат в canonical skill output, затем в HTTP report/assistant DTO. Однозначность quote обязательна внутри указанного fragment; неоднозначная короткая цитата требует нового явного прогона с более точным результатом, а не автоматического выбора позиции.

Контекстный anchor разрешается по доступным supporting sources, не по primary reviewed set. Для primary anchor/scope сохраняется принадлежность reviewed set, а каждому finding требуется основание в основном документе. Исправление overly-strict проверки context anchors в 003 не должно ослаблять первичное основание или точность цитаты.

Coverage сохраняет точные поля v1: reviewed_fragment_ids, unreviewed и source_gaps. reviewed_fragment_ids и fragment_id из unreviewed разбивают весь target set исходного документа ровно один раз; source_gaps отдельно объясняет недоступность/ограничения источников. Ошибочный ответ не превращается в completed с пустыми findings. Валидный нулевой список находок разрешён; он не считается доказательством отсутствия ошибок в ТЗ.

## Профиль подключения

Профили — серверная операторская конфигурация, не параметры произвольного web-запроса. ModelProfileRef остаётся id/version.

Клиентские короткие названия из продуктовой базы не являются model ID или готовыми профилями. Checkpoint, квантование, фактический context window, JSON/reasoning и serving API остаются неизвестными до проверки точного подключения. Ни один кандидат и внешний провайдер здесь не выбран.

| Группа | Правило |
| --- | --- |
| Identity | id/version, adapter_kind, provider label, model ID, config_sha256 |
| Endpoint | Полный chat-completions URL как задан, без дописывания /v1; отдельный optional probe URL |
| Credentials | Secret reference через существующий SecretProvider; секрет вне profile payload, report и журнала |
| Capabilities | Явные text_generation, native_structured_output и supported parameters; /models 200 не доказывает structured output |
| Response mode | text / json_object / json_schema; по умолчанию text. Unsupported mode отклоняется до генерации, schema validation обязательна в любом режиме |
| Parameters | Temperature/reasoning и provider options задаются только профилем, допустимые имена проверяются; отсутствующие параметры не отправляются. Модель/URL/auth нельзя переопределить extras |
| Output limit | Явный положительный max_output_tokens и поддерживаемое endpoint имя параметра: max_tokens либо max_completion_tokens |
| Input budget | Явные context_window_tokens и max_input_utf8_bytes, откалиброванный с учётом prompt overhead и output reserve; дополнительно локальный token counter, если доступен для точной версии tokenizer |
| Transport | TLS verify включён, redirects запрещены, connect timeout 5s либо остаток срока, остальные timeouts не больше остатка; max_connections=None |

Без известного tokenizer preflight по байтовому пределу не объявляется точным подсчётом токенов. Профиль обязан задать консервативный input limit; его фактическую достаточность проверяет endpoint suite. Provider context_limit сохраняется как явный отказ без усечения. Токенизаторы/веса автоматически не скачиваются.

Полный prompt serializes instructions, fragments, context, history, schema hints и служебные разделители; budget проверяется именно по нему. Превышение model output bytes budget прекращает чтение и даёт invalid_provider_response; в engine это невалидный результат без отчёта. Потоковое чтение transport bytes не вводит streaming HTTP API продукта.

Package registry проверяет manifest schema, полный inventory, пути, hash каждого файла, engine requirement и capabilities. Новая версия package digest включает canonical manifest semantics и file digests; legacy digest algorithm остаётся распознаваемым для старых snapshots. Тот же id/version с другим содержимым отклоняется; обновление требует новой версии.

## Availability и compatibility

Не меняя public available/unavailable, использовать отдельные mutable observations с checked_at/expires_at и причиной. Unknown/missing/expired/degraded проецируются в unavailable. Configuration validation не выдаётся за проверку доступности внешней модели.

- Если operator задал probe: режим `models` проверяет наличие выбранного model ID в ответе, режим `health` проверяет заданный endpoint health. Probe не вызывает генерацию, timeout=5s, TTL успешного наблюдения=300s. Обновление stale observation выполняется по запросу списка профилей или попытке новой операции; фонового монитора нет.
- Если probe не поддерживается: operator задаёт отдельное наблюдение доступности с checked_at/expires_at. Оно не входит в immutable model config и не возникает автоматически из факта заполненных настроек. После истечения нужна новая явная проверка/декларация оператора.
- Успешная генерация обновляет доступность. Ошибки auth/model-not-found/unavailable записываются как недоступность; transient rate limit даёт degraded до Retry-After либо 1s. После срока модель снова проверяется установленным для профиля способом.
- Endpoint compatibility хранится отдельно как результат точного набора profile digest + skill digest + engine/backend version + suite version/date. До реального прогона статус unverified. Он не превращается в verified по имени Qwen/Kimi или успешному healthcheck.

Это технические defaults плана. Ни один реальный probe, credential или model invocation в ходе подготовки документов не выполнялся.

## Ошибки и стабильный HTTP v1

| Внутренняя причина | Review AsyncError | DialogueError | Автоповтор |
| --- | --- | --- | --- |
| authentication_failed / model_not_found / unsupported_option | model_unavailable | model_unavailable | Нет |
| rate_limited; 502/503/504; connect failure до отправки | model_unavailable | model_unavailable | Один, если остаётся время |
| timeout / неизвестный исход после отправки | model_unavailable | model_unavailable | Нет; ручной retry допустим |
| context_limit | context_limit | context_limit | Нет |
| content_blocked | model_output_invalid | content_blocked | Нет |
| invalid_provider_response / invalid JSON / finish_reason=length | model_output_invalid | model_output_invalid | Нет |
| Семантически неверные anchors/coverage | validation_failed | validation_failed | Нет |
| process_interrupted | internal_error | internal_error | Нет; ручной retry допустим |

Расширенный внутренний code сохраняется в attempt; публичный enum не расширяется. Безопасное сообщение объясняет причину без raw provider body. Configuration/auth errors не обещают успешный retry без исправления настроек. Временный отказ может оставаться manual-retryable после исчерпания auto attempts.

Публичные endpoints, status codes, Location, DTO и ETag сохраняются. Create/retry возвращает существующий 202 с актуальным ресурсом, даже если синхронная работа уже закончилась. Replay во время исполнения может вернуть нетерминальное состояние. Новый retry-review endpoint и новые обязательные поля не вводятся. Idempotency keys 8–128 символов, включая 128, сохраняются без служебных префиксов.

## Поставка

Default Compose остаётся deterministic и internal network. `compose.external-model.yaml` — явно подключаемый override для outbound сети API, profile config и secret reference; только loopback proxy опубликован на host. Это разрешение egress, не обещание сетевой фильтрации по доменам: endpoint выбирается серверной конфигурацией, redirects запрещены.

Nginx proxy read/send timeout по умолчанию 330s: максимальный operation deadline 300s + 10s финализации + запас. При увеличении operation deadline конфигурация proxy должна проверять тот же порядок. Проверка provider availability не делает весь API неготовым: исторические отчёты должны читаться и при отказе модели.
