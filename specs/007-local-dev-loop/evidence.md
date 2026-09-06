# Evidence: localhost development loop

Дата: 2026-09-06. Срез: [spec.md](spec.md), [plan.md](plan.md), [tasks.md](tasks.md).

## Результат

Локальный стенд запущен и оставлен работающим: [http://localhost:5173](http://localhost:5173).
`./dev start`, `./dev stop`, `./dev status`, `./dev logs` описаны в [руководстве](../../docs/operations/local-development.md).
Web использует Vite HMR, API — native uvicorn reload, PostgreSQL — отдельный Compose project
`review-platform-dev`. Новая серверная выкладка не выполнялась.

## Исходное состояние

- Технический checkout на ветке `codex/mvp-launch-20260905`, исходный HEAD `a395ded`; перед работой Git status чистый.
- Порты 5173, 18000, 55451 не имели listeners. Docker context `colima` использовал локальный Unix socket.
- Уже работали `review-platform-kimi-k2-{api,proxy,postgres}-1` (proxy 18100) и
  `review-platform-004-review-storage-postgres-1` (55447).
- uv 0.11.29, Node v26.5.0, Docker Compose 5.4.0; Python и frontend dependencies установлены.
  `uv sync --frozen` проверил 88 packages. `uv.lock` и `apps/web/package-lock.json` не менялись.
- Во время работы соседняя задача изменила общий checkout: профиль Kimi стал 1.0.1 с output budget 8192.
  Эти правки модели/runtime/tests не входят в срез 007. Localhost проверен с текущим профилем 1.0.1;
  launcher читает существующий профиль из репозитория, а не копирует его.

## Проверки

| Проверка | Наблюдаемый результат |
| --- | --- |
| Startup | `./dev start` возвращает ссылку после готовности; повторный start не создаёт второй комплект процессов |
| PostgreSQL | Только `review-platform-dev-postgres-1`, loopback 55451; migrations до `20260905_0002`; images API/web не собирались |
| API | `/health/live` → alive; `/health/ready` → ready, composition ml, database/business_schema/exact_seed/artifact_store = true |
| Vite → API | `/api/health/ready`, `/api/v1/bootstrap` и каталог моделей отвечают через Vite |
| UI | Отдельный headless Chromium открыл `/new`; синтетический upload завершился, кнопка «Запустить проверку» доступна, page errors = 0; генерация не запускалась |
| Skill | `SkillRegistry.resolve` подтвердил review-data-spec 1.0.1 и canonical digest `93f89a407f19fb3035bee58b8aa355aaf2587bfab7f1bcf4663baad9fbdc71f7` |
| Model | `kimi-k2-hf-novita`, `moonshotai/Kimi-K2-Instruct:novita`, profile version 1.0.1, availability available |
| Periodic probe | Успешные observations 08:16:59, 08:18:06, 08:19:06 UTC; начальная проверка до готовности API, следующие — в работающем стенде, TTL каждого observation 300 s |
| Web HMR | Временная CSS custom property появилась и исчезла после обратной правки; navigation count = 0, JS sentinel в том же document сохранился |
| API reload | Временный комментарий в watched `app.py` вызвал новый server process и readiness без ручного restart; после удаления комментария API снова готов |
| Document persistence | Синтетический `tests/fixtures/ml-integration/primary.md` загружен под именем localhost-persistence.md; content SHA-256 `123f591ccb799f11a12d8a2d83fa7b33f47692c5e8e3283f5e8b379344293d7a` совпал до/после reload и полного stop/start; ID сохранился |
| Stop | API/Vite остановились, PostgreSQL Running=false, все порты 5173/18000/55451 свободны; volume `review-platform-dev_postgres-data` остался |
| Neighbors | После stop/start четыре соседних контейнера сохранили точные container IDs и StartedAt; их данные/процессы не останавливались |
| Focused tests | `uv run --frozen pytest -q tests/test_dev_launcher.py` → 11 passed |
| Static checks | Ruff check и format --check для launcher/tests, `git diff --check`, Markdown links, `CLAUDE.md -> AGENTS.md` — успешно |
| Independent review | Повторный review launcher/tests после исправлений — актуальных blockers нет |

Focused tests используют синтетические subprocess/socket fixtures: изоляция production environment,
занятый порт и prerequisites, повторный/конкурентный старт, stale socket/PID и reused PID,
отказ foreign checkout до stop side effect, очистка потомка после выхода group leader,
частичный startup с сохранением artifacts, адресная остановка PostgreSQL и продолжение
сервисов после initial и двух периодических неуспешных probe.

При первоначальной проверке cleanup обнаружился macOS EPERM для группы с unreaped zombie;
исправление учло это поведение. Окончательный полный stop/start выполнен с исправленной версией:
PostgreSQL действительно остановлена, порты свободны, документ сохранён. Временные CSS/Python
правки полностью удалены. Ранние ошибки остались в приватном launcher.log как история диагностики.

## Хранение и границы проверки

Credential использован через существующий FileSecretProvider; launcher передаёт только путь.
State, журналы и artifacts находятся в приватном каталоге вне Git; PostgreSQL использует постоянный volume.
Отчёты используют существующий durable runtime и тот же постоянный artifact store; новый отчёт
в этом smoke не создавался. Полный генеративный review → dialogue, оценка качества Kimi и серверный
release gate повторно не выполнялись: они не входят в launcher scope; предыдущий серверный результат
находится в [evidence 006](../006-mvp-launch/evidence.md).

Reload может прервать текущую review/dialogue операцию с `process_interrupted`.
Изменения модели, навыка и runtime-конфигурации требуют stop/start; проверка неизменности
конфигурации runtime продолжает действовать. Availability probe подтверждает доступность endpoint,
а не успешность генерации произвольного документа.
