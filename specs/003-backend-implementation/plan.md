# Implementation Plan: локальный restart-safe backend MVP

**Branch**: `codex/003-backend-implementation` | **Date**: 2026-09-05 | **Spec**: [spec.md](spec.md)

## Summary

Поставить локальный backend MVP одной командой Docker Compose. Default topology: PostgreSQL → one-shot Alembic migration → один FastAPI process с `PostgresReviewPlatform` и синхронным deterministic executor → nginx, опубликованный только на loopback. Состояние хранится в нормализованном PostgreSQL, immutable bytes — в POSIX volume. Worker/Procrastinate/outbox execution остаются deferred profile и не входят в readiness или DoD.

## Technical Context

**Language/Version**: Python 3.14.7
**Dependency manager**: uv 0.12.9, exact locked dependencies
**API**: FastAPI 0.141.1, Uvicorn 0.52.4
**Database**: PostgreSQL 18.6, psycopg 3.3.5, SQLAlchemy 2.0.52, Alembic 1.19.1
**Artifact storage**: local POSIX Docker volume
**Canonical JSON**: rfc8785 0.1.4
**Tests**: pytest 9.0.2; contract, unit, migration, integration, security, Compose E2E
**Target**: Docker Compose v2 on a local Mac, `127.0.0.1` only
**Scale boundary**: one configured organization/workspace/actor, one API replica, synchronous execution
**External dependencies**: none in the mandatory path

## Constitution Check

- `AGENTS.md` remains the only common instruction source; `CLAUDE.md` symlink is untouched.
- Feature 002 and canonical public v1 contracts are input baselines and are not modified.
- No files under `client-materials/` are read by runtime, packaged, or changed.
- Technical completion is reported separately from product validation and pilot evidence.
- Client-specific material stays outside common runtime and fixtures.

No constitution gate is violated.

## Architecture

```text
127.0.0.1:8080
      |
    nginx
      |
 FastAPI (one replica)
      |-- PostgresReviewPlatform -- PostgreSQL volume
      |-- TrustedFixtureReviewExecutor (synchronous)
      `-- PosixArtifactStore ------ artifact volume
```

Startup dependency order is enforced by Compose health conditions:

1. PostgreSQL reports healthy.
2. `migrate` runs `alembic upgrade head` and exits zero.
3. `api` starts, validates configuration/seed and exposes health checks.
4. `proxy` starts only after API health is green.

## Implementation Phases

### Phase 1 — Runtime composition

- Replace the obsolete `DurableReviewPlatform/runtime_state` composition with `PostgresReviewPlatform`.
- Make readiness check only database connectivity, exact Alembic head, exact seed and artifact writability.
- Keep queue prototypes importable but disconnected from default runtime.

### Phase 2 — Clean Compose

- Add one-shot migration service and init ownership for the artifact volume.
- Put worker behind `deferred-queue` profile.
- Add API/proxy health checks and loopback-only binding.
- Provide `make mvp-up`, `make mvp-smoke`, `make mvp-restart`, safe `make mvp-down`, and explicitly destructive `make mvp-reset`.

### Phase 3 — Verification

- Exercise canonical HTTP flow with exact synthetic fixture.
- Compare report bytes, SHA-256 and ETag across real container restart.
- Run locked unit/contract/migration/integration/security suites.
- Provision and clean an isolated loopback-only PostgreSQL project around the full contributor gate.
- Verify deterministic runtime does not attempt external connections.

## Project Structure

```text
apps/api/                       # FastAPI composition and routes
packages/review-core/           # domain/application rules
packages/review-runtime/        # PostgreSQL, artifacts, deterministic runtime
deploy/compose/                 # local-only image, Compose and config
tests/{contract,integration,e2e,security}/
specs/003-backend-implementation/
```

## Deferred Boundary

See [deferred-production-hardening.md](deferred-production-hardening.md). Queue dispatch, leases, recovery, multi-replica concurrency, collector crash races, external model productionization, public ingress/TLS and production operations are not enabled by this plan.

## Post-design Constitution Check

The design preserves all boundaries above. It changes implementation and feature-003 artifacts only.
