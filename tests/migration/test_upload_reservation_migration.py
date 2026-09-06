"""Reservation upgrade/rollback on a disposable database preserves saved sources."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.migration.test_guest_migration import _document_snapshot, _seed_document


def test_upload_reservation_migration_preserves_documents_and_enforces_scope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    url = os.environ.get(
        "REVIEW_TEST_DATABASE_URL", "postgresql+psycopg://review:review-local-only@127.0.0.1:55440/review"
    )
    dsn = url.replace("postgresql+psycopg://", "postgresql://", 1)
    monkeypatch.setenv("REVIEW_DATABASE_URL", url)
    root = Path(__file__).parents[2]
    config = Config(str(root / "packages/review-runtime/alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, "20260906_0004")
    organization, workspace, actor = [str(uuid4()) for _ in range(3)]
    with psycopg.connect(dsn) as connection:
        connection.execute("INSERT INTO organizations(id,name) VALUES(%s,'Synthetic')", (organization,))
        connection.execute(
            "INSERT INTO workspaces(organization_id,id,name) VALUES(%s,%s,'Synthetic')",
            (organization, workspace),
        )
        connection.execute(
            "INSERT INTO actors(organization_id,workspace_id,id,display_name) VALUES(%s,%s,%s,'Synthetic')",
            (organization, workspace, actor),
        )
        document, source = _seed_document(connection, organization, workspace, actor, tmp_path)
    original, source_bytes = _document_snapshot(dsn, workspace, document), source.read_bytes()
    command.upgrade(config, "head")
    assert _document_snapshot(dsn, workspace, document) == original
    with psycopg.connect(dsn) as connection:
        insert = """INSERT INTO guest_upload_reservations
                    (organization_id,workspace_id,id,size_bytes,lease_key,created_at)
                    VALUES(%s,%s,%s,%s,42,now())"""
        connection.execute(insert, (organization, workspace, str(uuid4()), 123))
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute(insert, (organization, workspace, str(uuid4()), 0))
        with pytest.raises(psycopg.errors.ForeignKeyViolation), connection.transaction():
            connection.execute(insert, (organization, str(uuid4()), str(uuid4()), 123))
    command.downgrade(config, "20260906_0004")
    assert _document_snapshot(dsn, workspace, document) == original
    assert source.read_bytes() == source_bytes
    command.upgrade(config, "head")
    with psycopg.connect(dsn) as connection:
        assert connection.execute("SELECT count(*) FROM guest_upload_reservations").fetchone() == (0,)
    command.downgrade(config, "base")
