# Tasks: Версии документа, цикл ревью и PDF

**Input**: [spec](spec.md), [plan](plan.md), [data model](data-model.md), [interfaces](contracts/README.md).
**Tests**: Required by acceptance criteria. Write scenario tests before corresponding behavior.

## Phase 1: Setup

- [x] T001 Integrate current design and guest baseline in this worktree; verify merge-only regression in `tests/integration/test_ml_review_http.py`.
- [x] T002 Complete SpecKit specification, clarification and reviewed quality checklist in `specs/009-document-review-cycle/`.

## Phase 2: Foundational contracts

- [ ] T003 Add compatible cycle/family/PDF resources, examples and changelog in `contracts/review-platform/v1/`; regenerate guest/static variants through `tools/contracts/` and validate compatibility.
- [ ] T004 Add storage migration and metadata for families, version membership and cycle snapshots in `packages/review-runtime/migrations/versions/` and `packages/review-runtime/src/review_runtime/postgres/models/__init__.py`.

## Phase 3: US1 — Повторить проверку

**Independent test**: Repeat completed/failed run with saved document and editable parameters; previous result unchanged.

- [ ] T005 [P] [US1] Add repeat entry/prepopulation with a fresh run request in `apps/web/src/features/new-review/` and entry actions in `apps/web/src/features/review-run/`.
- [ ] T006 [P] [US1] Verify repeat/idempotency and frozen comparison baseline through `tests/integration/test_document_cycle.py` and both platform adapters.

## Phase 4: US2 — Версии

**Independent test**: One family, two versions, three runs; old links and quotas remain valid.

- [ ] T007 [US2] Implement family/version storage, legacy backfill and HTTP actions in `packages/review-runtime/src/review_runtime/postgres/`, `packages/review-core/src/review_core/application/platform.py` and `apps/api/src/review_api/routes/`.
- [ ] T008 [P] [US2] Implement document list/history/version upload using generated client in `apps/web/src/features/document-cycle/` and connect existing routes.
- [ ] T009 [US2] Test upload concurrency, quotas, guest isolation and historical data preservation in `tests/integration/test_document_cycle.py` and `tests/migration/`.

## Phase 5: US3 — Замечания между проверками

**Independent test**: unchanged/changed/new/absent/ambiguous and v1→v2 resolved absent→v3 reappeared; manual corrections and retry preserve history.

- [ ] T010 [P] [US3] Test and implement pure conservative matching in `packages/review-core/src/review_core/application/review_cycle.py` and `packages/review-core/tests/test_review_cycle.py`.
- [ ] T011 [US3] Persist lineage, previous decision snapshots, manual links and resolution history in `packages/review-runtime/src/review_runtime/postgres/`; expose revision-checked routes in `apps/api/src/review_api/routes/`.
- [ ] T012 [P] [US3] Implement comparison, former decisions, manual linking and fix confirmation UI in `apps/web/src/features/document-cycle/` with MSW scenarios.
- [ ] T013 [US3] Cover partial/changed context, non-destructive retry and concurrent revision conflicts in `tests/integration/test_document_cycle.py`.

## Phase 6: US4 — PDF

**Independent test**: Download a coherent, complete and readable PDF of selected run with current decisions.

- [ ] T014 [P] [US4] Test and implement PDF renderer and bundled licensed Cyrillic font in `packages/review-runtime/src/review_runtime/report_export.py`; lock dependency in `packages/review-runtime/pyproject.toml` and `uv.lock`.
- [ ] T015 [US4] Build coherent export snapshot and protected attachment endpoint in `packages/review-runtime/src/review_runtime/postgres/` and `apps/api/src/review_api/routes/`.
- [ ] T016 [P] [US4] Add PDF download UI to `apps/web/src/features/review-report/`; verify network/export errors and selected-run semantics.
- [ ] T017 [US4] Extract and visually render synthetic multi-page Cyrillic PDF; test snapshot consistency and immutable ETag in `packages/review-runtime/tests/` and `tests/integration/test_document_cycle.py`.

## Phase 7: Verification

- [ ] T018 Run relevant backend/contract/migration and web gates, plus combined synthetic smoke in `apps/web/e2e/` and `tests/e2e/`; record actual evidence in `specs/009-document-review-cycle/evidence.md`.
- [ ] T019 Independently review implementation against spec, resolve findings, update `README.md`, domain/operations docs and product decision references; verify Markdown links and symlink.

## Dependencies & Execution Order

T001–T003 precede behavior work; T004 precedes persistent integration. US1 can be verified independently. US2 gives family membership used by US3; US4 exports any existing result and adds cycle detail when available. T010 and T014 are pure modules and run in parallel with T007/T011 and web mock work. T018–T019 follow all stories.

## Parallel Execution

- Backend owner: T004, T006, T007, T009, T011, T013, T015.
- Web owner: T005, T008, T012, T016.
- Root: T010, T014, T017, integration coordination and evidence.
- Contract owner: T003, followed by independent review.

## Implementation Strategy

Contract commit first, then independent backend and web work against that contract. Synthetic tests precede behavior. Do not run customer documents or paid model calls. Keep production unchanged; prepare a reviewable branch with all four stories.
