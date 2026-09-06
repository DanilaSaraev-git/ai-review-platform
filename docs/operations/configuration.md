# Настройка исполнения LLM

Инженерный слой поддерживает три явно разделённых режима: production-запуск без модели,
локальный synthetic fixture и opt-in подключение OpenAI-compatible endpoint. Для первого
реального подключения 2026-09-06 выбран Kimi K2 через Hugging Face/Novita. По последующему
поручению того же дня добавлен [DeepSeek V4 Flash через Yandex AI Studio](#deepseek-через-yandex-ai-studio).
До явного model-enable production-конфигурация использует
`REVIEW_COMPOSITION=unconfigured`: инфраструктурная readiness остаётся доступной, каталог
моделей показывает `unavailable` с причиной `not_configured`, а создание review завершается
канонической ошибкой `model_unavailable` до записи запуска. Fixture не подменяет этот ответ.

## Режимы запуска

Production overlay запускается без fixture-файлов и без model credential:

```sh
docker compose \
  -f deploy/compose/compose.yaml \
  -f deploy/compose/compose.production.yaml \
  up -d
```

В нём задаются отдельные неизменяемые идентификаторы
`REVIEW_MODEL_PROFILE_ID=model-not-configured` и
`REVIEW_DIALOGUE_POLICY_ID=bounded-dialogue-v1`. Изменение payload уже созданной записи под
тем же ID считается configuration drift и намеренно блокирует readiness.

Default Compose остаётся изолированным synthetic-контуром для локальных тестов:

```sh
docker compose -f deploy/compose/compose.yaml up -d
```

`REVIEW_COMPOSITION=fixture` использует только in-memory состояние. Durable synthetic Compose
использует `REVIEW_COMPOSITION=durable`, PostgreSQL и доверенную пару synthetic document/output.
Оба режима проверяют механику системы, но не выполняют смысловой анализ произвольного текста.
Неизвестное значение `REVIEW_COMPOSITION` останавливает запуск вместо fallback на fixture.

Внешний model transport включается только вторым файлом:

```sh
export REVIEW_MODEL_PROFILE_FILE=./deploy/compose/config/model-profile.external.example.json
export REVIEW_MODEL_CREDENTIAL_FILE=/absolute/path/to/untracked/model-api-key
docker compose \
  -f deploy/compose/compose.yaml \
  -f deploy/compose/compose.external-model.yaml \
  up -d
```

Перед запуском скопируйте пример профиля в отдельный операторский файл и задайте точный
`chat_url`, model ID, лимиты и capabilities фактического endpoint. Значение ключа находится
только в файле Docker secret. Его нельзя помещать в JSON-профиль, `.env`, командную строку,
HTTP DTO или журналы.

Внешний override разрешает egress контейнеру API и запрещает redirects на transport-уровне.
Это не доменный firewall: допустимый endpoint задаётся серверной конфигурацией. Nginx ждёт
ответ до 330 секунд, что покрывает review deadline 300 секунд, ограниченную финализацию до
10 секунд и транспортный запас.

## Профиль модели

Профиль неизменяем и идентифицируется парой `id/version` и SHA-256 конфигурации. Он задаёт:

- полный `chat_url` без автоматического добавления `/v1`;
- provider label и точный model ID;
- `secret_ref`, но не секрет;
- response mode и явно поддерживаемые параметры;
- `context_window_tokens`, консервативный `max_input_utf8_bytes` и `max_output_tokens`;
- необязательный негenerативный health/models probe.

## DeepSeek через Yandex AI Studio

Поручение 2026-09-06: подключить DeepSeek и запустить сервер без тестовых генераций.
Шаблон [профиля](../../deploy/compose/config/model-profile.yandex-deepseek.json) задаёт
`yandex-deepseek-v4-flash` 1.0.0, `provider=yandex` и точный Chat Completions endpoint
`https://ai.api.cloud.yandex.net/v1/chat/completions`. Model URI
`gpt://<folder_id>/deepseek-v4-flash/latest` берётся из фактического каталога `GET /v1/models`.
`latest` — изменяемая версия поставщика; профиль не заявляет закреплённый checkpoint весов.

Для сохранения ID каталога и API-ключа вне Git выполните
`bash tools/ops/save-yandex-credentials.sh`. Ключ вводится скрыто, файлы сохраняются в
`${XDG_CONFIG_HOME:-$HOME/.config}/ai-analytics-review` с правами 600. Затем создайте
операторский профиль (подставьте абсолютные пути к своим приватным файлам):

```sh
python3 tools/ops/render-yandex-profile.py \
  /absolute/private/path/yandex.folder-id \
  /absolute/private/path/yandex.profile.json
```

Renderer не читает API-ключ и не выполняет сетевые запросы. Профиль не содержит ключа;
`YANDEX_API_KEY` — ссылка на mounted-file secret. Adapter и models probe используют
`Authorization: Api-Key ...` и `OpenAI-Project` с ID каталога из model URI.

Используется существующий `plain_json`: схема включается в доверенные инструкции, а результат
проверяется каноническим валидатором до публикации. Поддержка строгой схемы конкретной моделью
не заявляется. Параметр `max_completion_tokens=16384` ограничивает ответ вместе с reasoning;
`reasoning_effort` и temperature не переопределяются. Это выбранный лимит запуска, а не
заявленный максимальный размер ответа модели. Контекст модели — 1048576 токенов, существующий
лимит всего сериализованного запроса 32768 UTF-8 байт сохраняется.

Активация идёт через штатные `model-disable.sh`, `model-configure.sh`, `model-enable.sh`.
`model-enable.sh` делает только GET списка моделей и инфраструктурные проверки. Генерации,
`model-smoke`, загрузку пробных документов и запросы диалога при этом подключении не выполнять.
Проверка списка моделей подтверждает авторизацию и наличие exact model URI; качество ревью и
совместимость фактического ответа остаются непроверенными.

Официальные источники: [модели](https://aistudio.yandex.ru/ru/docs/ai-studio/concepts/generation/models),
[Chat Completions](https://aistudio.yandex.ru/ru/docs/ai-studio/api/Chat-Completions/createChatCompletion),
[авторизация](https://aistudio.yandex.ru/ru/docs/ai-studio/api-ref/authentication),
[GET models](https://aistudio.yandex.ru/en/docs/ai-studio/api/Models/listModels).

## Ограничения запроса и доступность

Язык нового отчёта задаёт `locale` исходного review; web передаёт `ru-RU` по умолчанию.
Runtime добавляет проверенную locale в доверенные инструкции модели для всех создаваемых
пояснений и сохраняет её в приватном состоянии исполнения для последующего диалога,
включая диалог после перезапуска сервера. JSON keys, enum values, идентификаторы и дословные
цитаты сохраняются без перевода. У запусков, созданных до этой правки, locale не сохранялась:
для их новых ответов диалога используется `ru-RU`. Опубликованные отчёты и история не
переводятся и не меняются. Передача языка проверена на fake provider; фактический язык
новых ответов DeepSeek без отдельно разрешённой генерации не проверялся.

Полный prompt, включая инструкции проверенного skill package, schema и untrusted input,
проверяется по байтовому лимиту до вызова. Превышение возвращает `context_limit`; текст не
усекается. В текущем срезе один допустимый документ обрабатывается одним смысловым вызовом.
Чанкинг, overlap, synthesis и repair находятся в
[бэклоге 004](../../specs/004-llm-review-integration/backlog.md).

Configuration validity, availability observation и compatibility evidence — разные состояния.
Readiness проверяет БД, миграцию, seed и artifact store; генерацию и платный probe она не
запускает. Успешный health probe сам по себе не доказывает поддержку schema, budget или
предметного навыка.

После явного включения внешнего профиля оператор обновляет его availability отдельной
негенеративной командой:

```sh
review-cli model-probe
```

Команда работает только с `REVIEW_COMPOSITION=ml`, проверяет точную пару model profile
`id/version`, обращается только к объявленному в профиле `probe.url` методом GET и сохраняет
наблюдение в deployment database. Секрет читается из mounted file. Команда возвращает `0`
только для свежего состояния `available`; отсутствующий probe, ошибка конфигурации, сети,
авторизации или ответа возвращает `2` и безопасный JSON без credential и DSN. Probe не вызывает
генерацию и не входит в `/health/ready`.

Availability ограничена `probe.success_ttl_seconds`. После успешного enable операторский таймер
должен запускать ту же команду чаще TTL; production deployment использует интервал 60 секунд.
До явного enable таймер отключён. Просроченное или неуспешное наблюдение снова делает профиль
недоступным для новых review и требует исправить endpoint/credential, затем повторить probe.

## Runtime limits

`REVIEW_RUNTIME_CONFIG_PATH` задаёт server-side границы admission. При старте конфигурация
проверяется по canonical schema; неизвестные поля и значения вне диапазонов отклоняются. API
применяет `max_upload_bytes` во время потокового чтения, а не после загрузки тела в память, и
проверяет `max_context_documents`, `max_dialogue_message_codepoints` и
`max_dialogue_turns`. Review и dialogue используют общий семафор
`max_parallel_model_calls`, поэтому параллельные запросы не обходят операторский лимит.

Имена скачиваемых документов передаются через RFC 5987 `filename*`; исходное имя не
вставляется в HTTP header как неэкранированный текст.

## Исполнение и восстановление

API рассчитан на один процесс. Принятые coroutine принадлежат application lifespan, а не
соединению клиента. Review имеет общий deadline 300 секунд, dialogue — 60 секунд. Разрешён не
более чем один автоматический повтор: только для 429/502/503/504 или подтверждённой ошибки
соединения до отправки, в пределах того же deadline. Неопределённый timeout, невалидный JSON,
ошибка schema/anchors и content/context/auth failures автоматически не повторяются.

Короткие транзакции admission, claim, prepare и terminal publication выполняются отдельно от
сетевого ожидания. Последний terminal CAS допускается только до сохранённого DB deadline.
После рестарта незавершённые операции помечаются `process_interrupted`; модель на startup не
вызывается. Опубликованный report не пересчитывается, а dialogue и Human Decision хранятся
отдельно.

## Direct CLI и проверка endpoint

Direct CLI использует тот же adapter/engine, но отдельное локальное in-memory состояние. Он не
подключается к deployment database, не берёт process ownership lock и может работать рядом с
API. Обязательные тесты используют только fake provider.

Реальный `model-smoke` запускается оператором отдельно после выбора endpoint. Для подключения
Яндекса 2026-09-06 пользователь запретил пробные генерации: `model-smoke` не запускать.
В evidence нужно
зафиксировать profile digest, model/version, skill digest, engine/backend commit, suite version,
результат и время. Реальные credentials и клиентские документы в репозиторий не сохраняются.
Статус фактической серверной проверки хранится в [evidence выпуска](../../specs/006-mvp-launch/evidence.md).

Явная команда для отдельно разрешённой проверки endpoint (она выполняет по одному review и dialogue запросу):

```sh
uv run --frozen review-cli model-smoke \
  --profile /absolute/path/to/model-profile.json \
  --credential /absolute/path/to/model-api-key \
  --fixture tests/fixtures/ml-integration/primary.md \
  --skill skills/review-data-spec \
  --output /absolute/path/to/compatibility-evidence.json
```

Команда не запускается ни readiness, ни обязательным release gate. Evidence содержит только
идентичности, digests, безопасную фактическую provenance, usage/latency и статус; prompt,
ответ модели и значение credential в него не входят.

## Профиль Kimi K2

Готовый [профиль](../../deploy/compose/config/model-profile.huggingface-kimi-k2.json)
выбирает `moonshotai/Kimi-K2-Instruct:novita` через
`https://router.huggingface.co/v1/chat/completions`. Значение токена хранится только в private
credential file; `HF_TOKEN` в JSON — ссылка на секрет. Установка и включение выполняются
штатными [model-configure/model-enable](deployment.md#подключить-модель).

Профиль 1.0.1 задаёт temperature=0.6, максимум 8192 выходных токенов и 32768 UTF-8
байт на полный запрос с инструкциями и схемой. Байтовый бюджет — консервативная настройка
этого профиля, а не максимальное окно модели. Превышение отклоняется без скрытой обрезки.
Точный checkpoint сервера неизвестен. Профиль использует plain JSON с серверной проверкой
схемы, цитат и coverage; native structured output не заявлен для выбранного endpoint.

Версия 1.0.0 ограничивала ответ 4096 токенами. Серверный запуск достиг этого лимита и
завершился с `finish_reason=length`; обрезанный ответ не стал отчётом. Бюджет увеличен новой
версией профиля, чтобы сохранить неизменность истории. Это верхняя граница ответа,
а не гарантия завершения любого документа; автоматического продолжения или repair нет.

Health probe обращается к каталогу HF и подтверждает доступность router. Доступ к самой
модели и совместимость выходов подтверждает только отдельный реальный smoke. Production
таймер доступности и ограничения числа model calls сохраняются.
Основания конфигурации: [HF Novita API](https://huggingface.co/docs/inference-providers/providers/novita),
[карточка Kimi K2](https://huggingface.co/moonshotai/Kimi-K2-Instruct),
[каталог Router](https://router.huggingface.co/v1/models), проверены 2026-09-06.
