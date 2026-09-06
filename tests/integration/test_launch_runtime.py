from __future__ import annotations

import json
from functools import partial
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import anyio
import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient
from review_api.app import create_app
from review_cli.commands.model_probe import probe_configured_model
from review_runtime.config.settings import OperatorSettings

from tests.integration.fake_model_provider import (
    FakeModelProvider,
    ScriptedReply,
    chat_completion,
)

ROOT = Path(__file__).parents[2]


def _configure(
    monkeypatch: pytest.MonkeyPatch,
    operator_settings,  # type: ignore[no-untyped-def]
    tmp_path: Path,
    *,
    unconfigured: bool,
    max_upload_bytes: int | None = None,
) -> None:
    config = json.loads(
        (ROOT / "deploy/compose/config/runtime-config.synthetic.v1.json").read_text()
    )
    config["budgets"].update(
        max_upload_bytes=(
            max_upload_bytes if max_upload_bytes is not None else 32 if unconfigured else 52_428_800
        ),
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


def test_unconfigured_deployment_can_select_probe_and_run_one_external_model(
    monkeypatch: pytest.MonkeyPatch,
    operator_settings,  # type: ignore[no-untyped-def]
    tmp_path: Path,
) -> None:
    _configure(
        monkeypatch,
        operator_settings,
        tmp_path,
        unconfigured=True,
        max_upload_bytes=52_428_800,
    )
    unconfigured = create_app(composition="unconfigured")
    with TestClient(unconfigured) as client:
        workspace_id = unconfigured.state.platform.workspace_id
        initial = client.get(f"/v1/workspaces/{workspace_id}/model-profiles").json()["items"]
        assert len(initial) == 1
        assert initial[0]["availability"] == "unavailable"

    external_id = f"production-test-{uuid4().hex}"
    profile = json.loads(
        (ROOT / "deploy/compose/config/model-profile.external.example.json").read_text()
    )
    profile.update(
        id=external_id,
        provider="test-provider",
        model="test-model",
        chat_url="https://provider.test/chat/completions",
        probe={
            "mode": "health",
            "url": "https://provider.test/health",
            "timeout_seconds": 5,
            "success_ttl_seconds": 300,
        },
    )
    profile_path = tmp_path / "model-profile.json"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    credential_path = tmp_path / "model-credential"
    credential_path.write_text("probe-secret", encoding="utf-8")
    monkeypatch.setenv("REVIEW_COMPOSITION", "ml")
    monkeypatch.setenv("REVIEW_MODEL_PROFILE_ID", external_id)
    monkeypatch.setenv("REVIEW_MODEL_PROFILE_PATH", str(profile_path))
    monkeypatch.setenv("REVIEW_MODEL_CREDENTIAL_PATH", str(credential_path))
    monkeypatch.setenv("REVIEW_SKILL_PACKAGE_PATH", str(ROOT / "tests/fixtures/ml-integration/skill"))

    generation = FakeModelProvider(
        [
            ScriptedReply(
                chat_completion(
                    (ROOT / "tests/fixtures/ml-integration/review-response.json").read_text()
                )
            )
        ]
    )
    app = create_app(composition="ml", model_transport=generation.transport)
    probe_requests: list[httpx.Request] = []

    def probe_handler(request: httpx.Request) -> httpx.Response:
        probe_requests.append(request)
        return httpx.Response(200, json={"status": "ok"})

    with TestClient(app) as client:
        listed = client.get(f"/v1/workspaces/{workspace_id}/model-profiles").json()["items"]
        assert [(item["id"], item["availability"]) for item in listed] == [
            (external_id, "unavailable")
        ]
        assert generation.call_count == 0

        observation = anyio.run(
            partial(
                probe_configured_model,
                settings=OperatorSettings(),  # type: ignore[call-arg]
                transport=httpx.MockTransport(probe_handler),
            )
        )
        assert observation.state == "available"
        assert [(request.method, request.url.path) for request in probe_requests] == [
            ("GET", "/health")
        ]
        assert probe_requests[0].headers["authorization"] == "Bearer probe-secret"
        assert generation.call_count == 0
        listed = client.get(f"/v1/workspaces/{workspace_id}/model-profiles").json()["items"]
        assert [(item["id"], item["availability"]) for item in listed] == [
            (external_id, "available")
        ]

        document = _upload(
            client,
            workspace_id,
            (ROOT / "tests/fixtures/ml-integration/primary.md").read_bytes(),
            "primary.md",
        ).json()
        review_profile = client.get(f"/v1/workspaces/{workspace_id}/profiles").json()["items"][0]
        run = client.post(
            f"/v1/workspaces/{workspace_id}/review-runs",
            headers={"Idempotency-Key": f"external-run-{uuid4().hex}"},
            json={
                "document_id": document["id"],
                "context_document_ids": [],
                "profile": {"id": review_profile["id"], "version": review_profile["version"]},
                "model_profile": {"id": external_id, "version": profile["version"]},
                "locale": "ru-RU",
            },
        )
        assert run.status_code == 202
        assert run.json()["state"] == "completed"
        assert generation.call_count == 1

        failed = anyio.run(
            partial(
                probe_configured_model,
                settings=OperatorSettings(),  # type: ignore[call-arg]
                transport=httpx.MockTransport(lambda _request: httpx.Response(503)),
            )
        )
        assert failed.state == "unavailable"
        listed = client.get(f"/v1/workspaces/{workspace_id}/model-profiles").json()["items"]
        assert [(item["id"], item["availability"]) for item in listed] == [
            (external_id, "unavailable")
        ]
