# Evidence: 006 MVP launch

Статус: работа выполняется. Дата: 2026-09-05/06. Baseline: `2a61354`.

## Выполненные подготовительные проверки

- Актуальный technical repo отделён от product knowledge; создана отдельная ветка codex/mvp-launch-20260905 от integrated main.
- Web baseline: typecheck, lint, 94 unit tests, build, 29 Playwright tests — passed (web agent).
- SpecKit: spec/plan/research/data model/contracts/quickstart/tasks созданы; quality checklist 16/16. Это готовность требований, не production release.
- Server read-only audit: Ubuntu24.04, 2 GiB RAM + 2 GiB swap, 40 GiB disk; web/API/Postgres healthy на loopback, нет TLS/gateway/scheduled backups; найден uncommitted deployment overlay.
- Backend diagnosis: default durable fixture выглядит доступной моделью; production должен перейти на explicit unconfigured runtime.

## Оставшиеся проверки

Functional web, production gateway/certificate, backup restore, выпуск и внешний restart будут записаны после выполнения. Реальный endpoint и качество LLM не входят в этот gate.

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
