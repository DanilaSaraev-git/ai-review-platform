from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from review_api.app import create_app

ROOT = Path(__file__).parents[2]


def _configure(
    monkeypatch: pytest.MonkeyPatch,
    operator_settings,  # type: ignore[no-untyped-def]
    tmp_path: Path,
    *,
    unconfigured: bool,
) -> None:
    config = json.loads(
        (ROOT / "deploy/compose/config/runtime-config.synthetic.v1.json").read_text()
    )
    config["budgets"].update(
        max_upload_bytes=32 if unconfigured else 52_428_800,
        max_context_documents=1,
        max_dialogue_message_codepoints=5,
        max_dialogue_turns=1,
        max_parallel_model_calls=2,
    )
    if unconfigured:
        config["deterministic_gateway"]["trusted_fixture_bindings"] = []
    config_path = tmp_path / f"runtime-{uuid4().hex}.json"
    config_path.write_text(json.dumps(config))
    for field, value in operator_settings.model_dump().items():
        monkeypatch.setenv(f"REVIEW_{field.upper()}", str(value))
    for field in (
        "DEPLOYMENT_ID",
        "ORGANIZATION_ID",
        "WORKSPACE_ID",
        "ACTOR_ID",
        "SYSTEM_PROFILE_ID",
    ):
        monkeypatch.setenv(f"REVIEW_{field}", str(uuid4()))
    monkeypatch.setenv("REVIEW_RUNTIME_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("REVIEW_DIALOGUE_POLICY_ID", f"bounded-dialogue-{uuid4().hex}")
    if unconfigured:
        monkeypatch.setenv("REVIEW_MODEL_PROFILE_ID", f"model-not-configured-{uuid4().hex}")
        monkeypatch.delenv("REVIEW_EXPECTED_OUTPUT_PATH", raising=False)


def _upload(client: TestClient, workspace_id: str, content: bytes, name: str = "input.md"):
    return client.post(
        f"/v1/workspaces/{workspace_id}/documents",
        files={"file": (name, content, "text/markdown")},
    )


def test_unknown_composition_never_falls_back_to_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REVIEW_COMPOSITION", raising=False)

    with pytest.raises(ValueError, match="unsupported review composition"):
        create_app(composition="unconfigurd")


def test_unconfigured_launch_is_ready_but_never_runs_fixture_as_ai(
    monkeypatch: pytest.MonkeyPatch,
    operator_settings,  # type: ignore[no-untyped-def]
    tmp_path: Path,
) -> None:
    _configure(monkeypatch, operator_settings, tmp_path, unconfigured=True)
    app = create_app(composition="unconfigured")

    with TestClient(app) as client:
        workspace_id = app.state.platform.workspace_id
        with psycopg.connect(app.state.platform.database_url) as connection:
            runs_before = connection.execute(
                "SELECT count(*) FROM review_runs WHERE organization_id=%s AND workspace_id=%s",
                (app.state.platform.organization_id, workspace_id),
            ).fetchone()[0]
        readiness = client.get("/health/ready")
        assert readiness.status_code == 200
        assert readiness.json()["composition"] == "unconfigured"
        bootstrap = client.get("/v1/bootstrap").json()
        assert bootstrap["limits"] == {
            "document_upload_max_bytes": 32,
            "max_context_documents": 1,
        }
        models = client.get(f"/v1/workspaces/{workspace_id}/model-profiles").json()["items"]
        assert len(models) == 1
        assert models[0]["availability"] == "unavailable"
        assert models[0]["name"] == "Модель не подключена"
        assert models[0]["description"] == "Подключите модель, чтобы запускать проверку документов."

        oversized = _upload(client, workspace_id, b"x" * 33)
        assert oversized.status_code == 413
        document = _upload(client, workspace_id, b"# Input\n")
        assert document.status_code == 201
        unicode_name = "ТЗ MVP.md"
        unicode_document = _upload(client, workspace_id, b"safe", unicode_name)
        assert unicode_document.status_code == 201
        downloaded = client.get(
            f"/v1/workspaces/{workspace_id}/documents/{unicode_document.json()['id']}/content"
        )
        assert downloaded.status_code == 200
        assert downloaded.headers["content-disposition"] == (
            f"attachment; filename*=UTF-8''{quote(unicode_name, safe='')}"
        )
        unsafe = app.state.platform.upload(
            workspace_id,
            'unsafe"\r\nX-Injected: yes.md',
            "text/markdown",
            b"safe",
        )
        unsafe_download = client.get(
            f"/v1/workspaces/{workspace_id}/documents/{unsafe['id']}/content"
        )
        assert "\r" not in unsafe_download.headers["content-disposition"]
        assert "\n" not in unsafe_download.headers["content-disposition"]
        assert "X-Injected:" not in unsafe_download.headers["content-disposition"]
        profile = client.get(f"/v1/workspaces/{workspace_id}/profiles").json()["items"][0]
        response = client.post(
            f"/v1/workspaces/{workspace_id}/review-runs",
            headers={"Idempotency-Key": f"unconfigured-{uuid4().hex}"},
            json={
                "document_id": document.json()["id"],
                "context_document_ids": [],
                "profile": {"id": profile["id"], "version": profile["version"]},
                "model_profile": {"id": models[0]["id"], "version": models[0]["version"]},
                "locale": "ru-RU",
            },
        )

        assert response.status_code == 409
        assert response.json()["code"] == "model_unavailable"
        with psycopg.connect(app.state.platform.database_url) as connection:
            assert connection.execute(
                "SELECT count(*) FROM review_runs WHERE organization_id=%s AND workspace_id=%s",
                (app.state.platform.organization_id, workspace_id),
            ).fetchone() == (runs_before,)


def test_runtime_context_and_dialogue_limits_are_enforced(
    monkeypatch: pytest.MonkeyPatch,
    operator_settings,  # type: ignore[no-untyped-def]
    tmp_path: Path,
) -> None:
    _configure(monkeypatch, operator_settings, tmp_path, unconfigured=False)
    app = create_app(composition="durable")

    with TestClient(app) as client:
        workspace_id = app.state.platform.workspace_id
        trusted = (
            ROOT / "tests/fixtures/synthetic-review/synthetic-spec.md"
        ).read_bytes()
        primary_response = _upload(client, workspace_id, trusted, "synthetic-spec.md")
        assert primary_response.status_code == 201
        primary = primary_response.json()
        context_one = _upload(client, workspace_id, b"one", "one.md")
        context_two = _upload(client, workspace_id, b"two", "two.md")
        assert context_one.status_code == context_two.status_code == 201
        profile = client.get(f"/v1/workspaces/{workspace_id}/profiles").json()["items"][0]
        model = client.get(f"/v1/workspaces/{workspace_id}/model-profiles").json()["items"][0]
        body = {
            "document_id": primary["id"],
            "context_document_ids": [context_one.json()["id"], context_two.json()["id"]],
            "profile": {"id": profile["id"], "version": profile["version"]},
            "model_profile": {"id": model["id"], "version": model["version"]},
            "locale": "en-US",
        }
        limited = client.post(
            f"/v1/workspaces/{workspace_id}/review-runs",
            headers={"Idempotency-Key": f"context-limit-{uuid4().hex}"},
            json=body,
        )
        assert limited.status_code == 400
        assert limited.json()["code"] == "context_limit"

        run = client.post(
            f"/v1/workspaces/{workspace_id}/review-runs",
            headers={"Idempotency-Key": f"bounded-run-{uuid4().hex}"},
            json=body | {"context_document_ids": []},
        )
        assert run.status_code == 202
        report = client.get(
            f"/v1/workspaces/{workspace_id}/review-runs/{run.json()['id']}/report"
        ).json()
        finding_id = report["findings"][0]["id"]
        dialogue_url = (
            f"/v1/workspaces/{workspace_id}/review-runs/{run.json()['id']}"
            f"/findings/{finding_id}/dialogue/turns"
        )
        too_long = client.post(
            dialogue_url,
            headers={"Idempotency-Key": f"long-message-{uuid4().hex}"},
            json={"message": "123456", "expected_revision": 0},
        )
        assert too_long.status_code == 400
        assert too_long.json()["code"] == "invalid_message"

        stale_dialogue = app.state.platform._dialogue(
            workspace_id, run.json()["id"], finding_id
        )
        first = client.post(
            dialogue_url,
            headers={"Idempotency-Key": f"first-message-{uuid4().hex}"},
            json={"message": "12345", "expected_revision": 0},
        )
        assert first.status_code == 202
        second = client.post(
            dialogue_url,
            headers={"Idempotency-Key": f"second-message-{uuid4().hex}"},
            json={"message": "again", "expected_revision": first.json()["revision"]},
        )
        assert second.status_code == 409
        assert second.json()["code"] == "dialogue_blocked"

        original_dialogue = app.state.platform._dialogue
        monkeypatch.setattr(app.state.platform, "_dialogue", lambda *_args: stale_dialogue)
        decision = client.put(
            dialogue_url.removesuffix("/dialogue/turns") + "/decision",
            json={
                "status": "confirmed",
                "reason": "Verified by an analyst.",
                "resolution": None,
                "expected_revision": 0,
            },
        )
        monkeypatch.setattr(app.state.platform, "_dialogue", original_dialogue)
        assert decision.status_code == 200
        persisted = original_dialogue(workspace_id, run.json()["id"], finding_id)
        assert persisted["state"] == "closed"
        assert persisted["turns"] == first.json()["turns"]


def test_review_history_is_chronological_and_paginated(
    monkeypatch: pytest.MonkeyPatch,
    operator_settings,  # type: ignore[no-untyped-def]
    tmp_path: Path,
) -> None:
    _configure(monkeypatch, operator_settings, tmp_path, unconfigured=False)
    app = create_app(composition="durable")

    with TestClient(app) as client:
        workspace_id = app.state.platform.workspace_id
        document = _upload(
            client,
            workspace_id,
            (ROOT / "tests/fixtures/synthetic-review/synthetic-spec.md").read_bytes(),
            "synthetic-spec.md",
        ).json()
        profile = client.get(f"/v1/workspaces/{workspace_id}/profiles").json()["items"][0]
        model = client.get(f"/v1/workspaces/{workspace_id}/model-profiles").json()["items"][0]
        body = {
            "document_id": document["id"],
            "context_document_ids": [],
            "profile": {"id": profile["id"], "version": profile["version"]},
            "model_profile": {"id": model["id"], "version": model["version"]},
            "locale": "en-US",
        }
        created_ids = []
        for ordinal in range(21):
            response = client.post(
                f"/v1/workspaces/{workspace_id}/review-runs",
                headers={"Idempotency-Key": f"history-{uuid4().hex}-{ordinal}"},
                json=body,
            )
            assert response.status_code == 202
            created_ids.append(response.json()["id"])

        url = f"/v1/workspaces/{workspace_id}/review-runs"
        first_page = client.get(url, params={"limit": 20})
        assert first_page.status_code == 200
        first_value = first_page.json()
        assert [item["id"] for item in first_value["items"]] == list(
            reversed(created_ids[1:])
        )
        assert first_value["next_cursor"] is not None

        second_page = client.get(
            url,
            params={"limit": 20, "cursor": first_value["next_cursor"]},
        )
        assert second_page.status_code == 200
        assert [item["id"] for item in second_page.json()["items"]] == [created_ids[0]]
        assert second_page.json()["next_cursor"] is None

        malformed = client.get(url, params={"cursor": "not-a-cursor"})
        assert malformed.status_code == 400
        assert malformed.json()["code"] == "invalid_cursor"
