from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from review_api.app import create_app

from tests.integration.fake_model_provider import FakeModelProvider, ScriptedReply, chat_completion
from tests.integration.test_ml_review_http import FIXTURES, _configure_ml, _request_review


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
        run = _request_review(client, workspace_id, reference).json()
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
