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
from tests.integration.run_helpers import wait_for_run_terminal
from tests.integration.test_ml_review_http import FIXTURES, _configure_ml, _request_review


@pytest.mark.parametrize(
    ("locale", "legacy", "expected_dialogue_locale"),
    [("ru-RU", False, "ru-RU"), ("en-US", False, "en-US"), ("en-US", True, "ru-RU")],
)
def test_dialogue_preserves_review_locale_after_restart_without_changing_report(
    monkeypatch: pytest.MonkeyPatch,
    operator_settings,  # type: ignore[no-untyped-def]
    tmp_path: Path,
    locale: str,
    legacy: bool,
    expected_dialogue_locale: str,
) -> None:
    reference = _configure_ml(monkeypatch, operator_settings, tmp_path)
    review_provider = FakeModelProvider([
        ScriptedReply(chat_completion((FIXTURES / "review-response.json").read_text()))
    ])
    app = create_app(composition="ml", model_transport=review_provider.transport)
    app.state.platform.observe_model_profile(
        reference,
        state="available",
        reason_code=None,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    with TestClient(app) as client:
        workspace_id = app.state.platform.workspace_id
        response = _request_review(client, workspace_id, reference, locale=locale)
        assert response.status_code == 202, response.text
        run = wait_for_run_terminal(client, workspace_id, response.json()["id"])
        assert run["state"] == "completed"
        report_url = f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/report"
        before = client.get(report_url)
        assert before.status_code == 200
        finding_id = before.json()["findings"][0]["id"]
        review_request = json.loads(review_provider.requests[0].content)
        review_input = json.loads(review_request["messages"][-1]["content"])
        assert review_input["options"]["locale"] == locale
        review_language = "Russian" if locale == "ru-RU" else "English"
        assert f"Output language: {review_language} ({locale})" in review_request["messages"][0]["content"]

    with psycopg.connect(app.state.platform.database_url) as connection:
        saved_locale = connection.execute(
            """SELECT value->>'locale' FROM review_run_executions
               WHERE organization_id=%s AND workspace_id=%s AND run_id=%s""",
            (app.state.platform.organization_id, workspace_id, run["id"]),
        ).fetchone()
        assert saved_locale == (locale,)
        if legacy:
            connection.execute(
                """UPDATE review_run_executions SET value=value::jsonb - 'locale'
                   WHERE organization_id=%s AND workspace_id=%s AND run_id=%s""",
                (app.state.platform.organization_id, workspace_id, run["id"]),
            )

    dialogue_output = json.loads((FIXTURES / "dialogue-response.json").read_text())
    dialogue_output["anchors"] = dialogue_output["anchors"][:1]
    dialogue_provider = FakeModelProvider([
        ScriptedReply(chat_completion(json.dumps(dialogue_output)))
    ])
    restarted = create_app(composition="ml", model_transport=dialogue_provider.transport)
    with TestClient(restarted) as client:
        response = client.post(
            f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/findings/{finding_id}/dialogue/turns",
            headers={"Idempotency-Key": f"dialogue-locale-{uuid4().hex}"},
            json={"message": "Clarify the schedule.", "expected_revision": 0},
        )
        assert response.status_code == 202, response.text
        assert response.json()["turns"][0]["state"] == "completed", response.text
        dialogue_request = json.loads(dialogue_provider.requests[0].content)
        dialogue_input = json.loads(dialogue_request["messages"][-1]["content"])
        assert dialogue_input["options"]["locale"] == expected_dialogue_locale
        dialogue_language = "Russian" if expected_dialogue_locale == "ru-RU" else "English"
        assert (
            f"Output language: {dialogue_language} ({expected_dialogue_locale})"
            in dialogue_request["messages"][0]["content"]
        )
        after = client.get(report_url)
        assert after.content == before.content
        assert after.headers["etag"] == before.headers["etag"]
    assert review_provider.call_count == dialogue_provider.call_count == 1


def test_external_dialogue_failure_retries_same_turn_and_preserves_report(
    monkeypatch: pytest.MonkeyPatch, operator_settings, tmp_path: Path  # type: ignore[no-untyped-def]
) -> None:
    reference = _configure_ml(monkeypatch, operator_settings, tmp_path)
    dialogue_output = json.loads((FIXTURES / "dialogue-response.json").read_text())
    dialogue_output["anchors"] = dialogue_output["anchors"][:1]
    provider = FakeModelProvider(
        [
            ScriptedReply(chat_completion((FIXTURES / "review-response.json").read_text())),
            ScriptedReply(chat_completion("not-json")),
            ScriptedReply(chat_completion(json.dumps(dialogue_output))),
        ]
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
        accepted = _request_review(client, workspace_id, reference)
        run = wait_for_run_terminal(client, workspace_id, accepted.json()["id"])
        report_url = f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/report"
        before = client.get(report_url)
        finding_id = before.json()["findings"][0]["id"]
        base = f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/findings/{finding_id}"

        failed = client.post(
            f"{base}/dialogue/turns",
            headers={"Idempotency-Key": "dialogue-failure-key"},
            json={"message": "Propose an exact schedule.", "expected_revision": 0},
        )
        assert failed.status_code == 202, failed.text
        failed_turn = failed.json()["turns"][0]
        assert failed_turn["state"] == "failed"
        assert failed_turn["error"]["code"] == "model_output_invalid"

        retried = client.post(
            f"{base}/dialogue/turns/{failed_turn['id']}/retry",
            headers={"Idempotency-Key": "dialogue-retry-key"},
            json={"expected_revision": failed.json()["revision"]},
        )
        replay = client.post(
            f"{base}/dialogue/turns/{failed_turn['id']}/retry",
            headers={"Idempotency-Key": "dialogue-retry-key"},
            json={"expected_revision": failed.json()["revision"]},
        )
        assert retried.status_code == replay.status_code == 202
        assert len(retried.json()["turns"]) == 1
        assert retried.json()["turns"][0]["id"] == failed_turn["id"]
        assert retried.json()["turns"][0]["state"] == "completed"
        assert replay.json()["turns"][0] == retried.json()["turns"][0]
        assert provider.call_count == 3

        after = client.get(report_url)
        assert after.content == before.content
        assert after.headers["etag"] == before.headers["etag"]


@pytest.mark.parametrize("response_shape", ["valid_json", "truncated_json"])
@pytest.mark.parametrize(("finish_reason", "expected_code", "expected_message"), [
    (
        "length", "model_output_invalid",
        "The model response reached the output token limit before completion.",
    ),
    (
        "content_filter", "content_blocked",
        "The model response did not finish with a complete result.",
    ),
])
def test_external_dialogue_reports_incomplete_output_before_parsing_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    operator_settings,  # type: ignore[no-untyped-def]
    tmp_path: Path,
    response_shape: str,
    finish_reason: str,
    expected_code: str,
    expected_message: str,
) -> None:
    reference = _configure_ml(monkeypatch, operator_settings, tmp_path)
    dialogue_output = json.loads((FIXTURES / "dialogue-response.json").read_text())
    dialogue_output["anchors"] = dialogue_output["anchors"][:1]
    response_text = json.dumps(dialogue_output)
    if response_shape == "truncated_json":
        response_text = '{"content":"PRIVATE_TRUNCATED_MODEL_OUTPUT'
    provider = FakeModelProvider([
        ScriptedReply(chat_completion((FIXTURES / "review-response.json").read_text())),
        ScriptedReply(chat_completion(response_text, finish_reason=finish_reason)),
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
        accepted = _request_review(client, workspace_id, reference)
        run = wait_for_run_terminal(client, workspace_id, accepted.json()["id"])
        report_url = f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/report"
        before = client.get(report_url)
        finding_id = before.json()["findings"][0]["id"]
        response = client.post(
            f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/findings/{finding_id}/dialogue/turns",
            headers={"Idempotency-Key": "dialogue-output-limit"},
            json={"message": "Clarify the schedule.", "expected_revision": 0},
        )
        assert response.status_code == 202, response.text
        turn = response.json()["turns"][0]
        assert turn["state"] == "failed"
        assert turn["assistant_response"] is None
        assert turn["error"] == {
            "code": expected_code,
            "message": expected_message,
            "retryable": False,
        }
        assert "PRIVATE_TRUNCATED_MODEL_OUTPUT" not in response.text
        assert client.get(report_url).content == before.content
    assert provider.call_count == 2
