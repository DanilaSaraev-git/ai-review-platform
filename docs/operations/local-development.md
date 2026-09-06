# Локальная разработка

Основной цикл правок: Vite HMR для web, native `uvicorn --reload` для API и отдельная PostgreSQL в Docker. Запускайте команды из технического checkout `ai-review-platform`; продуктовая база и материалы заказчиков находятся отдельно.

## Запуск и остановка

```sh
cd /path/to/technical-checkout
./dev start
```

После готовности откройте [http://localhost:5173](http://localhost:5173). Команда запуска возвращается в терминал, сервисы продолжают работать в фоне. Повторный `start` показывает существующий стенд.

```sh
./dev status
./dev logs
./dev stop
```

`status` выводит JSON с фазой запуска, ссылкой и каталогом журналов; для работающего стенда добавляет API health и список профилей модели. `logs` показывает последние строки и продолжает чтение через `tail -F`: `Ctrl-C` завершает только просмотр. `stop` дожидается завершения собственных процессов и останавливает свою PostgreSQL, сохраняя данные. Docker/Colima и другие стенды продолжают работать.

## Что нужно перед первым запуском

- `python3` версии 3.10+ для launcher: только стандартная библиотека, POSIX с `waitid`/`WNOWAIT`.
- `uv`: при каждом старте выполняется `uv sync --frozen`; backend использует Python 3.14.7 и версии из `uv.lock`.
- Node.js версии не ниже 22.21.0 и npm. Если frontend dependencies ещё не установлены, выполните из корня `npm --prefix apps/web ci`; при обычных правках повторять установку не требуется.
- Работающий Docker с Compose и выбранным локальным context через Unix socket. Если используете остановленную Colima, сначала выполните `colima start`. Launcher не запускает и не останавливает VM самостоятельно.
- Читаемый credential в `~/.config/ai-analytics-review/huggingface.token`. Значение секрета читает существующий `FileSecretProvider` по `REVIEW_MODEL_CREDENTIAL_PATH`; храните файл приватным и вне Git. Launcher передаёт путь, а не значение токена.

Локальные адреса фиксированы:

| Сервис | Адрес |
| --- | --- |
| Web | `http://localhost:5173` |
| API | `http://127.0.0.1:18000` |
| PostgreSQL | `127.0.0.1:55451` |

При конфликте порта запуск завершится с объяснением; чужие процессы автоматически не останавливаются. Если этот dev-стенд принадлежит другому checkout, управляйте им из того checkout. Удалённый Docker context не поддерживается.

## Правки и модель

Vite применяет изменения web через HMR. API автоматически перезапускается при изменениях в `apps/api/src`, `packages/review-core/src` и `packages/review-runtime/src`. Web обращается к реальному API через Vite `/api` proxy; моки выключены. Docker images приложения при обычной работе не собираются.

Reload может прервать выполняющийся запуск проверки или ход диалога: после восстановления он получает состояние `process_interrupted`. Сохраняйте правки между такими операциями, если нужен непрерывный прогон. Для изменения профиля модели, навыка или runtime-конфигурации выполните `./dev stop`, затем `./dev start`.

Стенд использует существующий [профиль Kimi K2](../../deploy/compose/config/model-profile.huggingface-kimi-k2.json) `kimi-k2-hf-novita`, модель `moonshotai/Kimi-K2-Instruct:novita`, навык `review-data-spec` 1.0.1 и [действующие runtime limits](configuration.md#runtime-limits). Настройки launcher изолированы от экспортированных `REVIEW_*`, `VITE_*` и Compose overrides.

После миграций выполняется начальный `review-cli model-probe`, затем проверка повторяется каждые 60 секунд; срок availability — 300 секунд. Probe не генерирует текст, не вызывает API startup/reconciliation и совместим с работающим API. Ошибка поставщика отражается как `unavailable` и запись журнала, а dev-сервисы продолжают работать. Успешный probe подтверждает доступность endpoint; качество ревью и генерацию он не проверяет.

## Где остаются данные

Приватный каталог `~/.local/state/ai-review-platform/dev` содержит:

- `artifacts/` — сохраняемые документы и артефакты отчётов;
- `launcher.log`, `api.log`, `web.log`, `probe.log` — журналы;
- `control.sock` и lock-файлы — управление собственным экземпляром launcher.

PostgreSQL использует Compose project `review-platform-dev` и volume `review-platform-dev_postgres-data`. `stop` сохраняет volume и каталог artifacts; повторный `start` использует их снова. Не удаляйте volume или приватный каталог, если нужны сохранённые документы и отчёты. Локальные данные и журналы не входят в Git.

## Если запуск не удался

Сначала выполните `./dev status` и `./dev logs`. Проверьте указанную в сообщении зависимость, занятый порт или credential. Если недоступна только модель, смотрите `probe.log`: восстановите сеть или доступ поставщика и дождитесь следующей проверки. Для повторного запуска после изменения конфигурации используйте `stop`/`start`.

## Локальная проверка цикла документа

Feature 009 проверяется в отдельном checkout и Compose project `review-cycle-local`. Локальный адрес — [http://localhost:18109/documents](http://localhost:18109/documents); публикация порта ограничена loopback. База и исходники используют отдельные volumes. Существующие локальные и удалённые экземпляры не изменяются.

Приватный wrapper `~/.local/state/ai-review-platform/document-cycle-local/manage.sh` принимает команды Compose: `ps`, `stop`, `up --detach --build --wait`. Профиль модели и путь к credential берутся из существующей локальной конфигурации Яндекса без копирования секрета в репозиторий. GET-probe проверяет доступность; генерация происходит только при действии пользователя. Для HTTP на loopback используется trusted режим; гостевая изоляция проверяется отдельно интеграционными тестами.

После обновления кода стенд необходимо пересобрать. Остановка сохраняет данные. Результаты приёмки описаны в [SpecKit 009](../../specs/009-document-review-cycle/quickstart.md); production deployment допускается только после отдельной команды пользователя.

## Отдельный локальный стенд DeepSeek

Для локального тестирования 6 сентября 2026 года настроен отдельный Compose project
`review-platform-yandex-local` из checkout с принятым Numbat и правкой языка ответов.
Адрес — [http://localhost:18101/new](http://localhost:18101/new), порт опубликован только
на loopback. Ранее работающий `./dev` другого checkout на 5173 не изменяется.

Приватные настройки и управляющий wrapper находятся вне Git в
`~/.local/state/ai-review-platform/yandex-local`. Профиль и credential Яндекса читаются
из существующего приватного каталога; значения ключей в env и команды не включаются.
Модель — `yandex-deepseek-v4-flash` 1.0.0. Отдельный сервис раз в 60 секунд выполняет
только GET-проверку доступности; генерации выполняются по действиям пользователя.

```sh
sh ~/.local/state/ai-review-platform/yandex-local/manage.sh ps
sh ~/.local/state/ai-review-platform/yandex-local/manage.sh stop
sh ~/.local/state/ai-review-platform/yandex-local/manage.sh up --detach --build --wait
```

Этот стенд использует собранные images: после изменений кода повторите последнюю команду.
Его PostgreSQL и artifacts находятся в отдельных Docker volumes; остановка сохраняет
данные. Серверные документы и отчёты в локальную базу не переносились. Wrapper привязан
к текущему checkout и приватной конфигурации владельца; это локальная настройка машины,
а не переносимый скрипт с встроенными credentials.

Объём и проверки этого режима зафиксированы в [SpecKit 007](../../specs/007-local-dev-loop/spec.md) и [списке задач](../../specs/007-local-dev-loop/tasks.md). Фактические проверки и их границы записаны в [evidence](../../specs/007-local-dev-loop/evidence.md). Production остаётся отдельным стабильным стендом; новая серверная выкладка и повторный release gate не входят в локальный запуск. Серверная эксплуатация описана в [deployment.md](deployment.md).
