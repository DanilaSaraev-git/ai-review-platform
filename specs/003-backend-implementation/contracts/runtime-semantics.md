# Local MVP runtime semantics

## Default composition

The default durable API constructs `PostgresReviewPlatform` with typed `OperatorSettings`, `TrustedFixtureReviewExecutor` and `PosixArtifactStore`. It runs exactly one API replica. Upload extraction, review execution and dialogue generation finish synchronously before their create request returns.

`DurableReviewPlatform` and its former `runtime_state` snapshot are not valid production composition. Worker, Procrastinate, outbox dispatch and lease recovery are deferred prototypes and may run only through the explicit `deferred-queue` Compose profile.

## Persistence transaction boundary

- Original document bytes are staged, hash-verified and promoted to an opaque POSIX key before the referencing database transaction commits.
- Review output is structurally and semantically validated, canonicalized with `jcs-rfc8785-0.1.4`, staged and promoted before immutable report relations commit.
- Reads return the verified stored artifact bytes; they do not regenerate reports from mutable projections.
- Finding dialogue and Human Decision update only their own projections/history and cannot modify report relations or artifacts.
- Sequential create replays are resolved by `idempotency_records`. Concurrent multi-replica create semantics are deferred.

## Deterministic outcomes

- Exact configured document/profile/skill/parser/engine and expected-resource digests may resolve the packaged synthetic expected output.
- That exact fixture produces one validated finding.
- Any other supported document produces no findings, marks coverage partial, and adds one `CoverageGap(code=other, reason=semantic_analysis_not_performed)` per primary target fragment.
- Document text and filenames never select trusted behavior.

## Startup and readiness

Compose startup order is PostgreSQL health → successful one-shot Alembic migration → API health → proxy. API startup performs exact idempotent seed/check.

Liveness reports only process health. Readiness checks:

1. PostgreSQL connectivity;
2. exact application Alembic head;
3. exact configured seed and deterministic resources;
4. artifact-store write/read/delete probe.

Readiness does not inspect `runtime_state`, Procrastinate schema or worker health.

## Network boundary

Only nginx publishes a host port, bound to `127.0.0.1`. PostgreSQL, migration and API remain on the internal Compose network. The deterministic executor performs no HTTP or socket calls. Optional provider code is not selected by default and is not a release gate.

## Typed failures

| Condition | HTTP behavior |
| --- | --- |
| invalid upload/body | safe `400` |
| configured namespace/resource absent | `404` |
| idempotency mismatch or stale revision | `409` |
| report not yet available | `409` |
| upload exceeds limit | `413` |
| failed readiness check | safe `503` |
| unexpected internal error | safe `500`, without document/provider content |
