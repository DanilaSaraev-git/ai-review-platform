# Evidence: Гостевой доступ

Дата: 2026-09-06. Объём: [spec.md](spec.md), [plan.md](plan.md), [tasks.md](tasks.md).

## Состояние

Гостевой режим развёрнут: current `3a0ab32c90f6e2aaf5b69e99b1875105761a2b3e`, previous `398c01983814811de9c4495399e07719e2ed9067`, schema `20260906_0003`, `REVIEW_GUEST_ACCESS=true`. [Основной интерфейс](https://135.106.195.62/new) доступен без кода; подготовленный `/demo` сохраняет Basic-допуск. Локальный gate, production promotion, проверка изоляции/перезапуска и isolated restore пройдены. T014–T015 завершены.

В срезе не меняется действующий поставщик модели. Тесты используют синтетические данные и fake adapter/provider; они не подтверждают качество реального ревью.

## Подтверждённые локальные проверки

| Проверка | Результат |
| --- | --- |
| `pytest -q packages/review-runtime/tests/test_guest_contexts.py packages/review-core/tests/test_execution_coordinator.py` | 15 passed: 8 новых lifecycle/runtime tests и 7 существующих coordinator tests |
| Single-flight и scopes | 10 одновременных borrowers используют один context; два гостя имеют отдельные platform/runtime; private namespace не изменяется |
| Отмена caller и idle cleanup | Фоновая работа переживает отмену HTTP waiter; повторный borrower присоединяется; context закрывается после завершения работы |
| Ограничение живых contexts | При лимите 1 второй гость ждёт окончания первой фоновой операции; завершённые contexts освобождаются |
| Реальный класс `LLMReviewRuntime` с fake adapter | Записи двух гостей попали в отдельные storage; при общем лимите 1 одновременно выполнялся максимум 1 вызов; дочерние runtime не закрыли shared HTTP client, parent закрыл его |
| Startup и ошибки создания | Reconciliation разрешён до обработки запросов; отказ создания не оставляет занятую ёмкость registry |
| Ruff | Все `packages/`, `apps/`, `tests/` и `tools/` прошли проверку |
| Mypy | `--follow-imports=silent` для четырёх изменённых source files прошёл без ошибок |
| Связность документации | Проверены 66 локальных ссылок в 11 новых/изменённых Markdown-файлах; цели и Markdown anchors существуют; `CLAUDE.md -> AGENTS.md` остаётся относительным симлинком |
| PostgreSQL guest integration | 17 passed, включая квоты, изоляцию, cookie/restart и ML concurrency: 3 запроса завершились при общем лимите 2 |
| Миграция и guest contract | 13 passed на отдельной тестовой БД |
| Gateway | 9 passed с настоящим nginx, включая приватность демо и согласованность гостевого режима |
| Backup и переключение режима | 12 passed; включая 4 Linux shell integration с настоящими scripts и fake Docker |
| Guest ops после merge `398c019` | 9 passed; 4 новых opt-in promotion tests пройдены отдельно |
| Web | 104 tests в 23 files passed; API generation, typecheck, lint и build прошли |
| Web после merge | Дополнительно 20 RunStatePanel tests passed; typecheck, lint и build прошли |
| Общая типизация после merge `398c019` | Штатный `uv run mypy`: 110 source files без ошибок |
| Canonical contract tooling | validate, generate и TypeScript-проверка прошли |
| Итоговый backend gate после merge `398c019` | 397 passed, 11 skipped, 4 warnings; opt-in Docker проверки пройдены отдельно, включая 4 новых promotion tests |

В первом интеграционном прогоне обнаружено: foreign run ID внутри собственного workspace возвращал `409 report_unavailable`. В `PostgresReviewPlatform.report()` добавлен `get_run()` перед чтением отчёта; повторный guest integration gate прошёл.

В промежуточном backend-прогоне две проверки прежнего baseline требовали обновления — защищённый web и whitelist таблиц metadata. Обе исправлены под опциональный гостевой режим и новую таблицу; targeted gate дал 14 passed, после чего итоговый backend gate прошёл полностью с отдельно проверенными opt-in Docker сценариями.

## CI после публикации PR #5

Backend `release-check` прошёл. Первый web E2E gate: 44 passed, 2 skipped, 1 failed. Единственный отказ — прежний locator `Отчёт не опубликован.` после принятого изменения диагностики совпал с двумя текстами. В test-only commit `3be6f8c8f1befd2b2f6a5617d4397621a728b62a` поиск уточнён `exact: true`; UI и production code не менялись. Focused E2E прошёл: 1 passed на `localhost:18207` за 3,9 секунды. После исправления отправлен повторный полный CI; актуальный статус доступен в [PR #5](https://github.com/DanilaSaraev-git/ai-review-platform/pull/5). Production выпуск T014–T015 подтверждён отдельными проверками ниже.

## Фактический production выпуск, 2026-09-06

| Проверка | Наблюдаемый результат |
| --- | --- |
| Promotion и смена режима | Release `3a0ab32c90f6e2aaf5b69e99b1875105761a2b3e` сначала установлен с guest=false; проверка прошла. Затем переключение guest=true и повторная проверка прошли |
| Два независимых HTTPS посетителя | Два curl cookie jars получили разные workspace/actor; действующая cookie возвращает прежнюю identity |
| Upload и download | Загрузка синтетического файла вернула 201; собственный файл — 200, SHA-256 содержимого совпал |
| Граница доступа | Через `/api/v1` и `/v1`: собственные данные 200, чужие 404, отсутствие cookie 401, cross-origin запрос 403; `/demo` без Basic — 401 |
| Согласованный backup и restart | Backup остановил и снова запустил API, proxy и gateway; после restart проверены та же guest identity и SHA-256 загруженного файла |
| Isolated restore | Backup `20260906T134547Z`: 20 документов, 5 отчётов, 4 хода диалогов, 2 решения, 27 файлов артефактов. Количества и хеши совпали |
| Копия вне VPS | Набор сохранён в приватном каталоге владельца; SHA-256 и permissions 0700/0600 прошли проверку |
| UI production release | CUA через SSH-туннель `localhost:18106`: sidebar 202 px, `rgb(143, 24, 40)`, Onest, logo loaded; форма с профилем и моделью отображается |
| Внешний HTTPS | `curl --interface en0` прошёл с проверкой сертификата; основной `/new` доступен без кода |
| Состояние эксплуатации | Свободно около 16 GB; backup, certificate renewal и model probe timers активны |

Прямой переход IAB к публичному HTTPS сорвался на локальном соединении. Поэтому браузерный осмотр выполнен через приватный SSH-туннель к реальному release, а внешняя HTTPS-доступность подтверждена независимо curl. Прямой browser HTTPS PASS не заявляется.

В ходе production выпуска и приёмки агент не выполнял вызовов модели. Существующие отчёты/диалоги в восстановленной копии не являются новыми генерациями этой проверки. Порядок эксплуатации и ограничения отката после schema `0003`: [deployment.md](../../docs/operations/deployment.md).

## Границы результата

Cookie действует 30 дней с продлением при использовании; данные после истечения не удаляются. Восстановление доступа после потери cookie отсутствует. Лимиты исходных загрузок и reserve check не являются измерением полного расхода диска. Предметная экспертная оценка, нагрузочная ёмкость сервера и реальные пользовательские результаты в этом срезе не измерены.
