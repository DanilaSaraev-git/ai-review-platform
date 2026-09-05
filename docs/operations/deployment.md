# Выпуск MVP на одном сервере

Инструкция относится к trusted v1: одна небольшая группа работает в одном общем workspace.
Gateway даёт общий допуск, но не разделяет пользователей и компании. Для другой компании
нужен отдельный deployment с отдельными volumes, секретами и адресом.

## Проверенный исходный сервер

На 6 сентября 2026 года `135.106.195.62` работает на Ubuntu 24.04, Docker 29.1.3 и
Compose 2.40.3. В нём 2 GiB RAM, 2 GiB swap и 40 GiB диска. Текущая ссылка
`/opt/ai-review-platform-current` указывает на release `2a613542…`; PostgreSQL и artifacts
постоянны, proxy доступен только на `127.0.0.1:8080`. До этого выпуска публичного TLS,
gateway и регулярной копии не было. SSH password нельзя отключать, пока отдельный вход
непривилегированного оператора по ключу не проверен в новой сессии.

Новые release не используют synthetic review в production. Без подключённой модели health
готов, каталог показывает `model-not-configured` как `unavailable`, а запуск review возвращает
`model_unavailable`. Это ожидаемое состояние до выбора поставщика.

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
также сохраняет `legacy.env` с прежними composition/model/dialogue IDs, чтобы старый runtime
при откате не пытался прочитать новые immutable seed IDs. Оба файла имеют mode `0600`.
Promotion сам создаёт predeploy backup, собирает version-tagged images, применяет только
forward migrations, меняет display labels без смены
ID, поднимает сервисы и выполняет внешний probe. Ссылки current/previous меняются только
после успешной проверки:

```sh
"$target/tools/ops/promote-release.sh" "$target"
"$target/tools/ops/install-timers.sh"
```

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

## Копия, восстановление и откат

Ежедневный timer вызывает согласованную копию PostgreSQL и artifact volume. API и proxy на
короткое время останавливаются, затем возвращаются в исходное состояние даже при ошибке.
Набор `/opt/ai-review-backups/YYYYMMDDTHHMMSSZ` содержит dump, archive и manifest с SHA-256,
release commit, количествами и логическим fingerprint документов, отчётов, диалогов и решений.
Хранятся последние 14 наборов.

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

Откат приложения на установленный commit:

```sh
/opt/ai-review-platform-current/tools/ops/rollback-release.sh FULL_PREVIOUS_GIT_SHA
```

Скрипт сначала создаёт новую копию, запускает проверенный target без пересборки и только затем
переключает symlinks. Для production release сохраняется текущий выбор model mode. Откат не
понижает schema и не восстанавливает данные; восстановление данных — отдельное осознанное
действие после разбора причины.

## Подключить модель

Создайте профиль из `deploy/compose/config/model-profile.external.example.json`, заменив
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

После enable выполните отдельный compatibility smoke из
[configuration.md](configuration.md) на синтетическом документе. Только его успешный результат
подтверждает совместимость endpoint; readiness и config validation не выполняют платный запрос.
Вернуться в честный unavailable mode можно без удаления настроек:

```sh
/opt/ai-review-platform-current/tools/ops/model-disable.sh
```

`model-enable.sh` выполняет один объявленный негенеративный probe и сохраняет observation; при
его ошибке возвращает unconfigured mode. После успешного enable timer обновляет observation
раз в минуту, раньше его пятиминутного TTL. Без marker timer завершается без сетевого запроса.
Model files и marker находятся вне release, поэтому последующие promotion и rollback сохраняют
выбранный режим. Реальный API key остаётся Docker secret file и не попадает в JSON profile.
