"""Run against a disposable database; preserve immutable pre-cycle records."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.migration.test_guest_migration import _seed_document
from tests.migration.test_ml_migration import ACTOR, DOCUMENT, ORG, WORKSPACE, _seed_execution_and_dialogue

ROOT = Path(__file__).parents[2]


def test_cycle_migration_backfills_separate_families_and_preserves_legacy_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    url = os.environ.get(
        "REVIEW_TEST_DATABASE_URL", "postgresql+psycopg://review:review-local-only@127.0.0.1:55440/review"
    )
    dsn = url.replace("postgresql+psycopg://", "postgresql://", 1)
    monkeypatch.setenv("REVIEW_DATABASE_URL", url)
    config = Config(str(ROOT / "packages/review-runtime/alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, "20260906_0003")
    with psycopg.connect(dsn) as connection:
        _seed_execution_and_dialogue(connection)
        another, source = _seed_document(connection, ORG, WORKSPACE, ACTOR, tmp_path)
    source_before = source.read_bytes()

    def preserved():
        with psycopg.connect(dsn) as connection:
            return tuple(
                connection.execute(query).fetchall()
                for query in (
                    "SELECT row_to_json(d) FROM document_versions d ORDER BY id",
                    "SELECT row_to_json(r) FROM review_reports r ORDER BY id",
                    "SELECT row_to_json(d) FROM finding_dialogues d ORDER BY id",
                    "SELECT row_to_json(a) FROM artifacts a ORDER BY id",
                )
            )

    original = preserved()
    command.upgrade(config, "20260906_0004")
    assert preserved() == original
    assert source.read_bytes() == source_before
    with psycopg.connect(dsn) as connection:
        members = connection.execute(
            "SELECT document_id,family_id,version_number FROM document_family_versions ORDER BY document_id"
        ).fetchall()
        assert set(members) == {(DOCUMENT, DOCUMENT, 1), (another, another, 1)}
        assert connection.execute("SELECT baseline_run_id FROM review_cycles").fetchone() == (None,)
        with pytest.raises(psycopg.errors.IntegrityConstraintViolation), connection.transaction():
            connection.execute(
                "UPDATE document_family_versions SET version_number=2 WHERE document_id=%s", (DOCUMENT,)
            )
    command.downgrade(config, "20260906_0003")
    assert preserved() == original
    assert source.read_bytes() == source_before
    command.upgrade(config, "head")
    # Cleanup only the seeded synthetic execution shape before testing older rollback guards.
    with psycopg.connect(dsn) as connection:
        connection.execute("UPDATE review_run_executions SET value = '{}'::json")
        connection.execute("DELETE FROM review_work_items WHERE fragment_id IS NULL")
    command.downgrade(config, "base")
