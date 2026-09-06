# Evidence: 006 MVP launch

Статус: MVP реализован и развёрнут. Дата: 2026-09-05/06. Baseline: `2a61354`.
Рабочий release: `efe06f13c6f0c52d164b1c34df5e6fd81bc238f8`.
Адрес: [https://135.106.195.62](https://135.106.195.62). Доступ защищён общим gateway;
credentials переданы владельцу через приватный локальный файл вне репозитория.

## Выполненные подготовительные проверки

- Актуальный technical repo отделён от product knowledge; создана отдельная ветка codex/mvp-launch-20260905 от integrated main.
- Web baseline: typecheck, lint, 94 unit tests, build, 29 Playwright tests — passed (web agent).
- SpecKit: spec/plan/research/data model/contracts/quickstart/tasks созданы; quality checklist 16/16. Это готовность требований, не production release.
- Server read-only audit: Ubuntu24.04, 2 GiB RAM + 2 GiB swap, 40 GiB disk; web/API/Postgres healthy на loopback, нет TLS/gateway/scheduled backups; найден uncommitted deployment overlay.
- Backend diagnosis: default durable fixture выглядит доступной моделью; production должен перейти на explicit unconfigured runtime.

## Границы готовности

Web, runtime, protected gateway, restore, фактический rollback, restart и timers проверены.
Подключена DeepSeek V4 Flash через Yandex AI Studio; подключение проверялось без генераций.
Позже первый пользовательский запуск получил semantic отказ, а следующий завершился
с публикацией отчёта. Это подтверждает успешный ответ в одном запуске, не качество
модели или надёжность провайдера. Исторический smoke Kimi ниже относится к прежней
конфигурации. Профиль и порядок эксплуатации описаны в
[руководстве оператора](../../docs/operations/deployment.md).
Предметное качество LLM и оценка дизайна пользователем не проверялись. MVP рассчитан на одну
доверенную группу с общим workspace/actor. Постоянное автоматическое внешнее хранилище
копий ещё не выбрано; проверенная копия с VPS сохранена у владельца. На текущем Mac выявлен
внешний дефект VPN-маршрута; прямой маршрут работает, настройки сети пользователя не менялись.

Ниже сохранены результаты этапов в хронологическом порядке. Промежуточные неуспешные
проверки F1–F6 закрыты последующими исправлениями или подтверждённой диагностикой;
окончательное состояние записано в конце документа.

## Slice 1 — visual baseline

Коммит `20f1170` — `feat(web): simplify review workspace`. Пройдены typecheck, lint, 94 unit tests, production build и 33 Playwright scenarios. Координатор визуально проверил screenshots подготовки на 1280×720 и 390×844, отчёта на 1440×900: белые рабочие поверхности, светло-серый фон, красный акцент, читаемый текст, документ и правая панель; на подготовке основной action виден без прокрутки.

Найденные остатки для функционального этапа: detail/dialogue пока в длинной общей панели, duplicate decision/status, error recovery, history pagination, anchor positioning. Они не считаются закрытыми этим visual commit. Рендеры локальны в `.local-qa/006-mvp/`, synthetic fixtures; оценка пользователем ещё не проведена.

## SpecKit analyze — требования и план

Проверены 18 FR, 8 SC, 4 user stories, 25 tasks и 7 принципов AGENTS. Каждый FR/SC имеет задачи: visual FR001–004/016–018 → T007–T011; flow FR005–008/014 → T011–T014; deployment FR009–010/013 → T015–T018/T022; recovery FR011–012 → T019–T022; stage evidence FR015 → T001–T003/T023–T025. Нет блокирующих противоречий публичному контракту или trusted deployment. Субъективная оценка дизайна и реальная LLM явно отделены от инженерных gates. Эта проверка не утверждает завершённость реализации.

## Slice 2 — runtime

Коммит `4531968` — `fix(runtime): prepare bounded honest MVP launch`. Добавлены unconfigured composition, соблюдение runtime budgets, общий предел model calls, ограниченное чтение upload и корректная выдача Unicode filenames через RFC5987. Исправлены потеря нового состояния диалога при сохранении решения и история запусков (created_at DESC, id DESC, pagination 20+1).

Backend agent: targeted regressions 13 passed; integration 50 passed; unit/runtime/CLI/contract/security 200 passed; migrations 8 passed на чистой PostgreSQL18; Ruff и mypy (103 source files) passed. Contract protected-path gate запускался с явно разрешённым web-путём, поскольку visual commit входит в этот согласованный срез. Публичный HTTP/JSON не изменён. Общий live web/backend сценарий проверяется отдельно.

## Convergence finding F1 — model connection

HIGH / contradicts / FR-008, FR-013, SC-008: operator model configuration использует внешний profile ID, а runtime пытается seed-ить встроенный fixture под тем же identity. Это вызывает immutable drift; без override встроенный fixture остаётся доступным рядом с внешней моделью. Обнаружено независимым backend review после основного runtime commit; server owner подтвердил стык. Добавлена T026, отдельный regression/fix обязателен до model-connect gate. Остальная подготовка продолжается.

## Convergence finding F2 — availability admission

HIGH / missing / FR-008, FR-013, SC-008: внешний профиль стартует с unavailable/not_observed, create-run запрещён, а наблюдение available сохранялось только после успешной генерации. Получался замкнутый круг без operator activation. Добавлена T027: использовать объявленную негенеративную проверку и сохранять/обновлять availability, не вызывать generation из readiness. Проверка подключения проводится только на fake provider.

## Convergence finding F3 — API docs

MEDIUM / missing / FR-009, FR-014: существующая страница API docs запрашивает `/openapi.json`, но приложение не публиковало этот путь, поэтому интерфейс документации получал 404. Добавлена T028: вернуть каноническую схему по ожидаемому адресу и проверить, что gateway защищает и страницу, и схему. Бизнес-контракты существующих операций не меняются.

## Slice 2 — model activation convergence

Коммит `15b5613` — `fix(runtime): activate configured model safely`. Закрыт runtime identity drift (T026); реализован `review-cli model-probe`: GET-only объявленный probe, mounted-file secret, отсутствие redirects и generation, сохранённое observation с TTL, safe JSON/exit 2 при недоступности. Каноническая схема доступна по `/openapi.json` для существующей offline docs. Operator scripts и gateway проверяются отдельно в deployment slice.

Backend agent: focused 24 passed; integration 51 passed; unit/runtime/CLI/contracts/security 203 passed; Ruff и mypy (104 source files), diff-check passed. Переход unconfigured→ML и availability→review admission проверены на fake provider; реальный сетевой вызов модели не выполнялся.

## Recovery gate до выпуска

2026-09-05 21:41 UTC на исходном VPS создан backup `20260905T214144Z`. В отдельной PostgreSQL восстановлены 3 версии документа, 3 отчёта, 2 хода диалога и 2 решения. Для 6 DB artifact records проверены сохранность, размер и SHA-256; в архиве 8 файлов. Логический fingerprint совпал. Исходные volumes не изменялись; после короткой остановки на согласованную копию API/proxy снова healthy и loopback readiness passed. Это проверка существующих непустых данных, не только пустой базы.

## Convergence finding F4 — CI integration

HIGH / missing / FR-014, FR-015: стандартный CI вызывает protected-path gate без локальных allow-path, а закреплённый baseline предшествует авторизованному редизайну. Проверка без исключений возвращает failed на изменениях apps/web. T029 закрепляет новый принятый web commit после визуальной/функциональной приёмки; остальные защищённые каталоги должны остаться неизменными. Автоматическое разрешение произвольных изменений не используется.

## Slice 2 — functional web

Коммит `423e45f` — `feat(web): complete MVP review workflows`. Решение и диалог разделены вкладками с сохранением mounted drafts. Исправлены conflict/refetch/retry, потеря черновика при фоновом сбое, устаревшая отметка сохранения, пагинация истории, состояния ошибок и неоднозначные anchors. Тестовый результат определяется по provenance, неподключённая модель показана явно. Desktop панели прокручиваются внутри рабочей области; mobile toolbar закреплён при чтении.

Web agent: typecheck/lint/build passed, 100 unit tests passed, 41 Playwright scenarios passed; 2 live tests ожидаемо пропущены в MSW запуске. Отдельный `LIVE_WRITE=1` запуск без MSW прошёл upload→review→dialogue→confirmed decision→browser reload через isolated durable HTTP API. Run `3b42de4f-3310-4db1-b702-ad8a1364efe5`, document `5172e134-01b8-4a4f-9431-db45daa98524`. Backend restart gate отдельно подтвердил неизменные report bytes/SHA/ETag и сохранённые dialogue/decision. Координатор просмотрел desktop 1440×900 и mobile 390 screenshots; субъективная оценка пользователем остаётся открытой.

## Slice 3 — deployment/recovery implementation

Коммиты `b75b0d1` — `feat(deploy): add protected MVP gateway`, `bdb75ad` — `feat(ops): add recoverable release workflow`. Сборка web image прошла с небольшим build context без host node_modules. Проверены base/production/external Compose config, nginx config, full synthetic flow и restart persistence. В production composition доступны нейтральные labels и единственный unavailable profile. Прямые `/v1` и same-origin `/api/v1` маршруты сохранены.

Независимый ops review нашёл и закрыл ошибки atomic model mode, rotation при включённой модели и failure rollback. Private legacy.env сохраняет фактические ID старого исполнения; legacy rollback запрещён при активной модели, возвращает loopback-only версию и останавливает несовместимые timers. Rotation требует предварительного disable; failure восстановления возвращает прежние контейнеры. Targeted re-review и bash syntax/Compose validation passed, launch blockers в этом стыке не осталось.

Непустая копия `20260905T214144Z` также скопирована с VPS в приватный каталог владельца (0700/0600), локальные SHA проверены. Постоянное автоматическое внешнее хранилище не настроено; локальная daily copy на VPS сама по себе не защищает от потери всего сервера. Публичный TLS, actual promotion, rollback/re-promotion и timers ещё проходят внешний gate.

## Integrated acceptance перед выпуском

Финальная правка `52d3b3c` убрала повторные счётчики замечаний и имя документа; toolbar сохранил статус и имя. Typecheck/lint, 7 relevant unit и 2 targeted Playwright tests passed. В `7a96a89` approved web baseline закреплён на полном SHA этого коммита. Не-web protected paths не менялись от прежнего baseline; автоматических исключений нет.

Стандартный `env -u PROTECTED_PATH_ARGS make release-check-local` passed: Ruff, mypy 104, contracts 81, unit 110, security 12, protected gate. Дополнительно в этом срезе ранее прошли integration 51 и migrations 8; web полный gate — 100 unit и 41 Playwright, реальный HTTP write/reload и backend restart проверены отдельно. Markdown links и относительный symlink CLAUDE.md проверены. Модель не подключалась; внешний production gate записывается после установки.

## Convergence finding F5 — actual legacy transition

HIGH / contradicts / FR-011, FR-012, FR-015: первая попытка promotion `f3c2dfb` обнаружила drift display labels в `_seed_exact`. Private legacy.env содержал прежние model/dialogue ID, но не все фактические REVIEW labels. Current symlink остался на `2a61354`; после восстановления точной legacy конфигурации loopback API снова healthy. Данные не удалялись и не заменялись backup. Добавлена T030 для двустороннего согласования labels до seed, failure recovery и реального цикла new→legacy→new. Предыдущий read-only review не выявил этот переход; успешный выпуск пока не заявляется.

## GitHub CI

На опубликованном `f3c2dfb` оба workflow завершились успешно: [backend release-check](https://github.com/DanilaSaraev-git/ai-review-platform/actions/runs/33994456776) и [web checks](https://github.com/DanilaSaraev-git/ai-review-platform/actions/runs/33994456773). Этот результат проверяет код и синтетические сценарии; фактическая совместимость состояния старого VPS проверяется отдельным T030.

## Исправление перехода между выпусками

Коммит `dbb330a` — `fix(ops): preserve seed identity across releases`. Deployment labels согласуются до seed соответствующей версии, в том числе при failure rollback. Неполный legacy.env мигрирует атомарно из фактической конфигурации здорового старого API; полный файл проверяется по seed-critical keys. Также исправлены обработка вывода SQL-команды без SIGPIPE и redirect API docs на публичный HTTPS origin.

На PostgreSQL18 пройдены реальные команды: existing neutral→legacy labels, empty→deferred (exit 0), partial→rollback без изменения имени (exit 1). Bootstrap: старый файл с 3 keys обновлён до 18 REVIEW_*; повторный запуск сохранил hash; без работающего API неполная конфигурация отклоняется. Nginx/Compose/bash/diff checks passed; независимый targeted review не нашёл оставшихся blockers. Current VPS после проверок остаётся healthy на legacy `2a61354`. Фактический цикл нового выпуска и отката проходит следующим шагом.

## Первый успешный production promotion

На VPS установлен `501cf8618526140412cb8458a70c6989f601c3d2` из чистого Git archive (SHA-256 `bc1cb0e4d127dbe84ae064d5c379a1a2acd0fe9e3e978b51da7352d09d4d56f2`). Prebackup, build, migration, labels, startup и verify прошли; current symlink указывает на этот release. [Backend CI для этого SHA](https://github.com/DanilaSaraev-git/ai-review-platform/actions/runs/33996207753) также passed.

Server agent проверил с локальной машины: HTTP→308, 8 защищённых aliases без credentials→401, authenticated bootstrap с нейтральными labels, единственный unavailable `model-not-configured`, 3 прежних документа, OpenAPI/docs и точный redirect `/docs` на публичный HTTPS. Встречались единичные handshake timeouts; запросы повторялись, финальная стабильность проверяется после restart/rollback gate. Timers установлены, model probe без enabled marker завершился без сетевого вызова. Фактический rollback/re-promotion и финальная проверка ещё выполняются.

## Реальный rollback gate

Откат `501cf86`→legacy `2a61354` выполнен: current переключён, loopback healthy, публичные 80/443 закрыты, несовместимые timers остановлены. Данные сохранились: 3 document versions, 3 reports, 2 dialogue turns, 2 decisions, 6 artifact records; список документов содержит 3 записи. Данные из резервной копии не восстанавливались.

При проверке обнаружен false-positive: старый `/v1/bootstrap` возвращает SPA HTML с HTTP 200. Коммит `ed3d4d6` — `fix(ops): validate legacy rollback API` — использует фактический `/api/v1/bootstrap` и проверяет JSON, exact organization/workspace/actor IDs и labels до переключения symlink. Реальный legacy JSON прошёл, HTML отклонён; независимый targeted review passed. Обратная установка финального release выполняется после этого уточнения gate.

## Convergence finding F6 — external handshake sampling

HIGH / missing / FR-009, FR-014, SC-005: независимая серия root во время финальных maintenance работ дала 7 успешных и 7 неуспешных запросов (5 curl exit 28 во время TLS handshake, 2 exit 35). Успешные HTTPS запросы имели ssl_verify_result=0: auth bootstrap 200 с ожидаемыми labels, no-auth API/schema/health 401, cross-origin mutation 403; plaintext redirect 308. Неуспешные запросы не доказывают ошибку приложения или сертификата. T031 повторяет минимальный probe после прекращения restart/backup и сопоставляет host/network/browser evidence; доступность пока не считается окончательно проверенной.

## Финальный выпуск и эксплуатационная приёмка

Рабочая версия — `9aad090e1d007c16e55d79dbfcd166ce4ca7a8c5`, установленная после успешного
цикла `2a61354`→`501cf86`→`2a61354`→`9aad090`. T030 закрыта фактическим переключением
версий и проверкой exact seed. Current symlink и версии контейнеров согласованы; все
контейнеры перезапущены, полный deployment gate после restart прошёл. Сохранились
3 версии документа, 3 отчёта, 2 хода диалога, 2 решения и 6 DB artifact records.
Для отката не потребовалось восстанавливать данные из копии.

T022 закрыта: HTTP redirect, gateway на всех API/docs/document aliases, cross-origin denial,
authenticated UI/API и приватные DB/API проверены. Сертификат Let's Encrypt для IP
`135.106.195.62` проходит системную проверку и действителен до 2026-09-12 12:52:08 UTC;
staging renewal dry-run passed. Активны renewal (02:00/14:00 UTC, jitter ≤20 min), backup
(00:30 UTC, jitter ≤30 min, retention 14) и minute model probe timers. Без enabled marker
probe не вызывает сеть. Readiness возвращает `ready`, composition `unconfigured`; database,
business_schema, exact_seed и artifact_store checks — true. Каталог содержит ровно один
недоступный профиль `model-not-configured`. Реальных запросов модели не было.

Финальная копия `20260905T224545Z` прошла isolated restore: логический fingerprint БД
совпал, каждый из 6 DB artifacts проверен по пути/размеру/SHA-256; архив содержит 8 файлов.
Набор скопирован с VPS в приватный локальный каталог владельца с mode 0700/0600, SHA-256
проверены отдельно. Автоматическое offsite-хранилище остаётся эксплуатационным продолжением.

На завершении VPS: load average 0.33/0.59/0.52, доступно 1.4 GiB RAM, занято 34 MiB swap,
диск 29%; OOM и ошибки/drops интерфейсов не обнаружены. Это наблюдение во время приёмки,
не нагрузочный тест или обещание SLA. Локальные QA containers/networks удалены без `-v`;
данные в named volumes сохранены. Рабочий VPS оставлен запущенным.

## T031 — подтверждённая причина TLS failures

После завершения maintenance обычный маршрут Mac через `utun7` дал 4/6 успешных запросов
и два handshake timeout. Минимальный differential — тот же HTTPS запрос с привязкой только
его сокета к `en0` — дал 10/10 успешных 401 с `ssl_verify_result=0`, без retry, за 48–59 ms.
Независимая серия server agent: `en0` 12/12, `utun7` 7/12. Полный authenticated внешний
gate по `en0` также passed без повторов: bootstrap IDs/labels, документы, profiles, health,
OpenAPI 3.1.0, docs и gateway aliases.

Причина локализована в VPN-маршруте текущего Mac, а не в сертификате или готовности API.
T031 закрыта подтверждённой диагностикой; внешний клиентский дефект не объявлен исправленным.
Владельцу может потребоваться прямой маршрут/исключение IP из VPN. Системные настройки
сети, SSH и проверка доверия TLS не ослаблялись.

## Финальная визуальная проверка production

Playwright с HTTP credentials и `ignoreHTTPSErrors:false` открыл deployed UI. Все запросы
кроме GET/HEAD/OPTIONS блокировались: write attempts = 0. История содержит 3 записи,
подготовка явно показывает неподключённую модель и отключённый запуск, synthetic report
помечен «Тестовый результат», документ, dialogue и сохранённое confirmed decision доступны.
Проверены desktop 1440 и mobile 390. Для стабильной проверки на Mac использован временный
localhost CONNECT relay только к IP сервера, с outbound `en0` и end-to-end TLS; после QA
relay и временный файл удалены, порт освобождён.

Координатор просмотрел свежие production screenshots. Мобильный кадр первоначально был
снят во время загрузки; повторный capture дождался текста и корректной подсветки фрагмента,
без предупреждения о несопоставленном anchor. Кадры сохранены только локально в игнорируемом
`.local-qa/006-mvp/production-*.png`. Клиентские материалы в репозиторий не добавлялись.

## Финальный SpecKit analyze / converge

Проверены spec, plan, tasks, research, data model, contracts и quickstart. Все 18 FR и 8 SC
покрыты выполненными задачами и проверками; 4 истории реализованы в принятой области MVP.

| Требования | Задачи | Подтверждение |
| --- | --- | --- |
| FR-001–004, FR-016–018; SC-001–002 | T007–T011 | Visual commits, web gates, desktop/mobile production QA |
| FR-005–007, FR-014; SC-003–004 | T011–T014, T022 | Live HTTP flow, conflict/retry, immutable report, restart |
| FR-008, FR-013; SC-008 | T012, T017, T026–T027 | Unconfigured production, fake-provider activation/probe/admission |
| FR-009–010; SC-005 | T015–T018, T022, T028, T031 | TLS/auth/origin/private ports, trusted single workspace |
| FR-011–012; SC-006 | T019–T022, T030 | Actual rollback/re-promotion, consistent backup and isolated restore |
| FR-015; SC-007 | T001–T003, T023–T025, T029 | Stage commits, standard CI gate, operator handoff and explicit limits |

31 tasks, checklist 16/16, 7 AGENTS principles: PASS. F1–F5 исправлены с regression/actual
deployment evidence; F6 диагностирован с сохранением явной клиентской границы. Невыполненных
задач реализации в согласованной области не осталось; новые convergence tasks не нужны.
SpecKit prerequisites прошли с явным feature directory; локальные ссылки в 11 Markdown
файлах, относительный `CLAUDE.md -> AGENTS.md` и `git diff --check` проверены без ошибок.
Реальная модель, пользовательская эстетическая оценка, multi-company SaaS и постоянное
автоматическое offsite-хранилище не объявляются выполненными.

[Backend CI deployed SHA](https://github.com/DanilaSaraev-git/ai-review-platform/actions/runs/33996795001)
passed. Web source после ранее успешного full web CI не менялся. Финальный документационный
коммит не требует повторного развёртывания: код установленного release остаётся тем же.

## Передача владельцу

- Открыть [сервис](https://135.106.195.62); gateway credentials находятся в приватном
  локальном файле владельца вне Git и будут указаны локальной ссылкой в итоговом ответе.
- Подключить профиль/ключ модели и выполнить compatibility smoke по
  [руководству оператора](../../docs/operations/deployment.md#подключить-модель).
- Для отката использовать `rollback-release.sh` с полным SHA предыдущего release.
  Проверенный legacy target `2a613542056dd7b132a077a7c5b0619ff2bb733a` возвращает loopback-only
  сервис; для возврата публичного нового выпуска требуется promotion и установка timers.
- Отдельные commits сохранены в `codex/mvp-launch-20260905`; merge в main не выполнялся.
  Постоянное внешнее хранение копий и вход отдельного SSH-оператора по ключу остаются
  явными эксплуатационными продолжениями. На текущем Mac нужен исправный маршрут к IP вне VPN.

## Kimi K2 — подготовка серверного выпуска 2026-09-06

Пользователь поручил подключить выбранную Kimi K2 и выпустить обновление на существующий
сервер. Код переносится поверх 2fb8785; текущий server release перед обновлением — 9aad090.
Перенесены только plain JSON schema transport, семантическая проверка CLI smoke и профиль
`kimi-k2-hf-novita` 1.0.0. Production model-probe/timer, limits, gateway и UI сохранены.
Токен передаётся отдельным private file; в release archive секрета нет.

Targeted adapter/CLI gate: 34 passed. `release-check-local`: 81 contract, 125 unit/CLI,
12 security passed; Ruff и mypy (104 файла) passed; canonical schemas/client/protected paths passed.
Compose web/API build, synthetic smoke и restart на отдельном loopback стенде прошли.

Полный PostgreSQL gate выявил существовавший до Kimi рассинхрон: bootstrap сохранял
`max_member_turns=null`, основной runtime после `4531968` ожидал runtime budget. Исправлен
bootstrap с использованием того же validated config; regression с лимитом 7 прошёл red→green.
Guard неизменяемых версий не ослаблен, существующие записи не перезаписываются. На заново
созданной одноразовой test schema migration 8 + integration 52 passed.
Synthetic Compose fixture также актуализирован: явно задан внешний model profile ID и
используется выбранный app image. Это изменения тестовой конфигурации, не production defaults.

Ранее зелёный CI выполнял `release-check-local` без PostgreSQL suites; историческое полное
свидетельство 004 относится к более раннему baseline. Неуспешный новый прогон не скрывается
этими прежними результатами. Статус серверной установки фиксируется отдельно ниже после
promotion, enable и реального smoke.

После исправлений полный последовательный backend gate: 81 contract + 125 unit/CLI +
12 security + 8 migration + 52 integration + 9 E2E = **287 passed, 1 optional skip**.
Optional skip относится к отсутствующему local-model endpoint; HF будет проверяться отдельно
на сервере. Synthetic external-model Compose прошёл на настоящей сети Docker с fake provider.
Image web/API собран; synthetic report сохранил SHA-256 и ETag после restart.
Перед packaging проверены отсутствие credential и локальных путей, ссылки и symlink инструкций.

Серверный release `c61434de2ecba31e4bcd6d24aa045cd624bc64bd` успешно установлен после
predeploy backup `20260906T074046Z`; gateway/TLS/origin/private services passed.
Отдельный model preflight до включения обнаружил несовместимость старой записи навыка:
`review-data-spec` 1.0.0 хранит legacy digest (только файлы), а ML registry проверяет canonical
digest (manifest и файлы). CLI вернул `invalid_configuration`; рабочий сервис остался в
unconfigured режиме. Историческая запись не менялась. Исправление и повторная установка
отслеживаются в T037; это отдельный обнаруженный стык, не ошибка токена или Kimi.

Навык выпущен как 1.0.1 без изменения текста инструкций и legacy digest. Regression
реального пакета прошёл red→green и проверил unconfigured→ML→probe→review→unconfigured,
новую версию в execution snapshot и полную неизменность прежней SQL-записи 1.0.0.
Повторные проверки: 53 integration на чистой PostgreSQL, 52 registry/CLI/ML contract passed;
Ruff, diff check и стандартный protected-path gate без исключений passed. Ранее пройденные
web, migration и E2E gates не повторялись: UI, schema и runtime code этим исправлением не менялись.

## Kimi K2 — фактический серверный выпуск 2026-09-06

Установлен `5a3dae85d5dc6f3d5538969b3ddee810de5c5b02`; previous указывает на
`c61434de2ecba31e4bcd6d24aa045cd624bc64bd`. Штатный promotion создал predeploy backup
`20260906T075020Z`. Набор скопирован в приватное хранилище владельца вне VPS и Git;
локальные SHA-256 dump/archive и permissions 0700/0600 проверены. Новый restore drill
для этого набора не проводился; предыдущий успешный drill сохранён выше.

`model-configure` установил профиль и credential отдельно от release; runtime читает
смонтированный secret. `model-enable` завершился успешно, declared GET probe сохранил
`available`; gateway/TLS/origin/private ports passed. Таймеры backup, certificate renewal
и model probe активны. Server app/web images закреплены на полном SHA нового release.

Реальный smoke через `https://135.106.195.62/api/v1` с системной проверкой TLS и gateway
credentials использовал только явно синтетический `synthetic-kimi-smoke.md` из двух строк.

| Проверка | Результат |
| --- | --- |
| Review run | `542b68e9-2c69-425e-a525-81a37f9e8718`, completed, 47.579 s, 6 findings |
| Model provenance | `huggingface-novita`, `moonshotai/kimi-k2-instruct`; model version unknown |
| Review usage | 1 244 input / 1 873 output tokens |
| Skill snapshot | `review-data-spec` 1.0.1, canonical digest `93f89a407f19fb3035bee58b8aa355aaf2587bfab7f1bcf4663baad9fbdc71f7` |
| Dialogue turn | `88891ba4-640d-45e8-a999-976dc04c8d7f`, completed, 4.272 s, revision 2 |
| Immutable report | SHA-256 `ace7735968631e56034d2a017fede73240d71e2a9d2d29a5bb85c527faf34a33`; bytes unchanged after dialogue |

Это один успешный compatibility smoke, без повторов генерации. Он не измеряет качество на
пользовательских документах, надёжность провайдера или SLA. Прежние локальные неуспешные
прогоны не опровергаются этим результатом. Сохраняются лимиты профиля: 32 768 UTF-8 bytes
на полный вход с инструкциями и schema, 4 096 output tokens; chunking и auto-repair не добавлены.

Откат на previous требует успешного `model-disable.sh`, затем `rollback-release.sh` с полным SHA
`c61434de2ecba31e4bcd6d24aa045cd624bc64bd`: эта версия пригодна для unconfigured работы,
но не для повторного включения Kimi до возврата исправленного release.
DB/volumes и immutable версии сохраняются.

После завершения генераций выполнен restart API. Проверка непосредственно в окне запуска
получила 502; после перехода контейнера в healthy полный deployment probe прошёл.
Отдельное чтение подтвердило прежний SHA-256 отчёта, completed dialogue с revision 2 и
доступную модель. Model-probe service завершает обновления с exit 0. Локальные одноразовые
Compose-стенды проверки удалены вместе с их тестовыми volumes; production volumes сохранены.

T032–T037 выполнены. Документационный commit после установленного release не меняет код
на сервере. Ключи, документы и журналы не входят в коммиты; постоянное автоматическое
offsite-хранилище и предметная оценка остаются отдельными продолжениями.

## Инцидент: ограничение длины ответа и последующий billing block

2026-09-06 пользователь сообщил `model_output_invalid`. Безопасные model-attempt metadata
подтвердили `finish_reason=length`, ровно 4096 output tokens, latency 103402 ms. Это обрыв
по настройке выходного бюджета, а не ошибка подключения или ключа. Исходный ответ модели
не сохранялся, поэтому его содержимое не восстанавливалось и в репозиторий не переносилось.

Выпущен model profile `kimi-k2-hf-novita` 1.0.1 с max output 8192; config digest
`d1815b847c992809e4d121418c5ef3ca7c167ff8014d1f877fc58cc9cae6b579`.
Изменение применено на сервере через model-disable/configure/enable без замены application
release `5a3dae8`. Старые профиль и run не изменены. Проверка gateway/TLS/model mode passed.

Повтор исходного сценария сначала получил временный provider unavailable и штатный retry,
затем полный ответ: `finish_reason=stop`, 4464 output tokens, latency 110766 ms.
Обрезка устранена, но новый run завершился отдельным `validation_failed`; успешный отчёт
не опубликован. Конкретная причина семантической проверки пока не установлена: runtime
сохраняет общий код без исходного ответа. Временная диагностика с allow-list безопасных
причин выполнялась в отдельном процессе, без изменения работающего API, но следующий
вызов был отклонён до генерации.

Минимальный синтетический provider probe подтвердил HTTP 402 и сообщение о кредитах.
Дополнительная генерация прекращена; платежи, смена ключа и поставщика не выполнялись.
GET health probe к каталогу HF не подтверждает доступную платёжную квоту. По
[документации HF](https://huggingface.co/docs/inference-providers/pricing) бесплатный план
предоставляет $0.10 ежемесячных credits; для расхода сверх них нужна покупка credits.
Фактический баланс и план аккаунта в этой диагностике не читались.

Код runtime теперь проверяет non-stop finish reason до JSON/schema в review и dialogue,
включая запрет публикации валидного JSON при `length`. Public `model_output_invalid` и
`retryable=false` сохранены; для усечения добавлена безопасная точная server message.
CLI различает review/dialogue completion. Проверки: 8 regression red→green, затем
54 теста затронутого контура passed, Ruff и mypy 104 passed. Одноразовая test DB удалена.
Эти code changes доступны локальной разработке; на VPS пока обновлён только профиль.
UI продолжает выбирать общее сообщение по public code, поэтому точная server message
не является отдельным пользовательским экраном. Исторический compatibility gate — T040; после выбора Яндекса он отложен и не требует
новых генераций без отдельного поручения пользователя.

## Отдельный подготовленный деморежим, 2026-09-06

По новому поручению пользователя добавлен `/demo/new`: автономная web-сборка с приватным
runtime-пакетом документа, отчёта и ответов по замечаниям. Выбранный файл не анализируется;
исходник готового примера явно назван, вызовов модели нет. Приложение сохраняет решения
и диалоги отдельно для каждого замечания в текущей вкладке браузера. Основное приложение
и настройки внешней модели сохраняются.

Локально проверены: typecheck, lint, 100 unit tests и 2 E2E на production-сборке демо.
E2E покрывают произвольную загрузку, PDF и страницу привязки, подготовленный ответ,
решение, обновление, независимость замечаний, неизменность отчёта и блокировку
случайного выхода в рабочий API. Отдельно проверен отказ до API при недоступном пакете.
`nginx -t`, production Compose и его объединение с external-model overlay прошли
проверку; redirect `/demo` возвращает относительный путь. Материалы клиента в Git и
Docker image не добавлялись. Эти проверки относятся к механике демо, а не качеству LLM.

При проверке опубликованной сборки обнаружена существовавшая проблема PDF.js:
nginx 1.29.4 отдавал module worker `.mjs` как `application/octet-stream`, браузер
отклонял загрузку и не рисовал PDF. Причина подтверждена browser console и отдельным
контейнером с фактическим worker asset. Добавлена явная MIME-карта
`application/javascript mjs`; `nginx -t` и проверка Content-Type проходят.

## Принятый Numbat и деморежим: protected-path baseline, 2026-09-06

По прямому поручению пользователя влить реквест и обновить сервер с новым дизайном
во всех сценариях принятый UI и действующий деморежим объединены в commit
`004c8b63020612f8aff70ecade8f9789476e5939`. Он закреплён как новый baseline
стандартного protected-path gate без `allow-path`. Сравнение с предыдущим baseline
`52d3b3c6eac4078e1922688d477ec343266860e0` подтвердило неизменность защищённых
каталогов `client`, `implementation/poc`, `specs/001-review-data-spec-poc` и
`specs/002-target-review-platform`. Перед фиксацией прошли 2 E2E production-сборки
демо, 13 E2E решения/диалога/постоянного документа, 25 unit затронутого контура,
TypeScript и ESLint. Обновлённый gate вернул `status=ok` и пустой список изменений;
`tests/contract/test_protected_paths.py` прошёл без исключений. Эта запись
подтверждает локальную интеграцию и проверки;
результат обновления сервера фиксируется отдельно после развёртывания.
## DeepSeek через Yandex AI Studio — фактическое подключение, 2026-09-06

По поручению пользователя T041–T042 выполнены без пробных генераций и запусков документов.
Из точного предыдущего production commit `33d94299150259a853bf47566fb77c59655ac4b8`
собран и установлен release `8913a73e2ff7beef407e6b745d1d84216625a600`.
Current/previous указывают на эти версии; promotion выполнил predeploy backup, сборку,
миграции и проверку инфраструктуры. Постоянные volumes сохранены.
Копия `20260906T115450Z` сохранена также в приватном локальном каталоге владельца
вне VPS и Git; SHA-256 dump/archive и permissions 0700/0600 проверены.
Отдельный restore drill для этого набора не выполнялся.

Активен профиль `yandex-deepseek-v4-flash` 1.0.0 с моделью
`gpt://<folder_id>/deepseek-v4-flash/latest`. В фактическом ответе GET каталога Яндекса
присутствует суффикс `/latest`; профиль использует именно этот идентификатор.
Одинаковая авторизация `Api-Key` и `OpenAI-Project` применяется в generation adapter
и негенеративном probe. Ключ и конкретный каталог сохраняются вне Git; временная копия
ключа в `/root` после успешного включения удалена.

Перед переключением старые profile, API key и model env сохранены в приватный каталог
`/opt/ai-review-state/model-backups/20260906T115706Z-before-yandex` с режимами 0700/0600.
Порядок возврата старой модели описан в [руководстве оператора](../../docs/operations/deployment.md).

Проверки текущего изменения:

- 31 offline transport/availability test, Ruff и mypy изменённых runtime modules — passed.
- Рендер профиля, canonical `ModelProfile` validation, shell syntax и проверка patch — passed.
- GET `/v1/models` с российского сервера вернул HTTP 200 и точный выбранный ID;
  штатный `model-enable` сохранил `available` в 2026-09-06 11:57:41 UTC.
- Полный deployment gate после включения: gateway, TLS, origin policy, private services
  и model mode — PASS; API, proxy, gateway и PostgreSQL healthy.
- Backup, certificate renewal и model probe timers активны. Внешний HTTPS без credentials
  вернул ожидаемый 401 с системной проверкой сертификата; использован прямой интерфейс Mac.

Лимит ответа в профиле — 16 384 токена, включая reasoning по контракту провайдера;
это заданный бюджет приложения, не заявленный максимум модели. Сохранён режим `plain_json`
с проверкой ответа приложением. Генерация JSON, review/dialogue compatibility и предметное
качество DeepSeek ещё не проверены. Закреплённый checkpoint за `latest` неизвестен.
Грант 4 000 ₽ указан пользователем; баланс и фактические списания в этой работе не проверялись.

## Отказ пользовательского запуска и потеря диагностики, 2026-09-06

Запуск `ccc1dd2a-54fa-4ee1-ab60-e0d86b0cdd00`, созданный пользователем в 12:04:09 UTC,
завершился `validation_failed`. В сохранённых metadata один model attempt: `succeeded`,
`finish_reason=stop`, 107 312 ms, 3 048 input / 6 267 output tokens при лимите 16 384.
Ошибка в ветке semantic mapping означает, что JSON и output schema пройдены, а evidence
или coverage отклонены. Конкретную цитату, ссылку или правило отказа установить нельзя:
raw response и исходный `ValueError` прежний код не сохранял. Это не доказывает конкретный
дефект модели или извлечения текста. Ответ модели повторно не запрашивался.

Исправлен отдельно воспроизведённый дефект диагностики: фиксированные коды
`ReviewSemanticValidationError` проходят через runtime в существующий `error.message`.
Код HTTP ошибки остаётся `validation_failed`; правила валидации, отсутствие публикации
при отказе и запрет автоматического retry сохранены. Неизвестные исключения сохраняют
безопасное общее сообщение; текст документа и ответа не записывается в диагностику.
UI продолжает выбирать тексты по публичному коду: в terminal state показывает итог
и длительность, а `retryable=false` больше не трактуется как доказанная бесполезность
новой проверки или необходимость менять входные данные.

Локальный feedback loop на отдельной PostgreSQL и fake provider:
`pytest -q tests/integration/test_ml_review_http.py -k semantic_failure --tb=short` —
сначала 3 failed, после исправления 3 passed. Он воспроизводит именно потерю причины
для неверной цитаты, неизвестного фрагмента и несогласованного охвата, не исходный
неизвестный ответ DeepSeek. Review HTTP + contract compatibility: 9 passed;
core/contract: 52 passed; общий dialogue quote seam: 13 passed; UI: 20 passed.
Typecheck, ESLint, web build, Ruff и mypy затронутых modules прошли.
Независимое review не выявило ослабления валидации или утечки данных.

Исходный ответ нельзя повторно провалидировать offline. Первоначально T044
предполагала отдельно разрешённую диагностическую генерацию; последующие
свидетельства ниже уточняют необходимость этой проверки и результат promotion.

Пока готовилось обновление, на сервере появился новый запуск проверки
`84eb13fa-3121-420f-809d-713e1de4ab08` в 12:16:51 UTC. Она завершилась `completed`
в 12:18:22 UTC без ошибки; запись отчёта существует. Обновление ожидало завершения
активного запуска и не прерывало его. Агент эту генерацию не инициировал.
Этот успех на прежнем коде показывает, что
отказ не постоянный. Он не восстанавливает причину первого ответа и не означает
предметную оценку отчёта. Дополнительная диагностическая генерация сейчас не нужна;
T044 применима, только если отказ повторится с новой диагностикой.
Диагностический release `efe06f13c6f0c52d164b1c34df5e6fd81bc238f8` установлен;
previous — `8913a73e2ff7beef407e6b745d1d84216625a600`. Gateway/TLS/origin/private services
и model mode passed; API, proxy, PostgreSQL и gateway healthy. Профиль Яндекса сохранён.
Predeploy backup `20260906T121846Z` скопирован в приватный локальный каталог вне VPS/Git,
проверены SHA-256 и permissions 0700/0600. Новый restore drill не проводился.
Security suite: 12 passed; после добавления fallback regression изменённый файл —
11 passed, включая 4 новых случая неизвестной причины. Protected-path gate сравнивал
с установленным baseline и разрешал только два изменённых UI-файла; неожиданных изменений нет.
T043 выполнена, агент не инициировал ни одной реальной генерации.

## Возврат принятого дизайна после выпуска из старой ветки, 2026-09-06

Пользователь сообщил об исчезновении нового интерфейса. Проверка установленного
`efe06f13c6f0c52d164b1c34df5e6fd81bc238f8` подтвердила отсутствие CSS `numbat-sidebar`.
Причина установлена по графу Git: выпуск с Яндексом и диагностикой происходил из ветки
без принятого UI merge `9cd7f10`. Новый дизайн не был удалён из репозитория.

В отдельной ветке `codex/restore-numbat-design` объединены `cc948a3` и `9cd7f10`.
Сохранены Numbat UI, отдельное демо, Яндекс, semantic diagnostics и отклонение
незавершённых ответов. Конфликты журнала и тестов разрешены с сохранением обеих линий.
65 core/runtime/security tests, 13 review/dialogue integration tests на отдельной
PostgreSQL, 22 UI tests, typecheck, ESLint, Ruff и protected-path gate прошли.
В браузере на локальной сборке проверены меню 202 px, `rgb(143, 24, 40)`, Onest и
загруженный логотип. Новые реальные генерации не инициировались.

Сначала выпуск был передан задаче гостевого доступа, чтобы исключить конкурирующие
обновления. Затем пользователь прямо возобновил поручение «обновляй сервер» и попросил
выполнить его максимально быстро. После остановки соседнего deployment подтверждены
исходный release `efe06f13c6f0c52d164b1c34df5e6fd81bc238f8`, schema `20260905_0002`,
отсутствие активных запусков и свободная блокировка выпуска.

Установлен release `9a4d767a8dcd30469a942d1f39b7f0751d5421a3`; previous —
`efe06f13c6f0c52d164b1c34df5e6fd81bc238f8`. Штатный promotion создал backup
`20260906T123911Z`; копия сохранена локально в приватном каталоге владельца вне Git,
SHA-256 и permissions проверены. Gateway/TLS/origin/private services/model mode — passed;
API, proxy, gateway и PostgreSQL healthy. Профиль Яндекса сохранён, новые реальные
генерации не инициировались. В браузере через приватный SSH-туннель к серверному proxy
проверены `/new` и `/demo/new`: широкое бордовое меню, логотип и новая форма на месте;
демо явно сообщает, что модель не вызывается. CSS `numbat-sidebar` присутствует в обеих
серверных сборках. Публичный HTTPS отдельно вернул ожидаемый 401 с проверкой сертификата.
После проверки временный локальный туннель закрыт.
