# Research and decisions: 006

Дата: 2026-09-05/06. Основание: прямое поручение пользователя и read-only аудит baseline `2a61354` и имеющегося сервера.

## R-01 — Развивать существующий стек

**Decision**: сохранить React/Orval/FastAPI/PostgreSQL и public v1.
**Rationale**: интегрированы backend, LLM runtime и web005; web baseline проходит 94 unit и 29 Playwright tests. Пробелы находятся в композиции UX и production setup.
**Alternatives considered**: переписывание UI или backend увеличивает риск и не нужно для MVP.
**Sources**: root AGENTS, apps/web/package.json, specs003/004/005, baseline tests.

## R-02 — Классический стиль и постоянный документ

**Decision**: светлая строгая рабочая поверхность, бордовая навигация, точечный красный, стабильный документ и правая панель. Metadata раскрываются по запросу. Неработающие controls удаляются.
**Rationale**: пользователь уточнил Jira-classic с современными деталями и дорогим видом; текущий report/finding route теряет постоянный документ и содержит лишний текст.
**Alternatives considered**: только цветовая перекраска недостаточна; большие декоративные карточки расходятся с запросом.
**Sources**: поручение пользователя 2026-09-05/06; apps/web/src/features/review-report; визуальный макет в продуктовом репозитории. Клиентские материалы макета не копируются.

## R-03 — Honest unconfigured runtime

**Decision**: production composition без модели хранит документы, но показывает model unavailable и не запускает synthetic review. Offline fixture mode сохраняется для тестов.
**Rationale**: текущий durable default публикует доступный deterministic profile, который может создать видимость смыслового AI-ревью.
**Alternatives considered**: оставлять fixture как рабочий fallback нельзя; реальный provider пользователь ещё не выбрал.
**Sources**: deploy/compose/compose.yaml, runtime configuration/seed, audit backend agent.

## R-04 — Доверенный gateway на существующем VPS

**Decision**: TLS + gateway admission перед всеми маршрутами, single workspace. PostgreSQL/API остаются внутренними. Проверить публичный IP certificate с автоматическим renewal.
**Rationale**: существующий service на loopback, TLS отсутствует; accounts противоречат trusted v1. Домен не выбран.
**Alternatives considered**: plain HTTP Basic недопустим для документов/пароля; self-signed сертификат не считаем публично готовым; отдельный SaaS auth/tenancy выходит за MVP.
**Sources**: server read-only audit 2026-09-05/06; актуальные официальные источники сертификата и результаты issuance записывает deployment owner в ops evidence.

## R-05 — Версии и согласованные копии

**Decision**: сохранять releases и предыдущую версию; DB+artifact backup с quiescence/consistency, schedule/retention, isolated restore drill.
**Rationale**: серверный web overlay сейчас вне Git; обнаружен только ручной backup без расписания. Rollback кода не равен rollback данных.
**Alternatives considered**: in-place overwrite и отдельный несогласованный dump не дают проверяемого восстановления.
**Sources**: server audit, текущий deployment layout и postgres/artifact runtime.

## Неопределённость

Нет неразрешённого выбора архитектуры. Реальные credentials/модель и субъективная приёмка дизайна остаются внешними зависимостями. Сертификат, backup drill и release проверяются исполнением; не объявляются заранее успешными.
