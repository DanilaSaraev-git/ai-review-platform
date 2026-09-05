# Research Decisions: локальный restart-safe backend MVP

## Decision 1 — synchronous single-process execution

**Decision**: `PostgresReviewPlatform` executes extraction, deterministic review and dialogue synchronously inside the API process.

**Rationale**: this is the shortest reliable path to a working local demonstration today. It preserves durable business records and canonical reports without making an unfinished queue a runtime dependency.

**Alternatives considered**: mandatory Procrastinate worker/outbox (deferred until lease, duplicate delivery and recovery semantics are completed); in-memory platform (rejected because restart persistence is required).

## Decision 2 — one-shot migration in Compose

**Decision**: a dedicated `migrate` service applies frozen Alembic migrations after PostgreSQL health and before API startup.

**Rationale**: schema ownership is explicit, repeatable and independently observable. API startup never silently creates schema.

**Alternatives considered**: migration in API entrypoint (less observable and harder to order); manual host migration (violates clean-checkout one-command setup).

## Decision 3 — normalized PostgreSQL plus POSIX volume

**Decision**: business state uses normalized tables; original documents and canonical report bytes use an owned POSIX Docker volume.

**Rationale**: it satisfies restart and byte-identity requirements while keeping the local deployment small.

**Alternatives considered**: JSONB singleton snapshot (rejected as a hidden second state model); S3-compatible service (unnecessary for local MVP).

## Decision 4 — loopback proxy only

**Decision**: nginx publishes `127.0.0.1:${REVIEW_PROXY_PORT}:8080`; PostgreSQL and API have no host ports.

**Rationale**: local use needs a stable same-origin endpoint but no public perimeter.

**Alternatives considered**: direct Uvicorn host port (works but bypasses intended proxy boundary); domain/TLS (explicitly out of scope).

## Decision 5 — deterministic mandatory path

**Decision**: the packaged exact synthetic binding is the only path allowed to produce the expected finding; arbitrary input receives explicit partial coverage. Optional model code remains non-gating.

**Rationale**: mandatory validation is reproducible, cost-free and honest about semantic capability.

**Alternatives considered**: downloading a local model (resource-dependent and not reproducible); external provider (requires secrets and egress).

## Decision 6 — queue prototypes remain deferred

**Decision**: retain existing worker/outbox code for later work but place the worker in an opt-in Compose profile and exclude queue health from readiness.

**Rationale**: deleting useful prototypes loses work; enabling incomplete delivery semantics would misrepresent readiness.

**Alternatives considered**: remove queue packages (unnecessary churn); expose them by default (outside MVP reliability boundary).
