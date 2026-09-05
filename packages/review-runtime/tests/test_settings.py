from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from review_runtime.config.settings import OperatorSettings, RuntimePolicy

ROOT = Path(__file__).parents[3]


def test_runtime_policy_materializes_closed_safe_defaults() -> None:
    policy = RuntimePolicy.from_value({})
    assert policy.canonical_codec_id == "jcs-rfc8785-0.1.4"
    assert policy.deterministic_gateway.trusted_fixture_bindings == []
    assert policy.model_gateway.optional_openai_compatible.auto_download is False


def test_operator_settings_require_complete_single_namespace_and_seed() -> None:
    with pytest.raises(ValidationError):
        OperatorSettings()


def test_operator_settings_accept_exact_configured_context(tmp_path: Path) -> None:
    settings = OperatorSettings(
        deployment_id="60000000-0000-4000-8000-000000000001",
        organization_id="30000000-0000-4000-8000-000000000001",
        organization_name="Synthetic Organization",
        workspace_id="20000000-0000-4000-8000-000000000001",
        workspace_name="Synthetic Workspace",
        actor_id="10000000-0000-4000-8000-000000000001",
        actor_display_name="Synthetic Analyst",
        artifact_root=tmp_path,
        database_url="postgresql+psycopg://review:review@postgres/review",
        queue_database_url="postgresql://review:review@postgres/review",
        runtime_config_path=ROOT / "specs/003-backend-implementation/contracts/runtime-config.v1.schema.json",
        expected_output_path=ROOT
        / "tests/fixtures/synthetic-review/trusted-fixture-expected-output.v1.json",
        system_profile_id="50000000-0000-4000-8000-000000000001",
        model_profile_id="deterministic-v1",
        dialogue_policy_id="default-dialogue",
        skill_id="review-data-spec",
        skill_package_sha256="dda6f8e1dbbabb94132ee4530e0f592ec3164347a567999d97a6f613a3ea78e5",
    )
    assert settings.workspace_id.version == 4
    assert settings.artifact_root == tmp_path
    assert settings.expected_output_path.name == "trusted-fixture-expected-output.v1.json"
