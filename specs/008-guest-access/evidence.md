# Evidence: Гостевой доступ

Дата: 2026-09-06. Объём: [spec.md](spec.md), [plan.md](plan.md), [tasks.md](tasks.md).

## Состояние

Код и контракт guest-v1 подготовлены в рабочем дереве. Локальные guest integration, migration/contract, gateway, backup и web проверки прошли. Реальная выкладка гостевого режима и браузерный smoke на опубликованном сервисе **ещё не подтверждены**. Текущий статус regression и release gates указан ниже.

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
| Ruff | Проверка `guest_contexts.py`, `ml_runtime.py`, `postgres/platform.py`, core `execution.py` и `test_guest_contexts.py` прошла |
| Mypy | `--follow-imports=silent` для четырёх изменённых source files прошёл без ошибок |
| Связность документации | Проверены 66 локальных ссылок в 11 новых/изменённых Markdown-файлах; цели и Markdown anchors существуют; `CLAUDE.md -> AGENTS.md` остаётся относительным симлинком |
| PostgreSQL guest integration | 17 passed, включая квоты, изоляцию, cookie/restart и ML concurrency: 3 запроса завершились при общем лимите 2 |
| Миграция и guest contract | 13 passed на отдельной тестовой БД |
| Gateway | 9 passed с настоящим nginx, включая приватность демо и согласованность гостевого режима |
| Backup и переключение режима | 12 passed; включая 4 Linux shell integration с настоящими scripts и fake Docker |
| Web | 104 tests в 23 files passed; API generation, typecheck, lint и build прошли |
| Общая типизация | Mypy: 107 source files без ошибок |
| Canonical contract tooling | validate, generate и TypeScript-проверка прошли |

В первом интеграционном прогоне обнаружено: foreign run ID внутри собственного workspace возвращал `409 report_unavailable`. В `PostgresReviewPlatform.report()` добавлен `get_run()` перед чтением отчёта; повторный guest integration gate прошёл.

Общий backend-прогон: 321 тест, 319 passed и 2 ошибки ожиданий прежнего baseline — проверка защищённого web и whitelist таблиц metadata. Обе проверки исправлены под опциональный гостевой режим и новую таблицу; повторный targeted gate прошёл: 14 passed (guest contract, protected baseline, metadata и backup).

## Ещё не подтверждено

| Gate | Статус |
| --- | --- |
| Повторная проверка двух исправленных backend baseline tests | PASS; 14 targeted tests passed |
| Итоговый общий release gate | Ещё не завершён |
| Production migration, release и HTTPS smoke | Не выполнено в рамках этой записи |

## Границы результата

Cookie действует 30 дней с продлением при использовании; данные после истечения не удаляются. Восстановление доступа после потери cookie отсутствует. Лимиты исходных загрузок и reserve check не являются измерением полного расхода диска. Предметная экспертная оценка, нагрузочная ёмкость сервера и реальные пользовательские результаты в этом срезе не измерены.
