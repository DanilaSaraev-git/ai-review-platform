# Validation: цикл документа

Из корня технического checkout:

1. `uv sync --frozen`; `cd apps/web && npm ci && npm run api:generate`.
2. Поднять отдельный PostgreSQL для тестов и применить Alembic до head. Существующие dev/production БД не использовать.
3. Выполнить domain/contract/HTTP/migration тесты функции и регрессию immutable report, idempotency, guest isolation и locale. Конкретные команды и фактические результаты записать в evidence.md.
4. Web: `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`, `npm run test:e2e` против synthetic MSW.
5. Синтетический live smoke: upload v1 → review → human decision → upload v2 в семью → review → comparison → human fix confirmation → повтор v2 без upload → reopen v1 → PDF.
6. Проверить v1 issue → v2 absent/resolved → v3 returned, ambiguous duplicates, changed profile/context, partial report, concurrent state conflict, baseline frozen, repeated request, foreign guest IDs.
7. PDF: извлечь текст и сверить статусы/счётчики; отрендерить многостраничный кириллический пример в PNG и визуально проверить все страницы.
8. Проверить git diff, ссылки новых документов и `CLAUDE.md -> AGENTS.md`.

Модель и клиентские документы в этих проверках не используются. Визуальный пример — только синтетические данные.
