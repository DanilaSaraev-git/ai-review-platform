# Implementation Plan: Локальный цикл разработки

**Branch**: `codex/mvp-launch-20260905` | **Date**: 2026-09-06 | **Spec**: [spec.md](spec.md)

**Input**: [Спецификация 007-local-dev-loop](spec.md). Реализация разрешена поручением пользователя; production deployment не входит в срез.

## Summary

Добавить `./dev` с командами `start`, `stop`, `status`, `logs` и небольшой launcher на Python. API работает нативно с `uvicorn --reload`, web — с Vite HMR; Docker/Colima нужен только для отдельной PostgreSQL. Обычные правки не собирают Docker images. Локальные процессы используют существующие runtime adapters, ограничения, Kimi K2 и пакет навыка 1.0.1.

## Technical Context

- **Language/Version**: Python 3.14.7 и Node согласно `apps/web/package.json`; версии сохраняются из `uv.lock` и frontend lock-файла.
- **Primary Dependencies**: существующие uv, uvicorn, Vite, Docker Compose; новых библиотек launcher не требует.
- **Storage**: PostgreSQL 18.6 в Compose project `review-platform-dev`; приватный каталог вне Git для launcher state, журналов и document/report artifacts.
- **Testing**: focused pytest для lifecycle и локальные проверки health, proxy, model availability, reload и сохранности данных.
- **Target Platform**: рабочий macOS localhost с установленными Python/frontend dependencies и Docker/Colima.
- **Project Type**: внутренний launcher технического репозитория.
- **Performance Goals**: автоматическое применение правок; последовательный негенеративный probe каждые 60 секунд при TTL 300 секунд, без нового SLA.
- **Constraints**: bind только loopback; web 5173, API 18000, PostgreSQL 55451 после проверки занятости. Чужие процессы и volumes неприкосновенны; credential только через `FileSecretProvider` / `REVIEW_MODEL_CREDENTIAL_PATH`.
- **Scale/Scope**: один локальный dev-стенд, без изменений HTTP/skill JSON, CI или серверной поставки.

## Constitution Check

Проверено до проектирования и повторно после выбора подхода:

- I–II: канонические HTTP/skill contracts и generated web-клиент остаются существующими; новый публичный DTO не требуется.
- III: focused проверки launcher независимы от внешней генерации; live smoke подтверждает локальное соединение web/API.
- IV: доверенный localhost; секреты читает существующий file provider и не записывает launcher.
- V: опубликованный отчёт не меняется; launcher только управляет окружением.
- VI: только синтетические данные в проверках; реальные локальные артефакты вне Git.
- VII: новая операционная механика в `tools/`, инструкция в `docs/operations/`; файлы заказчиков остаются в продуктовом репозитории.

Нарушений или новых архитектурных исключений нет. Полный серверный release gate уже относится к feature 006 и повторно не требуется.

## Project Structure

### Documentation (this feature)

- `specs/007-local-dev-loop/spec.md`, `plan.md`, `tasks.md`, `checklists/requirements.md` — объём, подход и проверяемые задачи.
- `specs/007-local-dev-loop/evidence.md` — фактические команды, результаты и ограничения после реализации.
- `docs/operations/local-development.md` — короткая инструкция, связанная из `README.md`.

### Source Code (repository root)

- `dev` — исполняемая точка входа.
- `tools/dev.py` — конфигурация, lifecycle и probe loop.
- `tests/test_dev_launcher.py` — проверки рисков управления процессами.
- `deploy/compose/compose.yaml` + `deploy/compose/compose.release.yaml` — существующие сервис postgres, volume и публикация локального порта.
- `apps/web/vite.config.ts` — существующий `/api` proxy через `VITE_API_PROXY_TARGET`.

**Structure Decision**: Внутренний launcher не создаёт новую платформу развёртывания. Отдельные `research.md`, `data-model.md`, `contracts/` и `quickstart.md` не добавляются: решения и служебное состояние описаны ниже, runnable guide находится в существующем разделе operations. Доменных изменений нет.

## Phase 0 — Выбранный подход и основания

| Решение | Основание | Рассмотренная альтернатива |
| --- | --- | --- |
| Native API + web, Docker только для PostgreSQL | Нужны uvicorn reload и Vite HMR; зависимости уже установлены | Полный Compose приложения потребовал бы иной dev-конфигурации и лишней пересборки |
| Существующие Compose YAML, project `review-platform-dev`, только сервис `postgres` | Уже есть volume и loopback port override | Новый Compose файл дублировал бы текущую БД-конфигурацию |
| Существующий `review-cli model-probe` | Код `apps/cli/src/review_cli/commands/model_probe.py` сохраняет observation без `platform.startup` и reconciliation | API startup из timer конфликтовал бы с lifecycle API |
| Внешний Kimi K2 через существующий профиль | `deploy/compose/config/model-profile.huggingface-kimi-k2.json`: `kimi-k2-hf-novita`, TTL 300 секунд | Новая модель/adapter выходит за поручение |
| Приватное состояние и проверка владения процессами | Нужны сохранность данных и сосуществование со старыми стендами | Остановка по одному PID или имени процесса недостаточна |

Неопределённости runtime — свободные порты, Docker readiness и доступность поставщика — проверяются при запуске и в evidence, а не объявляются заранее решёнными.

## Phase 1 — Lifecycle и конфигурация

1. `start` сериализует управляющие команды, сверяет текущее состояние и наличие зависимостей, проверяет loopback порты. Повторный start показывает уже работающий стенд; конфликт не завершает чужой процесс.
2. Выделенный Compose project запускает только PostgreSQL на 55451. Существующий volume сохраняется; launcher не останавливает Docker/Colima целиком.
3. Native environment включает `REVIEW_COMPOSITION=ml`, отдельные namespace/state, PostgreSQL URL на 55451, существующие runtime limits и `review-data-spec` 1.0.1 с проверяемым package digest. Значение credential launcher не читает; передаёт только файловый путь через `REVIEW_MODEL_CREDENTIAL_PATH`.
4. Выполнить существующие миграции, затем первый `review-cli model-probe`. Ошибка поставщика логируется как unavailable и не прерывает запуск dev-сервисов; ошибки обязательной локальной инфраструктуры завершают start с понятным сообщением.
5. Запустить native API на 18000 с `uvicorn review_api.app:app --reload`, наблюдая API и Python packages; Vite — на 5173 с HMR, `VITE_API_BASE_URL=/api`, `VITE_API_PROXY_TARGET=http://127.0.0.1:18000`, моки выключены. Ожидать готовность и только затем показать ссылку.
6. Пока стенд работает, последовательный CLI probe обновляет availability каждые 60 секунд. Он не вызывает API startup/reconciliation и не захватывает owner lock API. Ошибка записывается, следующий цикл продолжается.
7. `stop` завершает собственные probe, Vite и uvicorn процессы с достаточным временем graceful shutdown, останавливает postgres только своего Compose project и сохраняет volume/artifacts. Частичный неуспешный start очищает лишь ресурсы, созданные этим запуском.

**Служебное состояние**: приватный каталог хранит Unix control socket, lock-файлы и журналы; supervisor сообщает свой checkout по socket и проверяет его до stop. PID-файлы не используются. `waitid(...WNOWAIT)` удерживает завершившегося leader до очистки всей его process group, предотвращая повторное использование PID. Управляющие команды защищены от гонок. `status` сообщает фактическую готовность сервисов и состояние модели; `logs` открывает журналы без credentials. State остаётся отдельным от доменных документов и отчётов.

## Verification

- **Focused tests**: повторный start; конфликт порта; stale/reused PID; own-only stop; rollback частичного запуска; сохранение volume/artifacts; ошибка probe не останавливает сервисы. Имитации проверяют границы побочных эффектов и не вызывают реальную генерацию.
- **Live start**: health/ready API и через Vite `/api/health/ready`; реальный bootstrap в браузере без MSW; выбранные профиль Kimi и навык 1.0.1.
- **Availability**: начальная успешная observation и следующая спустя один 60-секундный цикл; отказ поставщика проверяется без реальной генерации.
- **Reload**: обратимая правка web и Python source, наблюдение автоматического обновления и повторная готовность; затем исходное содержимое восстановлено.
- **Persistence/lifecycle**: синтетические данные до и после stop/start; volume и artifact content сохранились. Соседние стенды сравнить с исходной read-only инвентаризацией.
- **Completion**: заполнить evidence наблюдаемыми фактами, отметить выполненные tasks, проверить Markdown-ссылки и `CLAUDE.md -> AGENTS.md`; передать одну команду запуска/остановки и локальную ссылку.

Полный review → dialogue, генеративная оценка Kimi, серверный smoke и release gate в эти проверки не входят. Существующее серверное evidence остаётся в [feature 006](../006-mvp-launch/evidence.md).
