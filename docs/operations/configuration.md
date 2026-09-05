# Настройка исполнения LLM

Инженерный слой поддерживает три явно разделённых режима: production-запуск без модели,
локальный synthetic fixture и opt-in подключение OpenAI-compatible endpoint. Конкретная модель,
провайдер и коммерческий режим не выбраны. Production-конфигурация поэтому использует
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

Реальный `model-smoke` запускается оператором отдельно после выбора endpoint. В evidence нужно
зафиксировать profile digest, model/version, skill digest, engine/backend commit, suite version,
результат и время. Реальные credentials и клиентские документы в репозиторий не сохраняются.
Текущий статус реального endpoint: **не выбран и не проверялся**.

Явная команда после выбора endpoint (она выполняет по одному review и dialogue запросу):

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
