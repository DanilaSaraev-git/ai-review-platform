from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from review_api.app import create_app
from review_core.application.platform import ReviewPlatform
from review_runtime.config.settings import OperatorSettings
from review_runtime.fakes.review_executor import TrustedFixtureReviewExecutor


@pytest.fixture(scope="session")
def database_url() -> str:
    value = os.environ.get(
        "REVIEW_TEST_DATABASE_URL",
        "postgresql+psycopg://review:review-local-only@127.0.0.1:55440/review",
    )
    try:
        with psycopg.connect(value.replace("postgresql+psycopg://", "postgresql://", 1), connect_timeout=1):
            pass
    except psycopg.Error:
        pytest.fail("real PostgreSQL 18 integration database is required")
    return value


@pytest.fixture
def operator_settings(database_url: str, tmp_path: Path) -> OperatorSettings:
    return OperatorSettings(
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
        runtime_config_path=Path("deploy/compose/config/runtime-config.synthetic.v1.json"),
        expected_output_path=Path(
            "deploy/compose/config/trusted-fixture-output.synthetic.v1.json"
        ),
        system_profile_id="50000000-0000-4000-8000-000000000001",
        model_profile_id="deterministic-v1",
        dialogue_policy_id="default-dialogue",
        skill_id="review-data-spec",
        skill_package_sha256="dda6f8e1dbbabb94132ee4530e0f592ec3164347a567999d97a6f613a3ea78e5",
    )


@pytest.fixture
def durable_app(monkeypatch, operator_settings):  # type: ignore[no-untyped-def]
    values = {
        "REVIEW_DEPLOYMENT_ID": operator_settings.deployment_id,
        "REVIEW_ORGANIZATION_ID": operator_settings.organization_id,
        "REVIEW_ORGANIZATION_NAME": operator_settings.organization_name,
        "REVIEW_WORKSPACE_ID": operator_settings.workspace_id,
        "REVIEW_WORKSPACE_NAME": operator_settings.workspace_name,
        "REVIEW_ACTOR_ID": operator_settings.actor_id,
        "REVIEW_ACTOR_DISPLAY_NAME": operator_settings.actor_display_name,
        "REVIEW_ARTIFACT_ROOT": operator_settings.artifact_root,
        "REVIEW_DATABASE_URL": operator_settings.database_url,
        "REVIEW_QUEUE_DATABASE_URL": operator_settings.queue_database_url,
        "REVIEW_RUNTIME_CONFIG_PATH": Path(operator_settings.runtime_config_path).resolve(),
        "REVIEW_EXPECTED_OUTPUT_PATH": Path(operator_settings.expected_output_path).resolve(),
        "REVIEW_SYSTEM_PROFILE_ID": operator_settings.system_profile_id,
        "REVIEW_MODEL_PROFILE_ID": operator_settings.model_profile_id,
        "REVIEW_DIALOGUE_POLICY_ID": operator_settings.dialogue_policy_id,
        "REVIEW_SKILL_ID": operator_settings.skill_id,
        "REVIEW_SKILL_PACKAGE_SHA256": operator_settings.skill_package_sha256,
    }
    for name, value in values.items():
        monkeypatch.setenv(name, str(value))
    return create_app(composition="durable")


@pytest.fixture
def durable_client(durable_app):  # type: ignore[no-untyped-def]
    return TestClient(durable_app)


@pytest.fixture
def client_platform():  # type: ignore[no-untyped-def]
    root = Path(__file__).parents[2]
    platform = ReviewPlatform(TrustedFixtureReviewExecutor(root))
    document = platform.upload(
        platform.workspace_id,
        "synthetic-spec.md",
        "text/markdown",
        (root / "tests/fixtures/synthetic-review/synthetic-spec.md").read_bytes(),
    )
    profile = platform.system_profile
    run = platform.create_run(
        platform.workspace_id,
        {
            "document_id": document["id"],
            "context_document_ids": [],
            "profile": {"id": profile.id, "version": profile.version},
            "model_profile": {"id": "deterministic-v1", "version": "1.0.0"},
            "locale": "en-US",
        },
        "cancellation-test",
    )
    return platform, run["id"]
