# Quickstart: локальный restart-safe backend MVP

## Prerequisites

- macOS with Docker Desktop or Colima running
- Docker Compose v2
- `make`

No Python, API key, external model, domain or TLS setup is required on the host.

## Start or resume the MVP

```bash
make mvp-up
```

The target builds locked images, creates or reuses isolated named volumes, waits for PostgreSQL, applies Alembic migrations, starts one API replica and exposes nginx only at `http://127.0.0.1:8080` by default.

Expected:

```bash
curl --fail http://127.0.0.1:8080/health/live
curl --fail http://127.0.0.1:8080/health/ready
```

Both return HTTP 200. Readiness reports healthy database, migration, seed and artifact-store checks; it does not require queue tables.

## Run the real synthetic flow

```bash
make mvp-smoke
```

The smoke uses public HTTP endpoints to upload the packaged synthetic Markdown fixture, creates a review, reads the report, performs a dialogue turn and records a Human Decision. It asserts exactly one expected finding and records report bytes, SHA-256 and strong ETag.

## Verify restart persistence

```bash
make mvp-restart
```

The target restarts API and PostgreSQL without deleting volumes, waits for readiness, rereads the prior report and verifies identical bytes, SHA-256 and ETag.

## Contributor release gate

Operating the MVP does not require a host Python installation. Contributors running repository test suites additionally need the locked `uv` environment and Node.js. With the Compose flow and restart state still running, the full release gate is:

```bash
make release-check
```

The full target creates an isolated `review-platform-release` PostgreSQL 18 project on loopback port `55440`, runs migration before integration and E2E, and removes that test project's containers, networks and volume even when a suite fails. Set `RELEASE_DB_PORT` if that port is occupied. `make release-check-local` is a faster developer subset; it omits migration, integration and Compose E2E. Optional local-model smoke is not part of either mandatory gate.

The full gate automatically creates a separate `review-platform-release` PostgreSQL project on loopback port `55439`, runs migration before integration and E2E suites, and removes only that test project's containers and volumes even when a suite fails. Override `RELEASE_DB_PORT` if the default port is occupied. The running `review-platform-mvp` project and its operator data are not removed.

## Where the data is stored

The default Docker Compose project `review-platform-mvp` uses two named volumes:

- `review-platform-mvp_artifacts` stores the uploaded original document bytes and immutable canonical report bytes. The smoke verifier also keeps its restart-check state in this volume.
- `review-platform-mvp_postgres-data` stores PostgreSQL data: document and artifact metadata, extracted fragments, review runs, normalized findings, dialogues and Human Decisions.

Changing `MVP_PROJECT` changes the volume-name prefix. These are Docker-managed volumes, not files written into the repository checkout.

## Safe everyday shutdown

```bash
make mvp-down
```

This removes the MVP containers and networks but preserves both named volumes. A later `make mvp-up` reuses the documents, reports and application state.

## Destructive data reset

```bash
make mvp-reset
```

This irreversibly removes the isolated MVP containers and both named volumes, including every uploaded document, report, dialogue and decision in that project. It does not touch unrelated Docker resources. Use it only when a genuinely clean data state is required.

## Troubleshooting

- If port 8080 is occupied, run `MVP_PORT=18080 make mvp-up`; use the same `MVP_PORT` value for subsequent targets.
- If contributor test port 55440 is occupied, run `RELEASE_DB_PORT=55441 make release-check`.
- `docker compose -p review-platform-mvp -f deploy/compose/compose.yaml ps` shows startup ordering and health.
- `docker compose -p review-platform-mvp -f deploy/compose/compose.yaml logs migrate api proxy` shows safe startup diagnostics.
- Readiness `503` after configuration edits indicates schema, exact seed or artifact writability mismatch; no queue service is required.
