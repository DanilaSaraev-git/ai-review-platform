# Evidence: 006 MVP launch

Статус: работа выполняется. Дата: 2026-09-05/06. Baseline: `2a61354`.

## Выполненные подготовительные проверки

- Актуальный technical repo отделён от product knowledge; создана отдельная ветка codex/mvp-launch-20260905 от integrated main.
- Web baseline: typecheck, lint, 94 unit tests, build, 29 Playwright tests — passed (web agent).
- SpecKit: spec/plan/research/data model/contracts/quickstart/tasks созданы; quality checklist 16/16. Это готовность требований, не production release.
- Server read-only audit: Ubuntu24.04, 2 GiB RAM + 2 GiB swap, 40 GiB disk; web/API/Postgres healthy на loopback, нет TLS/gateway/scheduled backups; найден uncommitted deployment overlay.
- Backend diagnosis: default durable fixture выглядит доступной моделью; production должен перейти на explicit unconfigured runtime.

## Ещё не проверено

Новый дизайн, functional fixes, production gateway/certificate, backup restore, выпуск и restart будут записаны после выполнения. Реальный endpoint и качество LLM не входят в этот gate.
