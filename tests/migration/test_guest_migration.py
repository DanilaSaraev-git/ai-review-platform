"""Run only against the disposable migration database, like the other migration tests."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from review_runtime.security.guest_sessions import GuestSessionStore

ROOT = Path(__file__).parents[2]
PREVIOUS = "20260905_0002"
GUEST_REVISION = "20260906_0003"


def _seed_document(
    connection: psycopg.Connection,
    organization: str,
    workspace: str,
    actor: str,
    artifact_root: Path,
) -> tuple[str, Path]:
    document, artifact = str(uuid4()), str(uuid4())
    content = b"# Synthetic migration fixture\n\nThe original document survives a schema rollback.\n"
    digest = hashlib.sha256(content).hexdigest()
    store_key = f"objects/{workspace}/{artifact}-{digest}"
    path = artifact_root / store_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    connection.execute(
        """INSERT INTO artifacts(organization_id,workspace_id,id,kind,store_key,sha256,
             size_bytes,media_type,canonical_codec_id,created_at)
           VALUES(%s,%s,%s,'document_source',%s,%s,%s,'text/markdown',NULL,now())""",
        (organization, workspace, artifact, store_key, digest, len(content)),
    )
    connection.execute(
        """INSERT INTO document_versions(organization_id,workspace_id,id,artifact_id,filename,
             media_type,sha256,size_bytes,extraction_state,created_by,created_at)
           VALUES(%s,%s,%s,%s,'synthetic-migration.md','text/markdown',%s,%s,'pending',%s,now())""",
        (organization, workspace, document, artifact, digest, len(content), actor),
    )
    return document, path


def _document_snapshot(dsn: str, workspace: str, document: str) -> tuple[Any, ...]:
    with psycopg.connect(dsn) as connection:
        row = connection.execute(
            """SELECT row_to_json(d),row_to_json(a),row_to_json(w),row_to_json(c)
               FROM document_versions d
               JOIN artifacts a ON (a.organization_id,a.workspace_id,a.id)=
                 (d.organization_id,d.workspace_id,d.artifact_id)
               JOIN workspaces w ON (w.organization_id,w.id)=(d.organization_id,d.workspace_id)
               JOIN actors c ON (c.organization_id,c.workspace_id,c.id)=
                 (d.organization_id,d.workspace_id,d.created_by)
               WHERE d.workspace_id=%s AND d.id=%s""",
            (workspace, document),
        ).fetchone()
    assert row is not None
    return row


def test_guest_upgrade_and_rollback_preserve_legacy_and_guest_documents(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    url = os.environ.get(
        "REVIEW_TEST_DATABASE_URL",
        "postgresql+psycopg://review:review-local-only@127.0.0.1:55440/review",
    )
    dsn = url.replace("postgresql+psycopg://", "postgresql://", 1)
    monkeypatch.setenv("REVIEW_DATABASE_URL", url)
    config = Config(str(ROOT / "packages/review-runtime/alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, PREVIOUS)
    deployment, organization, workspace, actor = [str(uuid4()) for _ in range(4)]
    with psycopg.connect(dsn) as connection:
        connection.execute(
            "INSERT INTO deployments(id,release_version,created_at) VALUES(%s,'synthetic-test',now())",
            (deployment,),
        )
        connection.execute("INSERT INTO organizations(id,name) VALUES(%s,'Synthetic')", (organization,))
        connection.execute(
            "INSERT INTO workspaces(organization_id,id,name) VALUES(%s,%s,'Synthetic legacy workspace')",
            (organization, workspace),
        )
        connection.execute(
            "INSERT INTO actors(organization_id,workspace_id,id,display_name) VALUES(%s,%s,%s,'Synthetic')",
            (organization, workspace, actor),
        )
        legacy_document, legacy_file = _seed_document(connection, organization, workspace, actor, tmp_path)
    legacy_before = _document_snapshot(dsn, workspace, legacy_document)
    legacy_bytes = legacy_file.read_bytes()

    command.upgrade(config, GUEST_REVISION)
    assert _document_snapshot(dsn, workspace, legacy_document) == legacy_before
    store = GuestSessionStore(dsn, deployment, organization)
    token, session = store.create()
    assert store.resolve(token) == session
    with psycopg.connect(dsn) as connection:
        guest_document, guest_file = _seed_document(
            connection,
            organization,
            session.workspace_id,
            session.actor_id,
            tmp_path,
        )
        # The database prevents a session from claiming an actor from another workspace.
        with pytest.raises(psycopg.errors.ForeignKeyViolation), connection.transaction():
            connection.execute(
                "UPDATE guest_sessions SET actor_id=%s WHERE workspace_id=%s",
                (actor, session.workspace_id),
            )
    guest_before = _document_snapshot(dsn, session.workspace_id, guest_document)
    guest_bytes = guest_file.read_bytes()

    command.downgrade(config, PREVIOUS)
    with psycopg.connect(dsn) as connection:
        assert connection.execute("SELECT to_regclass('public.guest_sessions')").fetchone() == (None,)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (PREVIOUS,)
    assert _document_snapshot(dsn, workspace, legacy_document) == legacy_before
    assert _document_snapshot(dsn, session.workspace_id, guest_document) == guest_before
    assert legacy_file.read_bytes() == legacy_bytes
    assert guest_file.read_bytes() == guest_bytes

    command.upgrade(config, GUEST_REVISION)
    with psycopg.connect(dsn) as connection:
        assert connection.execute("SELECT count(*) FROM guest_sessions").fetchone() == (0,)
    assert store.resolve(token) is None
    assert _document_snapshot(dsn, workspace, legacy_document) == legacy_before
    assert _document_snapshot(dsn, session.workspace_id, guest_document) == guest_before
    command.downgrade(config, "base")
