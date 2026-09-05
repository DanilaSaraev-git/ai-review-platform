from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from review_core.canonical import digest_value
from review_runtime.config.settings import OperatorSettings
from review_runtime.fakes.review_executor import TrustedFixtureReviewExecutor
from review_runtime.postgres.platform import (
    PostgresReviewPlatform,
    ReviewStorageRequest,
    wire_time,
)

ROOT = Path(__file__).parents[2]


def _platform(tmp_path: Path) -> PostgresReviewPlatform:
    database_url = os.environ.get(
        "REVIEW_TEST_DATABASE_URL",
        "postgresql+psycopg://review:review-local-only@127.0.0.1:55440/review",
    )
    settings = OperatorSettings(
        deployment_id="60000000-0000-4000-8000-000000000001",
        organization_id="30000000-0000-4000-8000-000000000001",
        organization_name="Synthetic Organization",
        workspace_id="20000000-0000-4000-8000-000000000001",
        workspace_name="Synthetic Workspace",
        actor_id="10000000-0000-4000-8000-000000000001",
        actor_display_name="Synthetic Analyst",
        artifact_root=tmp_path / "artifacts",
        database_url=database_url,
        queue_database_url=database_url.replace("postgresql+psycopg://", "postgresql://", 1),
        runtime_config_path=ROOT / "deploy/compose/config/runtime-config.synthetic.v1.json",
        expected_output_path=ROOT
        / "deploy/compose/config/trusted-fixture-output.synthetic.v1.json",
        system_profile_id="50000000-0000-4000-8000-000000000001",
        model_profile_id="deterministic-v1",
        dialogue_policy_id="default-dialogue",
        skill_id="review-data-spec",
        skill_package_sha256="dda6f8e1dbbabb94132ee4530e0f592ec3164347a567999d97a6f613a3ea78e5",
    )
    return PostgresReviewPlatform(TrustedFixtureReviewExecutor(ROOT), settings)


def test_second_process_cannot_own_same_deployment(tmp_path: Path) -> None:
    first = _platform(tmp_path / "first")
    second = _platform(tmp_path / "second")
    first.startup()
    try:
        with pytest.raises(RuntimeError, match="already owns"):
            second.startup()
    finally:
        first.shutdown()
    second.startup()
    second.shutdown()


def test_startup_marks_accepted_review_interrupted_without_model_attempt(
    tmp_path: Path,
) -> None:
    platform = _platform(tmp_path)
    workspace_id = platform.workspace_id
    document = platform.upload(
        workspace_id,
        "interrupted.md",
        "text/markdown",
        b"Synthetic interrupted review.\n",
    )
    profile = platform.list_profiles(workspace_id)["items"][0]
    snapshot = platform.snapshot_for_profile_reference(
        {"id": profile["id"], "version": profile["version"]}
    )
    run_id = str(uuid4())
    created_at = wire_time(datetime.now(UTC))
    run_value = {
        "id": run_id,
        "workspace_id": workspace_id,
        "state": "queued",
        "progress": {"percent": 0, "message": "Review queued"},
        "document_id": document["id"],
        "context_document_ids": [],
        "execution_snapshot": snapshot,
        "created_by": platform.actor,
        "created_at": created_at,
        "started_at": None,
        "finished_at": None,
        "cancel_requested_at": None,
        "report_available": False,
        "error": None,
    }
    body = {
        "document_id": document["id"],
        "context_document_ids": [],
        "profile": {"id": profile["id"], "version": profile["version"]},
        "model_profile": {"id": "deterministic-v1", "version": "1.0.0"},
        "locale": "en-US",
    }
    platform.review_storage.admit(
        ReviewStorageRequest(
            workspace_id=workspace_id,
            idempotency_key=f"restart-{uuid4().hex}",
            request_body=body,
            run_id=run_id,
            snapshot_id=str(uuid4()),
            snapshot=snapshot,
            run_value=run_value,
            sources=(
                {
                    "source_id": "source-main",
                    "document_id": document["id"],
                    "role": "document",
                    "ordinal": 1,
                },
            ),
        ),
        datetime.now(UTC) + timedelta(minutes=5),
    )

    platform.startup()
    platform.shutdown()

    failed = platform.get_run(workspace_id, run_id).value
    assert failed["state"] == "failed"
    assert failed["error"]["code"] == "internal_error"
    with psycopg.connect(platform.database_url) as connection:
        execution = connection.execute(
            """SELECT state,value->'error'->>'code' FROM review_run_executions
               WHERE organization_id=%s AND workspace_id=%s AND run_id=%s""",
            (platform.organization_id, workspace_id, run_id),
        ).fetchone()
        attempts = connection.execute(
            """SELECT count(*) FROM model_attempts m JOIN review_work_items w
                 ON (w.organization_id,w.workspace_id,w.id)=
                    (m.organization_id,m.workspace_id,m.work_item_id)
               JOIN review_run_executions e
                 ON (e.organization_id,e.workspace_id,e.id)=
                    (w.organization_id,w.workspace_id,w.execution_id)
               WHERE e.run_id=%s""",
            (run_id,),
        ).fetchone()[0]
    assert execution == ("failed", "process_interrupted")
    assert attempts == 0
    assert digest_value(snapshot) == digest_value(failed["execution_snapshot"])
