from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from review_runtime.config.settings import OperatorSettings
from review_runtime.fakes.review_executor import TrustedFixtureReviewExecutor
from review_runtime.postgres.platform import PostgresReviewPlatform


def test_report_and_artifacts_survive_new_process_composition(tmp_path: Path) -> None:
    database_url = os.environ.get(
        "REVIEW_TEST_DATABASE_URL",
        "postgresql+psycopg://review:review-local-only@127.0.0.1:55440/review",
    )
    root = Path(__file__).parents[2]
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
        runtime_config_path=root / "deploy/compose/config/runtime-config.synthetic.v1.json",
        expected_output_path=root
        / "deploy/compose/config/trusted-fixture-output.synthetic.v1.json",
        system_profile_id="50000000-0000-4000-8000-000000000001",
        model_profile_id="deterministic-v1",
        dialogue_policy_id="default-dialogue",
        skill_id="review-data-spec",
        skill_package_sha256="dda6f8e1dbbabb94132ee4530e0f592ec3164347a567999d97a6f613a3ea78e5",
    )
    first = PostgresReviewPlatform(TrustedFixtureReviewExecutor(root), settings)
    workspace_id = str(settings.workspace_id)
    document = first.upload(
        workspace_id,
        "synthetic-spec.md",
        "text/markdown",
        (root / "tests/fixtures/synthetic-review/synthetic-spec.md").read_bytes(),
    )
    profile = first.list_profiles(workspace_id)["items"][0]
    run = first.create_run(
        workspace_id,
        {
            "document_id": document["id"],
            "context_document_ids": [],
            "profile": {"id": profile["id"], "version": profile["version"]},
            "model_profile": {"id": "deterministic-v1", "version": "1.0.0"},
            "locale": "en-US",
        },
        str(uuid4()),
    )
    report, etag = first.report(workspace_id, run["id"])
    second = PostgresReviewPlatform(TrustedFixtureReviewExecutor(root), settings)
    assert second.report(workspace_id, run["id"]) == (report, etag)
    assert second.get_document(workspace_id, document["id"]).content
