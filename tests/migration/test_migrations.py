import os
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config


def test_initial_migration_has_upgrade_downgrade_and_immutable_guards() -> None:
    root = Path(__file__).parents[2]
    migrations = root / "packages/review-runtime/migrations/versions"
    migration = (migrations / "20260905_0001_initial_durable_review_platform_schema.py").read_text()
    assert "Base.metadata" not in migration
    assert '"review_runs",' in migration
    assert 'op.drop_table("review_runs")' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "reject_immutable_row_mutation" in migration
    assert "review_reports" in migration


def test_alembic_environment_uses_runtime_url_override() -> None:
    root = Path(__file__).parents[2]
    environment = (root / "packages/review-runtime/migrations/env.py").read_text()
    assert 'os.environ.get("REVIEW_DATABASE_URL")' in environment
    assert "target_metadata = Base.metadata" in environment


def test_real_empty_upgrade_downgrade_current_head_and_immutability(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    root = Path(__file__).parents[2]
    url = os.environ.get(
        "REVIEW_TEST_DATABASE_URL",
        "postgresql+psycopg://review:review-local-only@127.0.0.1:55440/review",
    )
    dsn = url.replace("postgresql+psycopg://", "postgresql://", 1)
    try:
        connection = psycopg.connect(dsn, connect_timeout=1)
    except psycopg.Error:
        pytest.fail("real PostgreSQL 18 migration database is required")
    monkeypatch.setenv("REVIEW_DATABASE_URL", url)
    config = Config(str(root / "packages/review-runtime/alembic.ini"))
    command.downgrade(config, "base")
    assert connection.execute("SELECT to_regclass('public.review_runs')").fetchone() == (None,)
    connection.close()
    command.upgrade(config, "head")
    connection = psycopg.connect(dsn)
    with connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("20260905_0002",)
        connection.execute(
            "INSERT INTO deployments(id, release_version, created_at) VALUES(%s, %s, now())",
            ("60000000-0000-4000-8000-000000000099", "test"),
        )
        with pytest.raises(psycopg.errors.IntegrityConstraintViolation):
            connection.execute(
                "UPDATE deployments SET release_version = 'changed' WHERE id = %s",
                ("60000000-0000-4000-8000-000000000099",),
            )
        connection.rollback()
