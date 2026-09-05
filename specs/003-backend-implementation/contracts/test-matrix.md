# MVP requirements-to-test matrix

| Requirement | Active tasks | Primary evidence |
| --- | --- | --- |
| FR-001 | T002, T018, T023, T030 | `tests/contract/` public v1 compatibility, including required headers and key bounds |
| FR-002, FR-007 | T004, T006–T010 | clean Alembic + PostgreSQL flow |
| FR-003–FR-006 | T005, T009–T010, T029 | deterministic HTTP flows plus pre-publication schema/semantic validation |
| FR-008, FR-010 | T012–T014 | dialogue/decision immutability and restart E2E |
| FR-009 | T009, T012–T013 | sequential idempotency tests |
| FR-011, FR-014 | T006–T007, T020–T021 | exact seed/resource/readiness tests |
| FR-012, FR-015, FR-016, FR-018 | T011, T015–T016 | clean Compose topology and health |
| FR-013 | T008, T011, T025 | default request path creates no queue, execution-attempt or lease records |
| FR-017 | T017–T018 | deterministic no-egress gate |
| FR-019 | T014–T016, T018, T024, T032 | host-toolchain-free Make targets, persistent operator shutdown, isolated destructive reset and clean-checkout quickstart |
| FR-020 | T017–T019, T031, T033 | locked local gate plus self-provisioned isolated PostgreSQL for the full test gate |
| SC-001, SC-002 | T011, T015–T016 | `make mvp-up`, live/ready checks |
| SC-003 | T009–T010, T014 | real HTTP smoke with one expected finding |
| SC-004 | T012–T016 | restart byte/hash/ETag comparison |
| SC-005, SC-006 | T017–T019 | release suites and no-egress evidence |
| SC-007 | T014–T016, T018, T032 | isolated startup, persistent shutdown and project-scoped reset/teardown |
| SC-008 | T019 | final tasks/review/commit |
