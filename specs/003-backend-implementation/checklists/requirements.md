# Specification Quality Checklist: локальный restart-safe backend MVP

**Purpose**: проверить rebaseline feature 003 перед реализацией
**Updated**: 2026-09-05
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] Feature 003 отделён от feature 002 и не меняет canonical public v1.
- [x] Техническая поставка не представлена как продуктовая или пилотная валидация.
- [x] Локальный пользовательский flow и операторский restart описаны наблюдаемыми сценариями.
- [x] Все обязательные разделы заполнены, `NEEDS CLARIFICATION` отсутствует.

## Requirement Completeness

- [x] Все 20 Functional Requirements проверяемы и используют однозначные MUST/MUST NOT/MAY.
- [x] Все 8 Success Criteria имеют воспроизводимое evidence.
- [x] User stories содержат independent tests и acceptance scenarios.
- [x] Exact fixture и arbitrary deterministic partial behavior разделены.
- [x] Нормализованная persistence, canonical bytes и mutable human state разделены.
- [x] Single-process/single-replica и sequential-idempotency ограничения названы явно.
- [x] Startup order, readiness checks, volume ownership и loopback boundary определены.
- [x] Worker/outbox/leases/recovery и public ingress явно отложены.
- [x] Quickstart, restart comparison, persistent operator shutdown и явно разрушительный project-scoped reset входят в Definition of Done.

## Scope Safety

- [x] `apps/web/`, `client-materials/`, feature 001, feature 002 и canonical public v1 исключены из изменений.
- [x] Mandatory path не требует API key, egress или model download.
- [x] Optional local model не является gate.
- [x] Deferred production work сохранён отдельным backlog и не заявлен готовым.
- [x] Тестовые suites и active task completion являются явными release gates.

## Notes

- Checklist оценивает качество требований, а не реализацию и не качество AI-замечаний.
- `AGENTS.md` остаётся единственным источником общих project instructions.
