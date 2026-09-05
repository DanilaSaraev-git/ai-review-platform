# Research: инженерный слой LLM-интеграции

**Feature**: 004-llm-review-integration. **Дата**: 2026-09-05. **Статус**: реализация начата с Setup; проектные решения и исходный снимок сохранены ниже. Реальный endpoint не выбран и не проверен.

Документ определяет техническую интеграцию ревью и диалога с backend 003. Содержание harness, дерево проблем, состояние его узлов и семантика переходов обсуждаются отдельно в задаче `01a0712e-97b5-7f42-9d33-88594e861788`. Граф здесь не считается согласованным и не проектируется. Модель, провайдер, коммерческие условия и бесплатные квоты не выбраны; исследование рынка не проводилось.

## Принятый окончательный backend — T001

Дополнение S-33: актуальный клиентский список моделей и предположительные соответствия официальным карточкам сохранены в отдельном репозитории `ai-review-product`. Это вход для будущего выбора/профиля, не результат compatibility test. Модель/провайдер не выбраны; общие инженерные решения ниже не зависят от семейства кандидата.

По поручению S-32 2026-09-05 ветка `codex/004-llm-review-integration` fast-forward обновлена до **e0dd57e6bdc2967c49bbcb10ad88d1af315b528f**. Backend-worktree 41ea был чистым и не менялся. Alembic head проверен командой `uv run --frozen alembic -c packages/review-runtime/alembic.ini heads`: **20260905_0001**. Новых миграций в Setup нет.

Сверка всех 17 fingerprints исторической таблицы: 15 кодовых/контрактных файлов совпали. Изменились только `Makefile` (SHA-256 `0c4d08054122ddd92dc88e8376f2d1bc7695230c77064d772ae4228ec2b2d555`) и `tasks.md` backend 003 (`9bb521f3e0d9ba743b057499af2f225bc6ffaf64769ac4fdeb785e27d1e3f0cc`). T019 завершён; новый T033 добавил самостоятельный isolated PostgreSQL в full gate. Финальная задача 003 передала результат **122 passed / 1 optional skip**; собственные результаты 004 фиксируются в [quickstart.md](quickstart.md).

Уже выполнены в 003: полная schema validation отчёта и проверка Idempotency-Key 8–128. Они переиспользуются, не создаются повторно. Всё ещё относится к 004: async facade, короткие dialogue transactions, same-turn retry, atomic claim/idempotency, точный model/skill seed/snapshot и supporting context anchors. Архитектурных причин менять план не найдено.

Gate использует собственные проекты `review-platform-004-97ec` (HTTP 18084) и `review-platform-004-97ec-release` (PG 55444). Их имена/порты проверены до запуска; существующие `review-platform-mvp_*` volumes не используются. E2E-тест 003 имел hardcoded Compose project: в 004 добавлена переменная `REVIEW_MVP_PROJECT` с прежним default. Это изоляция тестового запуска, не изменение HTTP/runtime. Фактический default release-порта в Makefile — 55440; упоминание 55439 в старом quickstart003 устарело.

Итог собственного Setup gate: **144 passed / 1 optional skip**, lint/mypy/contracts/TypeScript consumer проходят; [точные команды, разбивка suites и restart evidence](quickstart.md). T001–T002 завершены. Дополнение S-33 потребовало явных exact allow-paths для трёх клиентских файлов: Makefile передаёт `PROTECTED_PATH_ARGS` в оба вызова guard; пустой default сохраняет прежний запрет изменений. Код модели/исполнения и production persistence в Setup не менялись.

## 1. Исторический baseline и границы свидетельств

Снимок снят **2026-09-05 11:10:44 UTC / 14:10:44 Europe/Moscow**. Источник backend: задача «Реализация backend feature 003», ID `01a06f33-1bf1-7e50-b732-ffa83e663f02`, отдельный локальный checkout.

- HEAD backend: `a4aed47f370a97962a168c5bc7bb4ad6a9e4ff51`.
- Worktree **dirty**: есть изменённые tracked-файлы и untracked-файлы, включая `packages/review-runtime/src/review_runtime/reports.py` и `specs/003-backend-implementation/deferred-production-hardening.md`. Анализ опирается на рабочие байты, а не только на HEAD.
- В активном `specs/003-backend-implementation/tasks.md:80` T019 — final review и commit — ещё не отмечен выполненным. T018 и convergence T020–T032 отмечены выполненными; это состояние документа задачи, а не повторный прогон тестов автором research.
- Собственный planning checkout имел HEAD `d88ae1379f1a7f763001026deee48a37cf365988` перед созданием материалов. Отсутствие backend-кода 003 в том checkout не означает отсутствия реализации.
- В передаче задачи сообщалось о `121 passed / 1 optional skipped`. Это ранее переданный результат; в рамках research тесты не запускались, привязка этого результата к окончательному commit ещё требует проверки. Новый ML-путь и реальные endpoints этими числами не проверены.

Все кодовые пути ниже, кроме явно существующих Markdown-ссылок в этом checkout, относятся к **baseline worktree 41ea**. Для них намеренно не создаются относительные ссылки на отсутствующие здесь файлы. Строки соответствуют снятому рабочему состоянию; SHA-256 позволяет обнаружить дальнейшее изменение. Это отпечатки ключевых швов, не полный воспроизводимый архив dirty worktree.

| Файл в baseline 41ea | Проверенный участок | SHA-256 рабочих байтов |
| --- | --- | --- |
| `contracts/review-platform/v1/model-adapter.md` | 8–59: нормативный порт, результаты и ошибки | `0d172f8dfa49d3e111d2ccc374990d6c70f2c2c5b58a536d4be235d4234ee176` |
| `apps/api/src/review_api/dependencies.py` | 13–24: composition подключает fixture executor | `e868b7fb100ddaaf03162195d7d9dd786bb1200fc4dafee93af4cd592a8d4d6c` |
| `apps/api/src/review_api/routes/reviews.py` | 21–35: async route вызывает sync platform | `6ac1123f31af9207598a257125fedbf74d05265064cd14699f3fdafdc4167b2c` |
| `apps/api/src/review_api/routes/findings.py` | 18–58: create/retry dialogue | `83249d6c416d4c2a1ac36ca3a3b658a4d4d4636bc67f001cb4c0dc2661833189` |
| `apps/cli/src/review_cli/commands/review.py` | 19–43: direct fixture composition, без HTTP | `04dab4272ee31f629505756fe8ced4a02eafebd54344b11c88c6d8f53a9bfc15` |
| `packages/review-core/src/review_core/application/platform.py` | 29–39: sync ReviewExecutor; 313–335: прямое исполнение | `d63afa27340b7ccf449f525dcc80515e6a745d7d71b51a5bd6e7b33fd33edd9b` |
| `packages/review-runtime/src/review_runtime/postgres/platform.py` | 58–149, 528–544: deterministic profile/snapshot; 638–681: review; 1002–1055: dialogue/retry | `8f06c11302faf0c9da3f925346ed82a53d016ea842374b67e99e26eec561caf5` |
| `packages/review-runtime/src/review_runtime/models/openai_compatible.py` | 49–128: capability probe, payload, retries, JSON и ошибки | `699a576021a00fb708db5223e4581ca2429ff5fce7dec2ad9f63217d722088ca` |
| `packages/review-runtime/src/review_runtime/config/settings.py` | 11–29, 57–93: retries/timeouts/budgets/model options | `1f9bd04a16c3cf9851be686c1ff8c0cf735d190bbe8a37ec23f27b0614af653f` |
| `packages/review-runtime/src/review_runtime/config/model_profiles.py` | 7–14: только свежий available observation проецируется в available | `39835952ace491fe531800d1f82d69d52ebf67ec1eeee59ced61717b7b5e2eb2` |
| `packages/review-runtime/src/review_runtime/skills/registry.py` | 15–38: manifest/file checks и package digest | `e3d18d503bcbd94ae0cd26f4d34b9211a13e9c948c087b9f4bf81a15b6fb7972` |
| `skills/review-data-spec/manifest.json` | 7–27: операции, requires и inventory | `4156137cfea1052c436e46c7b66ea1776fc2eed7e6bedcff5d6f39a744993a89` |
| `deploy/compose/compose.yaml` | 66–89, 124–127: API только в internal network | `b8f2bcfd5f3b2b70b871338efdab8ecd50e1ba9d72d4ddfdbdd588f11930dcb8` |
| `deploy/compose/nginx.conf` | 3–7: proxy без явно заданного read timeout | `7ccf80ab79774eac202708510863adbbcb62c5c9095c24c5b509998c6617755a` |
| `specs/003-backend-implementation/tasks.md` | 78–99: активный gate и незавершённый final commit | `3354248a8d7fd948d262098295407b65ad41830e8d48724ba9b67ac708af2929` |
| `specs/003-backend-implementation/deferred-production-hardening.md` | 3–6: прежний production scope отложен | `e1eff71d122a02a9f19df654e0dfc7f0d95cb1978089c086b3e41132159bac4a` |
| `Makefile` | 10–37: contributor gates; 39–48: Compose smoke/restart | `18a9a1d5b2b9b5b9e4b895e9bd376af8c703ba3500512a0ad4c645cad3d7c3fa` |

## 2. Решения и основания

### R-01. Один review step на полный вход

**Decision.** Принято пользователем: весь выбранный документ и необходимый контекст проходят один смысловой review step, если полный сформированный запрос помещается в бюджет профиля с резервом на ответ. Oversized input отклоняется до генерации с понятной причиной, без скрытой обрезки. Чанкинг, межчастные связи и synthesis остаются бэклогом. Один разрешённый повтор временного отказа является новой попыткой того же шага, а не дополнительным этапом анализа.

**Rationale.** Это проверяет техническую интеграцию при выбранном ограничении первого среза. Упоминание work units/synthesis в [Model Adapter v1](../../contracts/review-platform/v1/model-adapter.md) описывает целевой внутренний порт и не требует реализовать их в 004. Перед вызовом учитываются также trusted instructions, references, контекст и схема ответа; проверка размера только исходного файла недостаточна.

**Alternatives.** Chunking сейчас увеличивает scope вопреки принятому решению; скрытая обрезка теряет покрытие; отдельный LLM-вызов дедупликации или repair добавляет не согласованный смысловой шаг. Детерминированная нормализация результата на сервере допустима.

### R-02. Реализовать нормативный ModelAdapter, не второй конкурирующий контракт

**Decision.** Материализовать типы и async-порт из [model-adapter.md, Interface и Нормализованные ошибки](../../contracts/review-platform/v1/model-adapter.md). Адаптер выполняет одну сетевую попытку и возвращает `GenerationResult`: text, фактическую model provenance, finish reason, usage, request IDs, latency и safe parameters. Engine владеет допустимым повтором, разбором JSON, evidence/coverage validation и подготовкой публикации. HTTP v1 не зависит от провайдера.

**Rationale.** В baseline Python `ModelGateway.generate(Any) -> Any` и двухпольный `review/prompt.py:7` не реализуют полный порт. Gateway сейчас сам делает retry и `json.loads`, принимает произвольные `messages`, не возвращает usage/finish reason. Существующий sync `ReviewExecutor` возвращает уже отчёт; его роль отличается от роли ModelAdapter и не должна исчезать при подключении сети.

**Alternatives.** Сохранение JSON validation/retries в gateway создаёт два владельца ошибок и умножает число попыток; прямой вызов provider SDK из platform привязывает бизнес-операции к endpoint. Старый sync fixture executor сохраняется через совместимый локальный wrapper.

### R-03. Async coordinator; model concurrency не ограничивается приложением

**Decision.** Принятое архитектурное направление: async application/coordinator исполняет `await ModelAdapter.generate` на текущем ASGI loop. `to_thread` применяется к ограниченным по времени sync-фазам psycopg, артефактов, извлечения и CPU-проверок. Каждый DB connection и его транзакция целиком открываются и закрываются внутри одной sync-фазы. Сеть не удерживает DB transaction или общий threadpool thread. CLI вызывает тот же async workflow через единственный `anyio.run` на границе команды, без HTTP.

`httpx.AsyncClient` создаётся и закрывается в lifespan одного ASGI loop либо внутри единственного CLI loop и переиспользуется в этом сроке жизни. **Нет application semaphore, model-call queue или лимита числа активных генераций.** Настраивается `httpx.Limits(max_connections=None)`; ограничение числа idle keep-alive connections не является лимитом активных вызовов. Объявленный в старом RuntimePolicy `max_parallel_model_calls=2` не применяется к ML composition и не должен молча возобновиться при загрузке конфигурации.

**Rationale.** Baseline async routes напрямую вызывают sync platform; вынесение всего запроса с многоминутной сетью в общий threadpool сохраняло бы ограничение через занятые потоки. HTTPX рекомендует async client для async framework и scoped reuse клиента; создание/закрытие клиента — async resource lifecycle. Это инженерное основание выбора, не измерение производительности приложения: [HTTPX Async Support, Making Async requests / Opening and closing clients](https://www.python-httpx.org/async/). Значение `max_connections=None` означает отсутствие ограничения pool на число активных соединений: [HTTPX Resource Limits](https://www.python-httpx.org/advanced/resource-limits/).

**Alternatives.** `anyio.run` внутри threadpool на каждую генерацию требует управления несколькими loops и держит потоки во время сети. Полная миграция psycopg/storage на async не нужна для этого среза. Ограничитель model concurrency и очередь противоречат выбору пользователя; обычный threadpool для sync-фаз не используется для admission генераций.

### R-04. Явные профили подключения и честная provenance

**Decision.** Operator configuration разрешает точный versioned model profile: adapter/provider identity, model ID, точный endpoint и request path, secret reference, заявленные capabilities, входной/выходной бюджет, поддерживаемые параметры и режим structured output. Sampling/reasoning-параметры передаются только при явной поддержке профилем. Нативная JSON Schema — необязательная возможность; plain text с JSON проверяется тем же серверным validator. Endpoint не дополняется безусловным `/v1`.

Неизменяемый snapshot сохраняет ID/version/config digest; фактические значения модели, применённых safe parameters и usage поступают из GenerationResult. Неизвестные usage остаются null, версия — `unknown`. Секрет и его значение не входят в snapshot, отчёт или диагностическую ошибку. Изменение безопасной семантики профиля создаёт новую версию; существующие `model_profile_versions`/`skill_versions` с JSON payload и digest используются как storage seam.

**Rationale.** `openai_compatible.py:49–63` считает любой 200 от `/v1/models` поддержкой native structured output; `:71–86` жёстко задаёт JSON object, temperature и путь. `postgres/platform.py:58–149,528–544` независимо от endpoint сохраняет deterministic name/capabilities/digest и available observation с длительным сроком. Замена одного executor оставила бы ложную provenance.

**Alternatives.** Compatibility по названию семейства модели, обязательный `/models` и вывод capabilities из доступности сети недостаточны. Доступность, заявленные свойства и результат полного compatibility suite относятся к разным наблюдениям. Детальная политика первоначального наблюдения availability и точные значения endpoint заполняются профилем подключения; отсутствие выбранного endpoint не блокирует fake-provider интеграцию.

### R-05. Проверенный декларативный skill package

**Decision.** Подключить существующий SkillRegistry к composition: загрузка точной разрешённой версии, проверка manifest schema, declared inventory, файловых SHA и границы paths, затем `requires.engine`, model capabilities и соответствия run snapshot. Инструкции и references составляют доверенную часть запроса; документ, контекст, реплики и промежуточные результаты остаются данными. Содержание инструкций и tree/harness semantics находятся за границей этого research.

**Rationale.** `skills/registry.py:15–31` уже проверяет inventory, path escape и file SHA; `:34–38` считает package digest по путям и байтам файлов, но не по семантике manifest. Registry не включён в `build_platform`, требования `requires` при загрузке не проверяются. Поэтому требуется отдельно фиксировать manifest identity/semantics при разрешении версии и проверять их вместе с package digest. Сохранённые digest старых опубликованных snapshots не пересчитываются на месте.

**Alternatives.** Подгрузка произвольного SKILL.md из пользовательского документа или сетевых executable hooks не соответствует декларативному контракту. Добавление формата графа в manifest сейчас преждевременно: граф не согласован.

### R-06. Общий deadline и один строго ограниченный retry

**Decision.** Принято пользователем: review deadline **300 секунд**, dialogue deadline **60 секунд**. Это настройки первого среза, не измеренные SLO. Coordinator считает единый оставшийся бюджет операции; retry и ожидание `Retry-After` не начинают новый полный deadline. Разрешён не более чем один автоматический повтор после явных 429/502/503/504 либо доказанного сбоя соединения до отправки запроса. Adapter и transport не имеют собственных скрытых retries.

Неоднозначный timeout после возможной отправки, invalid JSON и невалидный смысловой результат не повторяются автоматически. Если `Retry-After` не помещается в остаток deadline, повтор не выполняется. Новая попытка сохраняет тот же logical work item/turn, получает новый attempt/request ID. Безопасная ошибка позволяет человеку решить, запускать ли ручной повтор.

**Rationale.** Общий deadline управляет операцией, а не только HTTP read timeout. Нельзя считать, что после сетевого timeout провайдер не обработал запрос. Документация AnyIO описывает cancel scopes, effective deadline, shielding cleanup и необходимость повторно выбрасывать cancellation: [AnyIO Cancellation and timeouts, Timeouts / Shielding / Finalization](https://anyio.readthedocs.io/en/stable/cancellation.html). Пользователь задал максимум одного повтора временного отказа; конкретные HTTP-коды и delay — инженерная детализация в plan.md, не доказательство идемпотентности вызовов провайдера.

Граница deadline — проверенный terminal CAS внутри sync publish-фазы непосредственно перед commit. Просрочка до CAS откатывает success-транзакцию; commit вовремя допущенного перехода либо запись ошибки имеют ограниченную finalization до 10s. Deadline/owner проверяются внутри sync-фазы, а не только вокруг to_thread; неизвестный commit outcome сверяется с durable state. Подробнее — раздел «Ошибки, сроки и перезапуск» в [plan.md](plan.md).

**Alternatives.** Повтор любого network error или invalid JSON увеличивает число потенциально обработанных запросов без разрешения пользователя. Retry на каждом слое умножает попытки. Полный shield вокруг генерации отключает нужный deadline; защищать следует только ограниченное завершение/фиксацию состояния.

### R-07. Перезапуск завершает прерванные операции ошибкой; публикация защищена состоянием

**Decision.** Принято пользователем: при старте единственного API process оставшиеся незавершённые ML runs/attempts прежнего процесса переводятся в `failed` с безопасной причиной interruption; повтор запускает человек. Внешний API после restart автоматически не вызывается. Это startup reconciliation локального single-process сценария, без worker, queue, lease recovery и продолжения production jobs.

Review и dialogue разделяются на prepare/claim, generation и publish/fail. Публикация повторно проверяет актуальные operation/attempt/state, отмену и revision; опоздавший ответ не заменяет terminal state или опубликованный report. Dialogue retry добавляет попытку к тому же turn и member message. При публикации dialogue перечитывается текущая Human Decision: ответ модели не открывает закрытый человеком диалог и не меняет его решение.

**Rationale.** `postgres/platform.py:1002–1036` генерирует ответ внутри транзакции и затем безусловно открывает диалог; `:1049–1055` повторяет через создание нового turn. После появления долгого await эти недостатки становятся наблюдаемыми. AnyIO отдельно отмечает, что поток нельзя принудительно остановить; поэтому sync-транзакции должны корректно завершаться, а terminal-state cleanup иметь ограниченную защищённую фазу. Cancellation сохраняется как cancellation, а не проглатывается после cleanup: [AnyIO Cancellation and timeouts](https://anyio.readthedocs.io/en/stable/cancellation.html).

**Alternatives.** Автоматическое продолжение после restart и production recovery относятся к отложенному scope 003. Удержание блокировки на всё время сети мешает конкурентному чтению/решениям. Создание новой пользовательской реплики при retry нарушает смысл существующего turn.

### R-08. Совместимость HTTP/CLI и явное включение egress

**Decision.** Сохраняются HTTP v1 DTO, status codes, Location и раздельное чтение immutable report и mutable finding states. API ожидает async coordinator в рамках текущего синхронного по пользовательскому сценарию запроса. Fixture/offline mode сохраняет существующие проверяемые результаты через wrapper sync executor. Direct CLI сохраняет команды, флаги и report/evidence outputs; общий coordinator создаётся runtime composition без зависимости CLI от FastAPI.

Direct CLI сохраняет отдельное локальное in-memory хранение и экспорт artifacts: он не подключается к БД deployment, не забирает API ownership lock и не выполняет её reconciliation. Общими остаются engine/coordinator/model port; CLI и API могут работать одновременно, не меняя операции друг друга.

Default Compose остаётся offline. Внешнее API включается отдельной operator configuration/Compose override для API; профиль задаёт разрешённый endpoint и секрет только на сервере. Proxy timeout согласуется с review deadline и ограниченным завершением ответа. После переноса в контур заказчика меняется профиль подключения, а не бизнес-логика.

**Rationale.** В `deploy/compose/compose.yaml:88–89` API подключён только к internal network; `:109–122` worker находится в deferred profile. `deploy/compose/nginx.conf:6–7` не задаёт timeout многоминутного upstream. CLI сейчас умеет только deterministic profile; новое подключение расширяет composition, не создавая второй процесс ревью.

**Alternatives.** Изменение публичного API, немедленная очередь/worker или обязательный внешний endpoint для fixture gates не требуются. Published report bytes/ETag, legacy PoC artifacts и клиентские данные не мигрируются через переписывание результатов.

## 3. Проверка технического слоя: что ещё предстоит выполнить

Обязательный gate не требует ключа модели. Fake provider предоставляет управляемый transport либо локальный synthetic HTTP endpoint; источники тестов не содержат клиентских материалов. Эти сценарии — план проверки, а не результаты выполненных тестов:

1. Порт/payload: точный URL без двойного `/v1`, отсутствие неподдерживаемых параметров, plain/JSON-object/native-schema режимы, output limit, trusted/untrusted разделение; неизвестные capabilities не объявляются подтверждёнными.
2. Results/errors: finish reason включая length/content filter, nullable usage, actual model/version/request IDs, безопасные параметры; redaction сырого error body и secret; невозможность публикации усечённого или невалидного ответа.
3. Retry/deadline: максимум две сетевые попытки только в разрешённых случаях; одна при ambiguous timeout/invalid JSON; общий остаток 300/60, bounded Retry-After, новые attempt IDs при прежнем logical work item/turn, без transport retry.
4. Async execution без model cap: несколько fake генераций одновременно ожидают сеть; нет application semaphore и pool cap; health, polling и независимые DB-операции обслуживаются, пока provider заблокирован тестовым событием. Sync-фазы не держат connection через await.
5. Storage: duplicate idempotency не запускает вторую генерацию; dialogue retry не создаёт member message; конкурентное решение человека/отмена/поздний результат не перезаписываются; invalid output не создаёт report.
6. Restart: прерывание prepare/generation/до publication, startup переводит только оставшиеся активные операции в failed без сетевого replay; ручной retry сохраняет нужную идентичность; опубликованный report после restart побайтно прежний.
7. Config/skills: версия/digest drift, file/manifest mismatch, неподдерживаемые requires; точные snapshots и реальная provenance; изменение credential value не переписывает старый report; default fixture gate делает zero egress.
8. Channels/deploy: прежние fixture HTTP/direct CLI результаты, canonical report validation, report bytes/SHA/ETag до и после диалога; внешний synthetic endpoint доступен только при явно включённой конфигурации; proxy выдерживает согласованное ожидание.

Отдельный будущий реальный smoke фиксирует точные model/provider/profile/skill/engine/backend versions, endpoint options, input size, latency, finish reason, usage и исход проверки контрактов/evidence. Его успех относится к этой конфигурации и не подтверждает семейство моделей, качество продукта или экономию. Материалы и результаты на клиентских документах сохраняются только в `ai-review-product`; отправка таких документов внешнему endpoint не выполняется при подготовке плана.

## 4. Как подхватить окончательный результат feature 003

1. Перед реализацией 004 получить актуальный компактный snapshot задачи 003 и проверить final commit/merge SHA, чистоту её worktree и active T019. Не считать ранее переданное число tests доказательством финального SHA.
2. В собственном рабочем checkout принять окончательный интегрированный результат 003 обычным Git workflow. Не копировать dirty-файлы из 41ea и не менять worktree backend-задачи. Зафиксировать base/merge SHA 004; текущая таблица остаётся историческим снимком.
3. Сопоставить SHA-256 и перечитать изменившиеся швы: composition, sync/async вызовы, review/dialogue transitions и retry, profiles/snapshot/availability, skill registry, настройки, contracts и Compose. Для каждого отличия записать, устранил ли final003 найденный gap либо изменил нужную интеграцию. Не применять повторно уже выполненный в 003 фикс.
4. Проверить актуальный `Makefile` и quickstart финального 003. В прочитанном baseline полный contributor gate — `make release-check`; `make release-check-local` пропускает migration/integration/Compose E2E. Предпосылка полного gate — поднятый isolated Compose flow с smoke/restart evidence (`make mvp-up`, `make mvp-smoke`, `make mvp-restart`). Повторять их только в собственной изолированной тестовой среде, без удаления существующих пользовательских volumes.
5. До ML-изменений записать результаты финального baseline gate и неизменяемые synthetic reports. После реализации повторить применимые contract/unit/integration/security/migration/Compose gates и новые fake-provider сценарии; сохранить exact commands, commit, результаты и причины skips. Новая real-endpoint проверка остаётся отдельной opt-in проверкой.
6. Проверить diff относительно принятого final003: HTTP v1 и опубликованные reports совместимы; нет случайного возврата queue/worker/recovery scope, application model limiter, выбранного провайдера или graph semantics. При несовместимом контрактном отличии сначала обновить SpecKit-артефакты, не маскировать его как незаметную реализационную деталь.

## 5. Первичные технические справки и нерешённые внешние параметры

Документация HTTPX и AnyIO прочитана 2026-09-05; ссылки выше служат инженерным основанием async/resource/cancellation решений. Это текущие страницы upstream, не утверждение о протестированной версии зависимостей checkout. При реализации direct dependency AnyIO и HTTPX должны соответствовать принятому lockfile и проходить тесты в нём.

Неизвестны точный endpoint, model ID/version/размер/квантизация, доступный контекст, особенности reasoning/sampling/structured output, credentials и фактические latency/usage. Они заполняются операторским профилем и проверяются отдельным endpoint smoke. Эти неизвестные не требуют выбирать провайдера в 004 и не блокируют typed port, fake-provider suite или инженерный план.
