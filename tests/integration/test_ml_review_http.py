from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from review_api.app import create_app

from tests.integration.fake_model_provider import FakeModelProvider, ScriptedReply, chat_completion

ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests/fixtures/ml-integration"


def _configure_ml(
    monkeypatch: pytest.MonkeyPatch,
    operator_settings,  # type: ignore[no-untyped-def]
    tmp_path: Path,
    *,
    max_input_bytes: int = 524_288,
) -> dict[str, str]:
    reference = {"id": f"synthetic-http-{uuid4().hex}", "version": "1.0.0"}
    profile = json.loads(
        (ROOT / "deploy/compose/config/model-profile.external.example.json").read_text()
    )
    profile.update(reference)
    profile["max_input_utf8_bytes"] = max_input_bytes
    profile_path = tmp_path / "model-profile.json"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    credential = tmp_path / "credential"
    credential.write_text("synthetic-secret", encoding="utf-8")
    values = {
        "REVIEW_COMPOSITION": "ml",
        "REVIEW_DEPLOYMENT_ID": str(operator_settings.deployment_id),
        "REVIEW_ORGANIZATION_ID": str(operator_settings.organization_id),
        "REVIEW_ORGANIZATION_NAME": operator_settings.organization_name,
        "REVIEW_WORKSPACE_ID": str(operator_settings.workspace_id),
        "REVIEW_WORKSPACE_NAME": operator_settings.workspace_name,
        "REVIEW_ACTOR_ID": str(operator_settings.actor_id),
        "REVIEW_ACTOR_DISPLAY_NAME": operator_settings.actor_display_name,
        "REVIEW_ARTIFACT_ROOT": str(tmp_path / "artifacts"),
        "REVIEW_DATABASE_URL": operator_settings.database_url,
        "REVIEW_QUEUE_DATABASE_URL": operator_settings.queue_database_url,
        "REVIEW_RUNTIME_CONFIG_PATH": str(Path(operator_settings.runtime_config_path).resolve()),
        "REVIEW_EXPECTED_OUTPUT_PATH": str(Path(operator_settings.expected_output_path).resolve()),
        "REVIEW_SYSTEM_PROFILE_ID": operator_settings.system_profile_id,
        "REVIEW_MODEL_PROFILE_ID": operator_settings.model_profile_id,
        "REVIEW_DIALOGUE_POLICY_ID": operator_settings.dialogue_policy_id,
        "REVIEW_SKILL_ID": operator_settings.skill_id,
        "REVIEW_SKILL_PACKAGE_SHA256": operator_settings.skill_package_sha256,
        "REVIEW_MODEL_PROFILE_PATH": str(profile_path),
        "REVIEW_MODEL_CREDENTIAL_PATH": str(credential),
        "REVIEW_SKILL_PACKAGE_PATH": str(FIXTURES / "skill"),
    }
    for name, value in values.items():
        monkeypatch.setenv(name, str(value))
    return reference


def _request_review(client: TestClient, workspace_id: str, reference: dict[str, str]):
    document = client.post(
        f"/v1/workspaces/{workspace_id}/documents",
        files={"file": ("primary.md", (FIXTURES / "primary.md").read_bytes(), "text/markdown")},
    )
    assert document.status_code == 201, document.text
    profiles = client.get(f"/v1/workspaces/{workspace_id}/profiles").json()["items"]
    return client.post(
        f"/v1/workspaces/{workspace_id}/review-runs",
        headers={"Idempotency-Key": f"ml-review-{uuid4().hex}"},
        json={
            "document_id": document.json()["id"],
            "context_document_ids": [],
            "profile": {"id": profiles[0]["id"], "version": profiles[0]["version"]},
            "model_profile": reference,
            "locale": "en-US",
        },
    )


def test_ml_review_calls_fake_provider_once_and_publishes_immutable_report(
    monkeypatch: pytest.MonkeyPatch, operator_settings, tmp_path: Path  # type: ignore[no-untyped-def]
) -> None:
    reference = _configure_ml(monkeypatch, operator_settings, tmp_path)
    response_text = (FIXTURES / "review-response.json").read_text()
    provider = FakeModelProvider(
        [ScriptedReply(chat_completion(response_text, usage={"prompt_tokens": 111, "completion_tokens": 22}))]
    )
    app = create_app(composition="ml", model_transport=provider.transport)
    app.state.platform.observe_model_profile(
        reference,
        state="available",
        reason_code=None,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    with TestClient(app) as client:
        workspace_id = app.state.platform.workspace_id
        response = _request_review(client, workspace_id, reference)
        assert response.status_code == 202, response.text
        assert response.json()["state"] == "completed"
        report = client.get(
            f"/v1/workspaces/{workspace_id}/review-runs/{response.json()['id']}/report"
        )
        assert report.status_code == 200
        assert report.json()["findings"][0]["title"] == "Refresh schedule is unspecified"
        assert provider.call_count == 1
        assert provider.requests[0].headers["authorization"] == "Bearer synthetic-secret"

    with psycopg.connect(app.state.platform.database_url) as connection:
        attempt = connection.execute(
            """SELECT state,value->'result'->>'provider',value->'result'->>'model_version'
               FROM model_attempts WHERE organization_id=%s AND workspace_id=%s""",
            (app.state.platform.organization_id, workspace_id),
        ).fetchone()
    assert attempt == ("succeeded", "synthetic-provider", "unknown")


@pytest.mark.parametrize("outcome", ["oversize", "invalid"])
def test_ml_review_failure_never_publishes_report(
    monkeypatch: pytest.MonkeyPatch,
    operator_settings,  # type: ignore[no-untyped-def]
    tmp_path: Path,
    outcome: str,
) -> None:
    reference = _configure_ml(
        monkeypatch,
        operator_settings,
        tmp_path,
        max_input_bytes=64 if outcome == "oversize" else 524_288,
    )
    provider = FakeModelProvider([ScriptedReply(chat_completion("not-json"))])
    app = create_app(composition="ml", model_transport=provider.transport)
    app.state.platform.observe_model_profile(
        reference,
        state="available",
        reason_code=None,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    with TestClient(app) as client:
        workspace_id = app.state.platform.workspace_id
        response = _request_review(client, workspace_id, reference)
        assert response.status_code == 202, response.text
        assert response.json()["state"] == "failed"
        expected = "context_limit" if outcome == "oversize" else "model_output_invalid"
        assert response.json()["error"]["code"] == expected
        report = client.get(
            f"/v1/workspaces/{workspace_id}/review-runs/{response.json()['id']}/report"
        )
        assert report.status_code == 409
    assert provider.call_count == (0 if outcome == "oversize" else 1)
