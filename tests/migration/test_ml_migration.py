from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import DBAPIError

ROOT = Path(__file__).parents[2]
HEAD = "20260905_0002"
BASELINE = "20260905_0001"
ORG = "30000000-0000-4000-8000-000000000001"
WORKSPACE = "20000000-0000-4000-8000-000000000001"
ACTOR = "10000000-0000-4000-8000-000000000001"
DOCUMENT_ARTIFACT = "70000000-0000-4000-8000-000000000001"
REPORT_ARTIFACT = "70000000-0000-4000-8000-000000000002"
DOCUMENT = "40000000-0000-4000-8000-000000000001"
RUN = "80000000-0000-4000-8000-000000000001"
EXECUTION = "81000000-0000-4000-8000-000000000001"
WORK_ITEM = "82000000-0000-4000-8000-000000000001"
REPORT = "83000000-0000-4000-8000-000000000001"
FINDING = "84000000-0000-4000-8000-000000000001"
DIALOGUE = "85000000-0000-4000-8000-000000000001"
TURN = "86000000-0000-4000-8000-000000000001"
OTHER_TURN = "86000000-0000-4000-8000-000000000002"
GENERATION = "87000000-0000-4000-8000-000000000001"
OTHER_GENERATION = "87000000-0000-4000-8000-000000000002"


def _database() -> tuple[str, str]:
    url = os.environ.get(
        "REVIEW_TEST_DATABASE_URL",
        "postgresql+psycopg://review:review-local-only@127.0.0.1:55440/review",
    )
    return url, url.replace("postgresql+psycopg://", "postgresql://", 1)


def _config(monkeypatch: pytest.MonkeyPatch) -> Config:
    url, _ = _database()
    monkeypatch.setenv("REVIEW_DATABASE_URL", url)
    return Config(str(ROOT / "packages/review-runtime/alembic.ini"))


def _seed_execution_and_dialogue(connection: psycopg.Connection) -> None:
    connection.execute("INSERT INTO organizations(id, name) VALUES(%s, 'Synthetic')", (ORG,))
    connection.execute(
        "INSERT INTO workspaces(organization_id, id, name) VALUES(%s, %s, 'Synthetic')",
        (ORG, WORKSPACE),
    )
    connection.execute(
        """INSERT INTO actors(organization_id, workspace_id, id, display_name)
           VALUES(%s, %s, %s, 'Synthetic Analyst')""",
        (ORG, WORKSPACE, ACTOR),
    )
    for artifact_id, kind, store_key, codec in (
        (DOCUMENT_ARTIFACT, "document_source", "documents/source", None),
        (REPORT_ARTIFACT, "report_canonical", "reports/report", "jcs-rfc8785-0.1.4"),
    ):
        connection.execute(
            """INSERT INTO artifacts(
                 organization_id, workspace_id, id, kind, store_key, sha256, size_bytes,
                 media_type, canonical_codec_id, created_at
               ) VALUES(%s, %s, %s, %s, %s, %s, 16, 'application/json', %s, now())""",
            (ORG, WORKSPACE, artifact_id, kind, store_key, "a" * 64, codec),
        )
    connection.execute(
        """INSERT INTO document_versions(
             organization_id, workspace_id, id, artifact_id, filename, media_type, sha256,
             size_bytes, extraction_state, created_by, created_at
           ) VALUES(%s, %s, %s, %s, 'synthetic.md', 'text/markdown', %s, 16,
                    'completed', %s, now())""",
        (ORG, WORKSPACE, DOCUMENT, DOCUMENT_ARTIFACT, "b" * 64, ACTOR),
    )
    connection.execute(
        """INSERT INTO review_runs(
             organization_id, workspace_id, id, document_id, state, revision, snapshot, value
           ) VALUES(%s, %s, %s, %s, 'completed', 1, '{}'::json, '{}'::json)""",
        (ORG, WORKSPACE, RUN, DOCUMENT),
    )
    connection.execute(
        """INSERT INTO review_run_executions(
             run_id, organization_id, workspace_id, id, state, checkpoint, attempt_count, revision, value
           ) VALUES(%s, %s, %s, %s, 'completed', 'published', 1, 1, '{}'::json)""",
        (RUN, ORG, WORKSPACE, EXECUTION),
    )
    connection.execute(
        """INSERT INTO review_work_items(
             organization_id, workspace_id, execution_id, id, ordinal, fragment_id, state, value
           ) VALUES(%s, %s, %s, %s, 0, NULL, 'completed', '{}'::json)""",
        (ORG, WORKSPACE, EXECUTION, WORK_ITEM),
    )
    connection.execute(
        """INSERT INTO review_reports(
             organization_id, workspace_id, id, run_id, artifact_id, canonical_sha256,
             etag, codec_id, graph, created_at
           ) VALUES(%s, %s, %s, %s, %s, %s, %s, 'jcs-rfc8785-0.1.4', '{}'::json, now())""",
        (ORG, WORKSPACE, REPORT, RUN, REPORT_ARTIFACT, "c" * 64, '"' + "c" * 64 + '"'),
    )
    connection.execute(
        """INSERT INTO findings(organization_id, workspace_id, report_id, id, ordinal, value)
           VALUES(%s, %s, %s, %s, 0, '{}'::json)""",
        (ORG, WORKSPACE, REPORT, FINDING),
    )
    connection.execute(
        """INSERT INTO finding_dialogues(
             organization_id, workspace_id, id, finding_id, revision, value
           ) VALUES(%s, %s, %s, %s, 0, '{}'::json)""",
        (ORG, WORKSPACE, DIALOGUE, FINDING),
    )
    for turn_id, ordinal in ((TURN, 0), (OTHER_TURN, 1)):
        connection.execute(
            """INSERT INTO dialogue_turns(
                 organization_id, workspace_id, id, dialogue_id, ordinal, state, value
               ) VALUES(%s, %s, %s, %s, %s, 'failed', '{}'::json)""",
            (ORG, WORKSPACE, turn_id, DIALOGUE, ordinal),
        )
    for generation_id, turn_id in ((GENERATION, TURN), (OTHER_GENERATION, OTHER_TURN)):
        connection.execute(
            """INSERT INTO generation_attempts(
                 dialogue_turn_id, ordinal, value, organization_id, workspace_id, id,
                 state, checkpoint, attempt_count, revision
               ) VALUES(%s, 0, '{}'::json, %s, %s, %s, 'failed', 'transport', 1, 1)""",
            (turn_id, ORG, WORKSPACE, generation_id),
        )


def _seed_legacy_report(connection: psycopg.Connection) -> None:
    connection.execute("INSERT INTO organizations(id, name) VALUES(%s, 'Synthetic')", (ORG,))
    connection.execute(
        "INSERT INTO workspaces(organization_id, id, name) VALUES(%s, %s, 'Synthetic')",
        (ORG, WORKSPACE),
    )
    connection.execute(
        """INSERT INTO actors(organization_id, workspace_id, id, display_name)
           VALUES(%s, %s, %s, 'Synthetic Analyst')""",
        (ORG, WORKSPACE, ACTOR),
    )
    for artifact_id, kind, store_key, sha256, codec in (
        (DOCUMENT_ARTIFACT, "document_source", "legacy/document", "a" * 64, None),
        (
            REPORT_ARTIFACT,
            "report_canonical",
            "legacy/report",
            "c" * 64,
            "jcs-rfc8785-0.1.4",
        ),
    ):
        connection.execute(
            """INSERT INTO artifacts(
                 organization_id, workspace_id, id, kind, store_key, sha256, size_bytes,
                 media_type, canonical_codec_id, created_at
               ) VALUES(%s, %s, %s, %s, %s, %s, 73, 'application/json', %s, now())""",
            (ORG, WORKSPACE, artifact_id, kind, store_key, sha256, codec),
        )
    connection.execute(
        """INSERT INTO document_versions(
             organization_id, workspace_id, id, artifact_id, filename, media_type, sha256,
             size_bytes, extraction_state, created_by, created_at
           ) VALUES(%s, %s, %s, %s, 'legacy.md', 'text/markdown', %s, 16,
                    'completed', %s, now())""",
        (ORG, WORKSPACE, DOCUMENT, DOCUMENT_ARTIFACT, "b" * 64, ACTOR),
    )
    connection.execute(
        """INSERT INTO review_runs(
             organization_id, workspace_id, id, document_id, state, revision, snapshot, value
           ) VALUES(%s, %s, %s, %s, 'completed', 1, '{}'::json, '{}'::json)""",
        (ORG, WORKSPACE, RUN, DOCUMENT),
    )
    connection.execute(
        """INSERT INTO review_run_sources(
             organization_id, workspace_id, run_id, source_id, document_id, role, ordinal, prepared
           ) VALUES(%s, %s, %s, 'legacy-primary', %s, 'primary', 0,
                    '{"digest":"legacy-prepared"}'::json)""",
        (ORG, WORKSPACE, RUN, DOCUMENT),
    )
    connection.execute(
        """INSERT INTO review_run_executions(
             run_id, organization_id, workspace_id, id, state, checkpoint, attempt_count, revision
           ) VALUES(%s, %s, %s, %s, 'completed', 'published', 1, 1)""",
        (RUN, ORG, WORKSPACE, EXECUTION),
    )
    connection.execute(
        """INSERT INTO review_work_items(
             organization_id, workspace_id, execution_id, id, ordinal, fragment_id, state, value
           ) VALUES(%s, %s, %s, %s, 0, 'legacy-fragment', 'completed', '{}'::json)""",
        (ORG, WORKSPACE, EXECUTION, WORK_ITEM),
    )
    connection.execute(
        """INSERT INTO model_attempts(
             organization_id, workspace_id, work_item_id, id, ordinal, state, value
           ) VALUES(%s, %s, %s, %s, 0, 'succeeded', '{"provider":"legacy"}'::json)""",
        (ORG, WORKSPACE, WORK_ITEM, "88000000-0000-4000-8000-000000000001"),
    )
    connection.execute(
        """INSERT INTO review_reports(
             organization_id, workspace_id, id, run_id, artifact_id, canonical_sha256,
             etag, codec_id, graph, created_at
           ) VALUES(%s, %s, %s, %s, %s, %s, %s, 'jcs-rfc8785-0.1.4',
                    '{ "schema_version": "review-report.v1", "title": "Synthetic" }'::json,
                    now())""",
        (ORG, WORKSPACE, REPORT, RUN, REPORT_ARTIFACT, "c" * 64, '"' + "c" * 64 + '"'),
    )


def test_empty_database_upgrades_to_ml_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config(monkeypatch)
    _, dsn = _database()
    command.downgrade(config, "base")

    command.upgrade(config, "head")

    with psycopg.connect(dsn) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (HEAD,)
        columns = {
            (row[0], row[1], row[2])
            for row in connection.execute(
                """
                SELECT table_name, column_name, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND (table_name, column_name) IN (
                    ('review_run_executions', 'value'),
                    ('review_work_items', 'fragment_id'),
                    ('model_attempts', 'generation_attempt_id'),
                    ('dialogue_turns', 'active_generation_attempt_id')
                  )
                """
            )
        }
        assert columns == {
            ("review_run_executions", "value", "NO"),
            ("review_work_items", "fragment_id", "YES"),
            ("model_attempts", "generation_attempt_id", "YES"),
            ("dialogue_turns", "active_generation_attempt_id", "YES"),
        }

    command.downgrade(config, "base")


def test_model_attempt_owner_and_active_generation_are_namespace_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(monkeypatch)
    _, dsn = _database()
    command.upgrade(config, "head")
    with psycopg.connect(dsn) as connection:
        _seed_execution_and_dialogue(connection)
        connection.execute(
            """INSERT INTO model_attempts(
                 organization_id, workspace_id, id, work_item_id, generation_attempt_id,
                 ordinal, state, value
               ) VALUES(%s, %s, %s, %s, NULL, 0, 'succeeded', '{}'::json)""",
            (ORG, WORKSPACE, "88000000-0000-4000-8000-000000000001", WORK_ITEM),
        )
        connection.execute(
            """INSERT INTO model_attempts(
                 organization_id, workspace_id, id, work_item_id, generation_attempt_id,
                 ordinal, state, value
               ) VALUES(%s, %s, %s, NULL, %s, 0, 'succeeded', '{}'::json)""",
            (ORG, WORKSPACE, "88000000-0000-4000-8000-000000000002", GENERATION),
        )
        for owner_column, owner_id in (
            ("work_item_id", WORK_ITEM),
            ("generation_attempt_id", GENERATION),
        ):
            with pytest.raises(psycopg.errors.UniqueViolation), connection.transaction():
                connection.execute(
                    f"""INSERT INTO model_attempts(
                          organization_id, workspace_id, id, {owner_column}, ordinal, state, value
                        ) VALUES(%s, %s, %s, %s, 0, 'failed', '{{}}'::json)""",
                    (ORG, WORKSPACE, "88000000-0000-4000-8000-000000000008", owner_id),
                )
        connection.execute(
            """UPDATE dialogue_turns SET active_generation_attempt_id = %s
               WHERE organization_id = %s AND workspace_id = %s AND id = %s""",
            (GENERATION, ORG, WORKSPACE, TURN),
        )

        for work_item_id, generation_attempt_id in ((None, None), (WORK_ITEM, GENERATION)):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(
                    """INSERT INTO model_attempts(
                         organization_id, workspace_id, id, work_item_id, generation_attempt_id,
                         ordinal, state, value
                       ) VALUES(%s, %s, %s, %s, %s, 9, 'failed', '{}'::json)""",
                    (
                        ORG,
                        WORKSPACE,
                        "88000000-0000-4000-8000-000000000009",
                        work_item_id,
                        generation_attempt_id,
                    ),
                )

        with pytest.raises(psycopg.errors.ForeignKeyViolation), connection.transaction():
            connection.execute(
                """UPDATE dialogue_turns SET active_generation_attempt_id = %s
                   WHERE organization_id = %s AND workspace_id = %s AND id = %s""",
                (OTHER_GENERATION, ORG, WORKSPACE, TURN),
            )

        primary_key = connection.execute(
            """SELECT pg_get_constraintdef(oid)
               FROM pg_constraint
               WHERE conrelid = 'model_attempts'::regclass AND contype = 'p'"""
        ).fetchone()
        assert primary_key == ("PRIMARY KEY (organization_id, workspace_id, id)",)

    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute("UPDATE dialogue_turns SET active_generation_attempt_id = NULL")
        connection.execute("DELETE FROM model_attempts")
        connection.execute("DELETE FROM review_work_items WHERE fragment_id IS NULL")
    command.downgrade(config, "base")


def test_prepared_source_can_be_filled_once_without_weakening_immutability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(monkeypatch)
    _, dsn = _database()
    command.upgrade(config, "head")
    with psycopg.connect(dsn) as connection:
        _seed_execution_and_dialogue(connection)
        connection.execute(
            """INSERT INTO review_run_sources(
                 organization_id, workspace_id, run_id, source_id, document_id, role, ordinal, prepared
               ) VALUES(%s, %s, %s, 'source-primary', %s, 'primary', 0, NULL)""",
            (ORG, WORKSPACE, RUN, DOCUMENT),
        )

    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(
            """UPDATE review_run_sources SET prepared = '{"digest":"synthetic"}'::json
               WHERE organization_id = %s AND workspace_id = %s
                 AND run_id = %s AND source_id = 'source-primary'""",
            (ORG, WORKSPACE, RUN),
        )
        assert connection.execute(
            """SELECT prepared->>'digest' FROM review_run_sources
               WHERE organization_id = %s AND workspace_id = %s
                 AND run_id = %s AND source_id = 'source-primary'""",
            (ORG, WORKSPACE, RUN),
        ).fetchone() == ("synthetic",)
        with pytest.raises(psycopg.errors.IntegrityConstraintViolation):
            connection.execute(
                """UPDATE review_run_sources SET prepared = '{"digest":"changed"}'::json
                   WHERE organization_id = %s AND workspace_id = %s
                     AND run_id = %s AND source_id = 'source-primary'""",
                (ORG, WORKSPACE, RUN),
            )
        with pytest.raises(psycopg.errors.IntegrityConstraintViolation):
            connection.execute(
                """UPDATE review_run_sources SET role = 'context'
                   WHERE organization_id = %s AND workspace_id = %s
                     AND run_id = %s AND source_id = 'source-primary'""",
                (ORG, WORKSPACE, RUN),
            )
        with pytest.raises(psycopg.errors.IntegrityConstraintViolation):
            connection.execute(
                """DELETE FROM review_run_sources
                   WHERE organization_id = %s AND workspace_id = %s
                     AND run_id = %s AND source_id = 'source-primary'""",
                (ORG, WORKSPACE, RUN),
            )

    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute("DELETE FROM review_work_items WHERE fragment_id IS NULL")
    command.downgrade(config, "base")


def test_legacy_history_and_published_report_survive_upgrade_and_downgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(monkeypatch)
    _, dsn = _database()
    command.upgrade(config, BASELINE)
    with psycopg.connect(dsn) as connection:
        _seed_legacy_report(connection)
        before = connection.execute(
            """SELECT r.graph::text, r.canonical_sha256, r.etag, a.sha256, a.size_bytes
               FROM review_reports r
               JOIN artifacts a
                 ON (a.organization_id, a.workspace_id, a.id) =
                    (r.organization_id, r.workspace_id, r.artifact_id)
               WHERE r.organization_id = %s AND r.workspace_id = %s AND r.id = %s""",
            (ORG, WORKSPACE, REPORT),
        ).fetchone()
    assert before == (
        '{ "schema_version": "review-report.v1", "title": "Synthetic" }',
        "c" * 64,
        '"' + "c" * 64 + '"',
        "c" * 64,
        73,
    )

    command.upgrade(config, "head")
    with psycopg.connect(dsn) as connection:
        after_upgrade = connection.execute(
            """SELECT r.graph::text, r.canonical_sha256, r.etag, a.sha256, a.size_bytes
               FROM review_reports r
               JOIN artifacts a
                 ON (a.organization_id, a.workspace_id, a.id) =
                    (r.organization_id, r.workspace_id, r.artifact_id)
               WHERE r.organization_id = %s AND r.workspace_id = %s AND r.id = %s""",
            (ORG, WORKSPACE, REPORT),
        ).fetchone()
        assert after_upgrade == before
        assert connection.execute(
            """SELECT value::jsonb, prepared->>'digest'
               FROM review_run_executions e
               JOIN review_run_sources s
                 ON (s.organization_id, s.workspace_id, s.run_id) =
                    (e.organization_id, e.workspace_id, e.run_id)
               WHERE e.organization_id = %s AND e.workspace_id = %s AND e.id = %s""",
            (ORG, WORKSPACE, EXECUTION),
        ).fetchone() == ({}, "legacy-prepared")
        assert connection.execute(
            """SELECT work_item_id, generation_attempt_id, value->>'provider'
               FROM model_attempts
               WHERE organization_id = %s AND workspace_id = %s""",
            (ORG, WORKSPACE),
        ).fetchone() == (WORK_ITEM, None, "legacy")

    command.downgrade(config, BASELINE)
    with psycopg.connect(dsn) as connection:
        assert connection.execute(
            """SELECT r.graph::text, r.canonical_sha256, r.etag, a.sha256, a.size_bytes
               FROM review_reports r
               JOIN artifacts a
                 ON (a.organization_id, a.workspace_id, a.id) =
                    (r.organization_id, r.workspace_id, r.artifact_id)
               WHERE r.organization_id = %s AND r.workspace_id = %s AND r.id = %s""",
            (ORG, WORKSPACE, REPORT),
        ).fetchone() == before
    command.downgrade(config, "base")


def test_downgrade_rejects_incompatible_ml_history_until_operator_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(monkeypatch)
    _, dsn = _database()
    command.upgrade(config, "head")
    with psycopg.connect(dsn) as connection:
        _seed_execution_and_dialogue(connection)
        connection.execute(
            """UPDATE review_run_executions
               SET value = '{"prepared_input_digest":"synthetic"}'::json
               WHERE organization_id = %s AND workspace_id = %s AND id = %s""",
            (ORG, WORKSPACE, EXECUTION),
        )
        connection.execute(
            """INSERT INTO model_attempts(
                 organization_id, workspace_id, id, work_item_id, generation_attempt_id,
                 ordinal, state, value
               ) VALUES(%s, %s, %s, NULL, %s, 0, 'succeeded', '{}'::json)""",
            (ORG, WORKSPACE, "88000000-0000-4000-8000-000000000002", GENERATION),
        )
        connection.execute(
            """UPDATE dialogue_turns SET active_generation_attempt_id = %s
               WHERE organization_id = %s AND workspace_id = %s AND id = %s""",
            (GENERATION, ORG, WORKSPACE, TURN),
        )

    with pytest.raises(DBAPIError, match="incompatible LLM execution history"):
        command.downgrade(config, BASELINE)
    with psycopg.connect(dsn) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (HEAD,)
        assert connection.execute("SELECT count(*) FROM model_attempts").fetchone() == (1,)
        assert connection.execute(
            "SELECT count(*) FROM review_work_items WHERE fragment_id IS NULL"
        ).fetchone() == (1,)

    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute("UPDATE dialogue_turns SET active_generation_attempt_id = NULL")
        connection.execute("DELETE FROM model_attempts WHERE generation_attempt_id IS NOT NULL")
        connection.execute("DELETE FROM review_work_items WHERE fragment_id IS NULL")
        connection.execute("UPDATE review_run_executions SET value = '{}'::json")

    command.downgrade(config, BASELINE)
    with psycopg.connect(dsn) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (BASELINE,)
    command.downgrade(config, "base")
