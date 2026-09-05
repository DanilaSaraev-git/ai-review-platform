.PHONY: lint contracts test-unit test-integration test-migration test-security test-e2e release-check-local release-check mvp-up mvp-smoke mvp-restart mvp-down mvp-reset

UV := uv run --frozen
MVP_PROJECT ?= review-platform-mvp
MVP_PORT ?= 8080
MVP_COMPOSE := REVIEW_PROXY_PORT=$(MVP_PORT) docker compose --project-name $(MVP_PROJECT) -f deploy/compose/compose.yaml
MVP_STATE := /var/lib/review/mvp-smoke-state.json
MVP_SMOKE := $(MVP_COMPOSE) exec -T api python tools/mvp_smoke.py --base-url http://proxy:8080 --state-file $(MVP_STATE)
RELEASE_PROJECT ?= review-platform-release
RELEASE_DB_PORT ?= 55440
RELEASE_DATABASE_URL := postgresql+psycopg://review:review-local-only@127.0.0.1:$(RELEASE_DB_PORT)/review
RELEASE_COMPOSE := REVIEW_TEST_POSTGRES_PORT=$(RELEASE_DB_PORT) docker compose --project-name $(RELEASE_PROJECT) -f deploy/compose/compose.yaml -f deploy/compose/compose.release.yaml

lint:
	$(UV) ruff check packages apps/api apps/worker apps/cli tests tools
	$(UV) mypy

contracts:
	npm ci --ignore-scripts --prefix tools/contracts/orval
	python3 tools/contracts/validate_contracts.py
	$(UV) pytest -q tests/contract

test-unit:
	$(UV) pytest -q packages/review-core/tests packages/review-runtime/tests apps/cli/tests

test-integration:
	$(UV) pytest -q tests/integration

test-migration:
	$(UV) pytest -q tests/migration

test-security:
	$(UV) pytest -q tests/security

test-e2e:
	$(UV) pytest -q tests/e2e

release-check-local: lint contracts test-unit test-security
	python3 tools/contracts/check_protected_paths.py

release-check: release-check-local
	@set -eu; \
	cleanup() { $(RELEASE_COMPOSE) down --volumes --remove-orphans >/dev/null 2>&1 || true; }; \
	trap cleanup EXIT INT TERM; \
	$(RELEASE_COMPOSE) up --detach --wait postgres; \
	REVIEW_TEST_DATABASE_URL=$(RELEASE_DATABASE_URL) $(UV) pytest -q tests/migration; \
	REVIEW_TEST_DATABASE_URL=$(RELEASE_DATABASE_URL) $(UV) pytest -q tests/integration; \
	REVIEW_TEST_DATABASE_URL=$(RELEASE_DATABASE_URL) $(UV) pytest -q tests/e2e

mvp-up:
	$(MVP_COMPOSE) up --build --detach --wait proxy

mvp-smoke:
	$(MVP_SMOKE) run

mvp-restart:
	$(MVP_COMPOSE) restart postgres api
	$(MVP_COMPOSE) up --detach --wait proxy
	$(MVP_SMOKE) verify-restart

mvp-down:
	$(MVP_COMPOSE) down --remove-orphans

mvp-reset:
	$(MVP_COMPOSE) down --volumes --remove-orphans
