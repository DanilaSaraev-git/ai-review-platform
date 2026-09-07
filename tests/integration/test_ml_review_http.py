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
        "REVIEW_MODEL_PROFILE_ID": reference["id"],
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


def _request_review(
    client: TestClient, workspace_id: str, reference: dict[str, str], *, locale: str = "en-US"
):
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
            "locale": locale,
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


@pytest.mark.parametrize("violation", ["coverage", "json", "length"])
@pytest.mark.parametrize("invalid_attempts", [1, 2])
def test_review_recovers_invalid_response_before_publishing(
    monkeypatch: pytest.MonkeyPatch, operator_settings, tmp_path: Path,
    violation: str, invalid_attempts: int,
) -> None:
    reference = _configure_ml(monkeypatch, operator_settings, tmp_path)
    valid = (FIXTURES / "review-response.json").read_text()
    invalid = json.loads(valid)
    if violation == "quote":
        invalid["findings"][0]["anchors"][0]["quote"] = "PRIVATE_MODEL_INSTRUCTION"
    elif violation == "fragment":
        invalid["findings"][0]["anchors"][0]["fragment_id"] = "wrong-fragment"
    elif violation == "coverage":
        invalid["coverage"]["reviewed_fragment_ids"] = []
    provider = FakeModelProvider([
        *[ScriptedReply(chat_completion(
            "not-json" if violation == "json" else json.dumps(invalid),
            finish_reason="length" if violation == "length" else "stop",
        )) for _ in range(invalid_attempts)],
        ScriptedReply(chat_completion(valid)),
    ])
    app = create_app(composition="ml", model_transport=provider.transport)
    app.state.platform.observe_model_profile(
        reference, state="available", reason_code=None,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    with TestClient(app) as client:
        workspace_id = app.state.platform.workspace_id
        response = _request_review(client, workspace_id, reference, locale="ru-RU")
        assert response.status_code == 202, response.text
        assert response.json()["state"] == "completed", response.text
        report = client.get(
            f"/v1/workspaces/{workspace_id}/review-runs/{response.json()['id']}/report"
        )
        assert report.status_code == 200
        assert report.json()["findings"][0]["anchors"][0]["quote"] == "Refresh runs regularly."
    assert provider.call_count == invalid_attempts + 1
    retry_body = json.loads(provider.requests[1].content)
    assert "PRIVATE_MODEL_INSTRUCTION" not in retry_body["messages"][0]["content"]
    assert "previous_response" in retry_body["messages"][1]["content"]
    if violation == "quote":
        assert "findings[0].anchors" in retry_body["messages"][0]["content"]
        assert "PRIVATE_MODEL_INSTRUCTION" in retry_body["messages"][1]["content"]
    assert "ru-RU" in json.dumps(retry_body)
    assert "Previous response rejected" in json.dumps(retry_body)


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
    provider = FakeModelProvider([ScriptedReply(chat_completion("not-json")) for _ in range(3)])
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
    assert provider.call_count == (0 if outcome == "oversize" else 3)

@pytest.mark.parametrize(
    ("violation", "diagnostic"),
    [
        ("coverage", "coverage_partition_inexact"),
    ],
)
def test_semantic_failure_preserves_safe_reason_after_bounded_recovery_without_publishing(
    monkeypatch: pytest.MonkeyPatch,
    operator_settings,  # type: ignore[no-untyped-def]
    tmp_path: Path,
    violation: str,
    diagnostic: str,
) -> None:
    reference = _configure_ml(monkeypatch, operator_settings, tmp_path)
    response = json.loads((FIXTURES / "review-response.json").read_text())
    private_marker = "synthetic-private-content-not-for-diagnostics"
    if violation == "quote":
        response["findings"][0]["anchors"][0]["quote"] = private_marker
    elif violation == "fragment":
        response["findings"][0]["anchors"][0]["fragment_id"] = private_marker
    else:
        response["coverage"]["reviewed_fragment_ids"] = []
    provider = FakeModelProvider([
        ScriptedReply(chat_completion(json.dumps(response))) for _ in range(3)
    ])
    app = create_app(composition="ml", model_transport=provider.transport)
    app.state.platform.observe_model_profile(
        reference,
        state="available",
        reason_code=None,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    expected_error = {
        "code": "validation_failed",
        "message": f"The model response evidence failed validation ({diagnostic}).",
        "retryable": False,
    }
    with TestClient(app) as client:
        workspace_id = app.state.platform.workspace_id
        accepted = _request_review(client, workspace_id, reference)
        assert accepted.status_code == 202
        run = accepted.json()
        assert run["state"] == "failed"
        assert run["error"] == expected_error
        assert private_marker not in accepted.text
        report = client.get(f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/report")
        assert report.status_code == 409
    with psycopg.connect(app.state.platform.database_url) as connection:
        saved = connection.execute(
            "SELECT value->'error' FROM review_runs WHERE id=%s", (run["id"],)
        ).fetchone()
    assert saved == (expected_error,)
    assert provider.call_count == 3


@pytest.mark.parametrize("quote", ["invented quote ...", "regularly regularly"])
def test_bad_evidence_is_detached_without_losing_the_finding(
    monkeypatch: pytest.MonkeyPatch, operator_settings, tmp_path: Path, quote: str
) -> None:
    reference = _configure_ml(monkeypatch, operator_settings, tmp_path)
    output = json.loads((FIXTURES / "review-response.json").read_text())
    output["findings"][0]["anchors"][0]["quote"] = quote
    provider = FakeModelProvider([ScriptedReply(chat_completion(json.dumps(output)))])
    app = create_app(composition="ml", model_transport=provider.transport)
    app.state.platform.observe_model_profile(
        reference, state="available", reason_code=None,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    with TestClient(app) as client:
        workspace_id = app.state.platform.workspace_id
        response = _request_review(client, workspace_id, reference, locale="ru-RU")
        assert response.json()["state"] == "completed", response.text
        report = client.get(
            f"/v1/workspaces/{workspace_id}/review-runs/{response.json()['id']}/report"
        )
        assert report.status_code == 200
        assert report.json()["coverage"]["status"] == "complete"
        assert len(report.json()["findings"]) == 1
        assert report.json()["findings"][0]["anchors"] == []
        assert report.json()["findings"][0]["problem"] == output["findings"][0]["problem"]
        assert report.json()["summary"] == output["summary"]
        assert report.json()["limitations"] == output["limitations"]
        assert quote not in report.text
        finding_id = report.json()["findings"][0]["id"]
        run_id = response.json()["id"]
        assert client.get(
            f"/v1/workspaces/{workspace_id}/review-runs/{run_id}/findings/{finding_id}/dialogue"
        ).status_code == 200
    assert provider.call_count == 1

@pytest.mark.parametrize("response_shape", ["valid_json", "truncated_json"])
def test_ml_review_rejects_output_limit_before_parsing_and_preserves_attempt_metadata(
    monkeypatch: pytest.MonkeyPatch,
    operator_settings,  # type: ignore[no-untyped-def]
    tmp_path: Path,
    response_shape: str,
) -> None:
    reference = _configure_ml(monkeypatch, operator_settings, tmp_path)
    response_text = (FIXTURES / "review-response.json").read_text()
    if response_shape == "truncated_json":
        response_text = '{"summary":"PRIVATE_TRUNCATED_MODEL_OUTPUT'
    provider = FakeModelProvider([
        ScriptedReply(chat_completion(
            response_text,
            finish_reason="length",
            usage={"prompt_tokens": 3126, "completion_tokens": 4096},
        )) for _ in range(3)
    ])
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
        run = response.json()
        assert run["state"] == "failed"
        assert run["error"] == {
            "code": "model_output_invalid",
            "message": "The model response reached the output token limit before completion.",
            "retryable": False,
        }
        assert "PRIVATE_TRUNCATED_MODEL_OUTPUT" not in response.text
        assert client.get(
            f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/report"
        ).status_code == 409
    assert provider.call_count == 3
    with psycopg.connect(app.state.platform.database_url) as connection:
        attempt = connection.execute(
            "SELECT state,value FROM model_attempts WHERE value#>>'{profile,id}'=%s",
            (reference["id"],),
        ).fetchone()
    assert attempt is not None
    assert attempt[0] == "succeeded"
    assert attempt[1]["result"]["finish_reason"] == "length"
    assert attempt[1]["result"]["usage"]["output_tokens"] == 4096
    assert "PRIVATE_TRUNCATED_MODEL_OUTPUT" not in json.dumps(attempt[1])
