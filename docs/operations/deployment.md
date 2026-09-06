# Выпуск MVP на одном сервере

По умолчанию действует trusted v1: одна небольшая группа работает в одном общем workspace.
Gateway даёт общий допуск, но не разделяет пользователей и компании. Гостевой режим ниже
выделяет посетителю отдельное рабочее пространство по браузерной cookie. Это не корпоративная
авторизация; для отдельной компании нужен отдельный deployment с volumes, секретами и адресом.

## Текущее состояние сервера

На 6 сентября 2026 года `135.106.195.62` работает на Ubuntu 24.04, Docker 29.1.3 и
Compose 2.40.3. В нём 2 GiB RAM, 2 GiB swap и 40 GiB диска. Текущий runtime release —
`398c01983814811de9c4495399e07719e2ed9067`, предыдущий —
`9a4d767a8dcd30469a942d1f39b7f0751d5421a3`. Актуальный release определяется ссылкой
`/opt/ai-review-platform-current` (`readlink -f /opt/ai-review-platform-current`). Сервис доступен по
[HTTPS](https://135.106.195.62) с общим gateway-допуском; PostgreSQL и artifacts постоянны,
внутренний proxy доступен только на `127.0.0.1:8080`. Проверенный legacy rollback target —
`2a613542056dd7b132a077a7c5b0619ff2bb733a`. Полный цикл new→legacy→new и restart прошли
без потери данных. SSH password нельзя отключать, пока отдельный вход
непривилегированного оператора по ключу не проверен в новой сессии.

Включена DeepSeek V4 Flash через Yandex AI Studio: профиль `yandex-deepseek-v4-flash`
1.0.0, навык `review-data-spec` 1.0.1. Негенеративная GET-проверка доступности прошла
`2026-09-06T11:57:41Z`. По прямому запрету пользователя пробные генерации, review,
dialogue и `model-smoke` при подключении не выполнялись. Совместимость фактического ответа
при подключении не проверялась. Позже один пользовательский запуск получил semantic
отказ, следующий завершился с публикацией отчёта; предметное качество не оценивалось.
Текущий release объединяет принятый интерфейс Numbat для рабочего сервиса и деморежима,
авторизацию Яндекса и диагностику. Он сохраняет безопасную причину будущих semantic
отказов в `error.message`, не записывая текст документа или ответа, и отклоняет
незавершённые ответы модели до разбора JSON. После promotion инфраструктурная проверка
gateway/TLS/origin/private services/model mode прошла. Новый дизайн обеих страниц
проверен в браузере через приватный SSH-туннель к серверному proxy; публичный HTTPS
отдельно подтвердил ожидаемый gateway 401. [Настройки Яндекса](configuration.md#deepseek-через-yandex-ai-studio)
и порядок отката модели ниже описывают текущий контур.

Исторически, до Яндекса, работала Kimi K2 через Hugging Face Router/Novita: профиль
`kimi-k2-hf-novita` 1.0.0, позднее 1.0.1 с output budget 8192, модель
`moonshotai/Kimi-K2-Instruct:novita`. Для версии 1.0.0 реальный
синтетический HTTP smoke прошёл review и dialogue; результаты предметной оценки качества
из этого не следуют и на DeepSeek не переносятся. До отдельного деморежима рабочим release
был `5a3dae85d5dc6f3d5538969b3ddee810de5c5b02`.

При отключении модели health остаётся готов, каталог показывает `model-not-configured`
как `unavailable`, а запуск review возвращает `model_unavailable`. Synthetic review
в production не подставляется.

## Собрать и установить неизменяемый release

Собирать архив нужно из чистого commit, прошедшего backend, web и Compose проверки:

```sh
release_archive=/private/tmp/ai-review-release.tar.gz
tools/ops/package-release.sh "$release_archive"
scp "$release_archive" root@135.106.195.62:/root/ai-review-release.tar.gz
scp tools/ops/common.sh tools/ops/install-release.sh root@135.106.195.62:/root/
```

На сервере перед первым promotion установить release, создать приватную конфигурацию и
получить короткоживущий публично доверенный сертификат Let's Encrypt для IP:

```sh
commit=FULL_GIT_SHA_FROM_PACKAGE
bash /root/install-release.sh /root/ai-review-release.tar.gz "$commit"
target="/opt/ai-review-releases/$commit"
"$target/tools/ops/bootstrap-state.sh" 135.106.195.62
"$target/tools/ops/bootstrap-gateway.sh"
```

`bootstrap-state.sh` генерирует пароль PostgreSQL и сохраняет конфигурацию с mode `0600` в
`/opt/ai-review-state/review.env`. `bootstrap-gateway.sh` сначала проверяет выдачу ACME
challenge через port 80, затем использует Certbot 5.8 и профиль `shortlived`. Пароль общего
gateway и htpasswd лежат только в `/opt/ai-review-state/secrets`. Закрытый ключ сертификата
остаётся в `/opt/ai-review-state/letsencrypt`. Значения секретов не передают в аргументах
Compose и не записывают в журналы.

Для IP certificates Let's Encrypt требует короткоживущий профиль; срок таких сертификатов
составляет 160 часов. Поддержка IP certificates и профиль Certbot описаны в официальных
объявлениях [Let's Encrypt](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability.html)
и [Certbot](https://letsencrypt.org/2026/03/11/shorter-certs-certbot).

При переходе с существующей установки bootstrap сохраняет её текущий внутренний пароль
PostgreSQL в новом private env; смена credentials не совмещается с выпуском приложения. Он
также сохраняет `legacy.env` со всеми фактическими прежними `REVIEW_*` settings, включая
display labels и composition/model/dialogue IDs. Поэтому старый runtime при откате получает
ровно тот seed, с которым уже работал. Оба файла имеют mode `0600`.
Promotion сам создаёт predeploy backup, собирает version-tagged images, применяет только
forward migrations, меняет display labels без смены
ID, поднимает сервисы и выполняет внешний probe. Ссылки current/previous меняются только
после успешной проверки:

```sh
"$target/tools/ops/promote-release.sh" "$target"
"$target/tools/ops/install-timers.sh"
```

Для защиты от смены текущего release между подготовкой и запуском можно передать
`REVIEW_EXPECTED_CURRENT_COMMIT=FULL_EXPECTED_CURRENT_SHA` в окружении `promote-release.sh`.
Скрипт сверяет полный SHA под общим release lock до backup и сборки; при расхождении
останавливается, чтобы оператор проверил новое состояние.

При первом переходе на гостевую схему `20260906_0003` автоматический откат старого кода
после начала migration запрещён: команда миграции могла успеть зафиксировать изменения
даже при ошибке. Если promotion после этой границы не завершился, gateway останавливается,
а прежний release, ожидающий `0002`, не запускается. Исправьте новый release и повторите
его promotion; после успешной миграции trusted режим включайте на этом же release через
`REVIEW_GUEST_ACCESS=false`. Таблицу сессий и схему назад не откатывайте. Для совместимых
releases обычный автоматический откат сохраняется.

Для первой установки предыдущий legacy release остаётся пригоден для отката. Такой откат
останавливает новый public gateway, возвращает loopback-only proxy и останавливает новые
timers, отсутствующие в старом release. После повторного promotion запустите
`install-timers.sh` снова. Схема БД назад не мигрирует, volumes не удаляются.

## Проверка после выпуска

```sh
current=/opt/ai-review-platform-current
"$current/tools/ops/verify-deployment.sh"
docker compose \
  --project-name review-platform-mvp \
  --env-file /opt/ai-review-state/review.env \
  -f "$current/deploy/compose/compose.yaml" \
  -f "$current/deploy/compose/compose.production.yaml" ps
systemctl list-timers --all \
  review-backup.timer review-cert-renew.timer review-model-probe.timer --no-pager
```

Обязательные результаты: `http://135.106.195.62` отвечает redirect, HTTPS без credentials
отвечает 401, HTTPS с credentials открывает UI и API, cross-origin mutation отвечает 403,
сертификат проходит системную проверку доверия, а ports PostgreSQL/API не опубликованы.
Gateway ограничивает размер тела 52 MiB, частоту и число соединений; Docker хранит не более
трёх лог-файлов по 10 MiB на контейнер. HTTP используется только для ACME и redirect — пароль
и документы по plaintext не принимаются.

После проверки credentials передают пользователям через выбранный владельцем защищённый
канал. Не вставляйте их в issue, chat transcript или репозиторий.

## Вход без регистрации

Гостевой доступ включается значением `REVIEW_GUEST_ACCESS=true` в приватном
`/opt/ai-review-state/review.env`. Допустимы только `true` и `false`; отсутствие настройки
означает `false`. Установите release с поддержкой гостевых сессий, измените настройку и
выполните обычный `promote-release.sh`: он применит миграцию и пересоздаст API вместе с
gateway. Не открывайте основной маршрут отдельной ручной правкой `auth_basic`.

При `true` основное приложение открывается по HTTPS без пароля и кода. Первый bootstrap
создаёт гостевую сессию и выдаёт cookie `review_guest` (`HttpOnly`, `Secure`, `SameSite=Lax`,
`Path=/`, срок 30 дней). Повторный вход из этого браузера возвращает то же рабочее пространство.
Документы и результаты хранятся в постоянных PostgreSQL/artifact volumes и входят в обычную
резервную копию. Сессии также сохраняются в PostgreSQL, поэтому перезапуск API не меняет
доступ. Очистка cookie, приватный режим, другой браузер или истечение сессии создают новый
доступ; автоматического восстановления прежнего доступа без cookie нет.

API требует действительную cookie для `/v1/*`, кроме bootstrap, и проверяет принадлежность
рабочего пространства. Наличие Basic credentials не даёт доступа к чужому гостю или прежнему
общему workspace. Пути `/demo` и все `/demo/*`, включая данные и browser worker, всегда
остаются за прежним Basic-допуском. Гостевая cookie этот допуск не заменяет.

Один Compose-параметр передаётся и API, и gateway. Перед проксированием в гостевом режиме
gateway проверяет внутренний `/health/guest-access`: только API с включённой изоляцией
отвечает `204`. При старом API, рассинхроне флагов или ошибке проверки gateway закрывает
доступ. Неизвестное значение флага останавливает запуск обоих сервисов. Внутренний proxy
остаётся доступен только на loopback; PostgreSQL и API host ports не публикуются.

`verify-deployment.sh` автоматически проверяет выбранный режим. В гостевом режиме он
проверяет публичный UI, атрибуты cookie, возвращение в ту же сессию, разные workspace двух
гостей, запрет запросов без cookie и запросов к чужому workspace через оба API-префикса,
а также сохранение Basic на `/demo`. Проверка создаёт две пустые гостевые сессии; документы
не загружает и платных запросов к модели не делает. Дополнительно перед приглашением
посетителей проверьте синтетическую загрузку и возвращение к ней после рестарта приложения.

Для возврата к общему trusted workspace установите `REVIEW_GUEST_ACCESS=false` и выполните
смену режима на том же новом release. После миграции `20260906_0003` старые releases,
ожидающие ровно `20260905_0002`, не проходят readiness. Простая установка флага `false`
не делает их совместимыми с новой схемой. Безопасный операционный откат — отключение
гостевого доступа на release с поддержкой `0003`, без отката приложения или БД:

```sh
/opt/ai-review-platform-current/tools/ops/guest-access-mode.sh false
```

Скрипт берёт общий lock, проверяет поддержку `0003`, останавливает gateway, атомарно
обновляет private env и пересоздаёт API, proxy и gateway из образов текущего release.
После этого запускается `verify-deployment.sh` без вызова модели. Если проверка или
пересоздание не удались, gateway остаётся остановленным до исправления оператором.
Миграции, таблица гостевых сессий и volumes не изменяются; соответствие cookie гостю
сохраняется. Для повторного включения выполните ту же команду с `true`. Гостевые данные
при выключении не удаляются и не становятся доступны через trusted workspace.

Ограничения загрузки задаются в том же private env и передаются API через Compose:
`REVIEW_GUEST_STORAGE_BYTES=209715200` (200 MiB на гостя),
`REVIEW_GUEST_TOTAL_STORAGE_BYTES=1073741824` (1 GiB на всех гостей),
`REVIEW_GUEST_DOCUMENT_LIMIT=20` и `REVIEW_GUEST_DISK_RESERVE_BYTES=3221225472`
(3 GiB свободного места). Изменения вступают в силу после пересоздания API, например
той же командой смены режима с текущим значением флага.

В проверке 6 сентября VPN-маршрут `utun7` на Mac давал intermittent TLS handshake failures.
Тот же адрес через прямой интерфейс `en0` прошёл 10/10 и независимо 12/12 запросов без
повторов и с системной проверкой сертификата. Если на этом Mac сервис не открывается,
проверьте прямой маршрут или исключение адреса из VPN. Сертификат обходить не нужно;
настройки VPN пользователя при выпуске не менялись.

На проверенном release активны timers: backup ежедневно в 00:30 UTC (случайная задержка
до 30 минут), certificate renewal в 02:00 и 14:00 UTC (до 20 минут), model probe раз в минуту.
Сертификат проверен до 12 сентября 2026 12:52:08 UTC; staging renewal dry-run прошёл.
Срок короткий, поэтому renewal timer должен оставаться активным. Финальная копия
`20260905T224545Z` прошла isolated restore и скопирована с VPS в приватное хранилище владельца;
контрольные суммы проверены. Полные результаты находятся в
[evidence выпуска](../../specs/006-mvp-launch/evidence.md).

## Копия, восстановление и откат

Ежедневный timer вызывает согласованную копию PostgreSQL и artifact volume. API и proxy на
короткое время останавливаются, затем возвращаются в исходное состояние даже при ошибке.
Набор `/opt/ai-review-backups/YYYYMMDDTHHMMSSZ` содержит dump, archive и manifest с SHA-256,
release commit, количествами и логическим fingerprint документов, отчётов, диалогов и решений.
Хранятся последние 14 наборов.

Перед записью новой полной копии `backup.sh` проверяет свободное место на файловой системе
каталога копий. Требуется двойной суммарный размер PostgreSQL и несжатых artifacts, ещё
64 MiB на служебные данные и резерв 2 GiB. Резерв задаётся положительным
`REVIEW_BACKUP_MIN_FREE_BYTES` в private env; проверку выполняет
[`backup_space.py`](../../tools/ops/backup_space.py). При нехватке места команда завершается
с ошибкой и возобновляет остановленные сервисы, не создавая неполный backup set и не удаляя
прежние копии. Retention удаляет старые наборы только после успешного создания нового.
Если место заканчивается, новые копии перестают создаваться до действий оператора;
автоматическая чистка документов и прежних копий ради освобождения места не выполняется.

```sh
backup_set="$(/opt/ai-review-platform-current/tools/ops/backup.sh)"
/opt/ai-review-platform-current/tools/ops/restore-drill.sh "$backup_set"
```

Restore drill не касается рабочего PostgreSQL: он создаёт временные container/volume,
проверяет manifest, восстанавливает dump, сравнивает логический fingerprint и сверяет каждый
artifact с DB по пути, размеру и SHA-256. Временное состояние удаляется после проверки.

Перед приглашением пользователей и после каждого существенного выпуска один завершённый
backup set нужно скопировать с VPS в приватный каталог владельца с mode `0700/0600`, проверить
локальный SHA-256 и не коммитить. Постоянное внешнее хранилище и его retention пока не выбраны;
локальные копии на том же VPS не защищают от потери всего сервера.

Следующие исторические команды отката применимы только к совместимым со схемой releases.
После миграции `20260906_0003` нельзя возвращать release, readiness которого ожидает
`20260905_0002`. Используйте смену режима на новом release, описанную выше; не удаляйте
таблицу гостевых сессий и не выполняйте downgrade ради readiness старой версии.

Откат приложения на совместимый установленный commit. Для Yandex-выпуска до миграции
`20260906_0003` сначала выполните описанный ниже возврат к прежней модели:

```sh
/opt/ai-review-platform-current/tools/ops/rollback-release.sh FULL_PREVIOUS_GIT_SHA
```

Скрипт сначала создаёт новую копию, запускает проверенный target без пересборки и только затем
переключает symlinks. Для production release сохраняется текущий выбор model mode. Откат не
понижает schema и не восстанавливает данные; восстановление данных — отдельное осознанное
действие после разбора причины.

Исторический порядок для установки до миграции `20260906_0003`: перед откатом
Yandex-выпуска на `33d94299150259a853bf47566fb77c59655ac4b8` сначала верните прежнюю
модель, поскольку старый release не поддерживает авторизацию Яндекса. После `0003`
этот откат приложения неприменим, даже после возврата прежней модели.
Приватная копия `/opt/ai-review-state/model-backups/20260906T115706Z-before-yandex`
содержит `model-profile.json`, `model-api-key` и `model.env` с mode `0600`. Выполняйте команды
по очереди и продолжайте только после успешного завершения предыдущей:

```sh
current=/opt/ai-review-platform-current
model_backup=/opt/ai-review-state/model-backups/20260906T115706Z-before-yandex
"$current/tools/ops/model-disable.sh"
"$current/tools/ops/model-configure.sh" \
  "$model_backup/model-profile.json" \
  "$model_backup/model-api-key"
"$current/tools/ops/model-enable.sh"
"$current/tools/ops/rollback-release.sh" 33d94299150259a853bf47566fb77c59655ac4b8
```

`model-configure.sh` восстановит профиль и credential через штатную установку и пересоздаст
`model.env`; копировать сохранённый env поверх работающей конфигурации не нужно. Enable
проверит только доступность прежней модели и инфраструктуру, без генерации. При ошибке
configure или enable не откатывайте приложение с профилем Яндекса. Секрет из backup не
выводите и не передавайте в аргументах; в командах используются только пути к файлам.

Исторический порядок отката Kimi-выпуска на `c61434de2ecba31e4bcd6d24aa045cd624bc64bd`:
сначала успешно выполните `model-disable.sh`, затем `rollback-release.sh` с этим полным SHA. Эта предыдущая
версия работает в unconfigured режиме, но ещё содержит конфликт legacy/canonical identity
навыка 1.0.0. Перед повторным включением Kimi верните исправленный release с навыком 1.0.1.
Исторические версии навыка и результаты проверок при таком откате сохраняются.

## Подключить модель

Для текущей DeepSeek V4 Flash через Яндекс используйте
[инструкцию настройки](configuration.md#deepseek-через-yandex-ai-studio) и
[`model-profile.yandex-deepseek.json`](../../deploy/compose/config/model-profile.yandex-deepseek.json).
Для прежней Kimi K2 сохранён готовый
[`model-profile.huggingface-kimi-k2.json`](../../deploy/compose/config/model-profile.huggingface-kimi-k2.json)
с Hugging Face Router и Novita. Для другого endpoint создайте профиль из
`deploy/compose/config/model-profile.external.example.json`, заменив
synthetic ID/provider/model, оба точных HTTPS URL, limits и capabilities. Профиль проходит
canonical `ModelProfile` validation внутри version-tagged app image. Скрипт не вызывает
поставщика и проверяет, что непривилегированный runtime читает root-owned файлы:

```sh
current=/opt/ai-review-platform-current
"$current/tools/ops/model-configure.sh" \
  /root/model-profile.production.json \
  /root/model-api-key
"$current/tools/ops/model-enable.sh"
```

Для замены профиля или ротации ключа сначала выполните `model-disable.sh`, затем повторите
`model-configure.sh` и `model-enable.sh`. Configurator отказывается менять файлы работающей
модели, чтобы timer и API не увидели разные версии profile/credential.

Для подключения Яндекса 2026-09-06 пользователь прямо запретил пробные генерации:
после enable не запускайте `model-smoke`, тестовый review или dialogue.
Отдельный compatibility smoke из [configuration.md](configuration.md) возможен по новому
поручению пользователя. Только его успешный результат подтверждает совместимость endpoint;
readiness и config validation не выполняют платный запрос.
Вернуться в честный unavailable mode можно без удаления настроек:

```sh
/opt/ai-review-platform-current/tools/ops/model-disable.sh
```

`model-enable.sh` выполняет один объявленный негенеративный probe и сохраняет observation; при
его ошибке возвращает unconfigured mode. После успешного enable timer обновляет observation
раз в минуту, раньше его пятиминутного TTL. Без marker timer завершается без сетевого запроса.
Model files и marker находятся вне release, поэтому последующие promotion и rollback сохраняют
выбранный режим. Реальный API key остаётся Docker secret file и не попадает в JSON profile.

## Отдельный демонстрационный разбор

Путь `/demo/new` открывает автономный браузерный сценарий с заранее подготовленным
разбором. Основное приложение и настройки внешней модели продолжают работать в своём
режиме. Демонстрация не вызывает модель и не отправляет выбранный файл в API: выбор
любого поддерживаемого файла открывает один и тот же явно обозначенный пример.
Диалог воспроизводит подготовленный ответ по выбранному замечанию; решения хранятся
только в текущей вкладке браузера и не попадают в рабочие отчёты.

Код деморежима входит в web image, а содержимое кейса подключается отдельно, только
при запуске. Каталог `REVIEW_DEMO_DATA_DIR` (по умолчанию `/opt/ai-review-state/demo`)
содержит `demo.json` и исходный `document.pdf`. Он подключён read-only и доступен через
тот же защищённый gateway по `/demo/data/`. Не добавляйте материалы заказчика в Git,
Docker image, synthetic fixtures или архив release. Если пакет отсутствует или не
подходит по формату, деморежим показывает ошибку вместо случайного тестового отчёта.

`demo.json` использует `schemaVersion: 1`, канонические DTO `document`, `report`,
необязательный `bootstrap` и словарь `dialogues` с ключами из `report.findings[].id`.
Первый ход каждого диалога содержит подготовленный ответ. Для синтетических текстовых
примеров вместо PDF допускается поле `documentText`. Привязки отчёта должны ссылаться
на исходный документ и точные страницы/цитаты. В provenance указывается подготовленное
демо, расход модельных токенов не выдумывается; ограничения сохраняют статус экспертной
проверки и отличают гипотезу замечания от подтверждённой ошибки.

Проверки выпуска: `/demo/new` и прямая ссылка на замечание открываются после обновления;
загрузка произвольного документа приводит к подготовленному отчёту; PDF открывается на
странице привязки; тестовый диалог и решение работают; `/demo/api/v1/bootstrap` без
активного browser worker возвращает 503. В Network не должно быть вызовов основного
`/api/` или модельного endpoint. HTTPS без gateway credentials по-прежнему возвращает
401, в том числе для `/demo/data/demo.json` и `/demo/data/document.pdf`.
