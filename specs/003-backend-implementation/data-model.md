# Data Model: локальный restart-safe backend MVP

The frozen Alembic migration is the schema authority. This document names the subset used by the default synchronous runtime.

## Deployment namespace

- `deployments`: release identity.
- `organizations` → `workspaces` → `actors`: one configured namespace and actor.
- `review_profile_families` → `review_profile_versions` + `review_profile_heads`: deployment-scoped system profile and optional workspace profiles.
- `model_profile_versions`, `skill_versions`, `dialogue_policy_versions`, `model_profile_availability`: exact seeded execution dependencies.

Bootstrap is idempotent. Existing IDs with different names, versions or digests are drift and make readiness fail.

## Documents

- `artifacts`: immutable opaque POSIX key, SHA-256, byte length and media type.
- `document_versions`: immutable metadata linked to its original artifact and actor.
- `document_extractions`: extraction state and parser identity.
- `fragments`: immutable ordered extracted text and location.

`DocumentVersion` belongs to exactly one organization/workspace through composite foreign keys.

## Review

- `execution_snapshots`: immutable profile/model/skill/policy/engine snapshot.
- `review_runs`: mutable lifecycle projection and stable public value.
- `review_run_sources`: immutable requested sources.
- `review_reports`: immutable canonical report graph linked to canonical artifact.
- `findings`, `finding_anchors`, `report_coverage`, `report_provenance`: normalized immutable report children.

The report artifact bytes are the read authority. Dialogue and decisions never update report relations or bytes.

## Human review

- `finding_states`: current decision projection with revision.
- `finding_dialogues`: ordered dialogue projection with revision and sendability.
- `dialogue_turns`: stored turns.
- `human_decisions`: append-only decision history.

## Idempotency

- `idempotency_records`: operation + configured namespace + caller key → request digest and resource ID.

The MVP guarantees sequential replay semantics. Multi-replica concurrent creation and queue delivery semantics are deferred.

## Deferred tables

`review_run_executions`, `generation_attempts`, `job_outbox` and lease fields remain in the frozen schema for forward compatibility but receive no records from the default synchronous request path and are not consumed by default Compose or readiness. Their production state machine is described only in [deferred-production-hardening.md](deferred-production-hardening.md).

## Immutable boundary

Database triggers reject UPDATE/DELETE on release/config versions, artifacts, documents, snapshots, reports and normalized report/history children. Mutable heads and projections are separate tables.
