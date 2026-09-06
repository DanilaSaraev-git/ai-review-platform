from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from uuid import uuid4

import anyio
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from review_api.app import create_app
from review_cli.commands.model_probe import probe_configured_models
from review_runtime.config.model_profiles import ModelProfile, profile_config_digest
from review_runtime.config.settings import OperatorSettings

from tests.integration.fake_model_provider import FakeModelProvider, ScriptedReply, chat_completion
from tests.integration.test_ml_review_http import FIXTURES, _configure_ml, _request_review


def _reference(profile: ModelProfile) -> dict[str, str]:
    return {"id": profile.id, "version": profile.version}


def _write_profiles(path: Path, profiles: tuple[ModelProfile, ...]) -> None:
    path.write_text(json.dumps({"profiles": [profile.model_dump(mode="json") for profile in profiles]}))


def _configure_two_models(
    monkeypatch: pytest.MonkeyPatch, settings: OperatorSettings, tmp_path: Path
) -> tuple[ModelProfile, ModelProfile]:
    _configure_ml(monkeypatch, settings, tmp_path)
    path = tmp_path / "model-profile.json"
    template = json.loads(path.read_text())
    profiles = tuple(
        ModelProfile.model_validate(
            {
                **template,
                "id": f"synthetic-{name}-{uuid4().hex}",
                "model": f"synthetic-{name}",
                "chat_url": f"https://model.invalid/{name}/chat/completions",
                "probe": {
                    "mode": "models",
                    "url": "https://model.invalid/models",
                    "timeout_seconds": 5,
                    "success_ttl_seconds": 300,
                },
            }
        )
        for name in ("alpha", "beta")
    )
    _write_profiles(path, profiles)
    monkeypatch.setenv("REVIEW_MODEL_PROFILE_ID", profiles[0].id)
    return profiles[0], profiles[1]


def _observe(app: FastAPI, profile: ModelProfile, *, available: bool = True) -> None:
    app.state.platform.observe_model_profile(
        _reference(profile),
        state="available" if available else "unavailable",
        reason_code=None if available else "operator_unavailable",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )


def _dialogue_output() -> str:
    output = json.loads((FIXTURES / "dialogue-response.json").read_text())
    output["anchors"] = output["anchors"][:1]
    return json.dumps(output)


def _turn(client: TestClient, base: str, *, revision: int = 0) -> httpx.Response:
    return client.post(
        f"{base}/dialogue/turns",
        headers={"Idempotency-Key": f"multi-model-dialogue-{uuid4().hex}"},
        json={"message": "Clarify the synthetic schedule.", "expected_revision": revision},
    )


def _retry(client: TestClient, base: str, turn_id: str, revision: int) -> httpx.Response:
    return client.post(
        f"{base}/dialogue/turns/{turn_id}/retry",
        headers={"Idempotency-Key": f"multi-model-retry-{uuid4().hex}"},
        json={"expected_revision": revision},
    )


def test_review_selects_each_exact_model_and_records_its_snapshot(
    monkeypatch: pytest.MonkeyPatch, operator_settings: OperatorSettings, tmp_path: Path
) -> None:
    alpha, beta = _configure_two_models(monkeypatch, operator_settings, tmp_path)
    selected = (beta, alpha)
    provider = FakeModelProvider(
        [
            ScriptedReply(chat_completion((FIXTURES / "review-response.json").read_text(), model=item.model))
            for item in selected
        ]
    )
    app = create_app(composition="ml", model_transport=provider.transport)
    for profile in (alpha, beta):
        _observe(app, profile)

    with TestClient(app) as client:
        workspace_id = app.state.platform.workspace_id
        catalogue = client.get(f"/v1/workspaces/{workspace_id}/model-profiles").json()["items"]
        assert {(item["id"], item["availability"]) for item in catalogue} == {
            (alpha.id, "available"),
            (beta.id, "available"),
        }
        for index, profile in enumerate(selected):
            response = _request_review(client, workspace_id, _reference(profile))
            assert response.status_code == 202, response.text
            run = response.json()
            assert run["state"] == "completed", response.text
            expected_snapshot = {**_reference(profile), "config_sha256": profile_config_digest(profile)}
            assert run["execution_snapshot"]["model_profile"] == expected_snapshot
            sent = provider.requests[index]
            assert str(sent.url) == profile.chat_url
            assert json.loads(sent.content)["model"] == profile.model
            report = client.get(f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/report")
            assert report.status_code == 200
            assert report.json()["provenance"]["execution_snapshot"]["model_profile"] == expected_snapshot
        assert "synthetic-secret" not in response.text
    assert provider.call_count == 2


def test_dialogue_and_same_turn_retry_remain_pinned_after_restart_and_default_change(
    monkeypatch: pytest.MonkeyPatch, operator_settings: OperatorSettings, tmp_path: Path
) -> None:
    alpha, beta = _configure_two_models(monkeypatch, operator_settings, tmp_path)
    initial = FakeModelProvider(
        [
            ScriptedReply(chat_completion((FIXTURES / "review-response.json").read_text())),
            ScriptedReply(chat_completion("not-json")),
        ]
    )
    app = create_app(composition="ml", model_transport=initial.transport)
    for profile in (alpha, beta):
        _observe(app, profile)
    with TestClient(app) as client:
        workspace_id = app.state.platform.workspace_id
        response = _request_review(client, workspace_id, _reference(alpha))
        assert response.status_code == 202, response.text
        run = response.json()
        assert run["state"] == "completed", response.text
        report_url = f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/report"
        before = client.get(report_url)
        finding_id = before.json()["findings"][0]["id"]
        base = f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/findings/{finding_id}"
        failed = _turn(client, base)
        assert failed.status_code == 202, failed.text
        failed_turn = failed.json()["turns"][0]
        assert failed_turn["state"] == "failed"

    monkeypatch.setenv("REVIEW_MODEL_PROFILE_ID", beta.id)
    restarted_provider = FakeModelProvider(
        [ScriptedReply(chat_completion(_dialogue_output())) for _ in range(2)]
    )
    restarted = create_app(composition="ml", model_transport=restarted_provider.transport)
    with TestClient(restarted) as client:
        retried = _retry(client, base, failed_turn["id"], failed.json()["revision"])
        assert retried.status_code == 202, retried.text
        assert retried.json()["turns"][0]["id"] == failed_turn["id"]
        assert retried.json()["turns"][0]["state"] == "completed", retried.text
        followup = _turn(client, base, revision=retried.json()["revision"])
        assert followup.status_code == 202, followup.text
        assert followup.json()["turns"][-1]["state"] == "completed", followup.text
        after = client.get(report_url)
        assert after.content == before.content
        assert after.headers["etag"] == before.headers["etag"]
    assert initial.call_count == restarted_provider.call_count == 2
    for sent in (*initial.requests, *restarted_provider.requests):
        assert json.loads(sent.content)["model"] == alpha.model
        assert str(sent.url) == alpha.chat_url


def test_removed_model_blocks_review_dialogue_and_retry_without_fallback_or_report_mutation(
    monkeypatch: pytest.MonkeyPatch, operator_settings: OperatorSettings, tmp_path: Path
) -> None:
    alpha, beta = _configure_two_models(monkeypatch, operator_settings, tmp_path)
    initial = FakeModelProvider(
        [
            ScriptedReply(chat_completion((FIXTURES / "review-response.json").read_text())),
            ScriptedReply(chat_completion("not-json")),
        ]
    )
    app = create_app(composition="ml", model_transport=initial.transport)
    for profile in (alpha, beta):
        _observe(app, profile)
    with TestClient(app) as client:
        workspace_id = app.state.platform.workspace_id
        response = _request_review(client, workspace_id, _reference(alpha))
        assert response.status_code == 202, response.text
        run = response.json()
        assert run["state"] == "completed", response.text
        report_url = f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/report"
        before = client.get(report_url)
        finding_id = before.json()["findings"][0]["id"]
        base = f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/findings/{finding_id}"
        failed = _turn(client, base)
        assert failed.status_code == 202, failed.text
        failed_turn = failed.json()["turns"][0]
        assert failed_turn["state"] == "failed"

    _write_profiles(tmp_path / "model-profile.json", (beta,))
    monkeypatch.setenv("REVIEW_MODEL_PROFILE_ID", beta.id)
    provider = FakeModelProvider([])
    restarted = create_app(composition="ml", model_transport=provider.transport)
    with TestClient(restarted) as client:
        catalogue = client.get(f"/v1/workspaces/{workspace_id}/model-profiles").json()["items"]
        assert [item["id"] for item in catalogue] == [beta.id]
        for reference in (
            _reference(alpha),
            {"id": "synthetic-unknown-model", "version": "1.0.0"},
            {"id": "deterministic-v1", "version": "1.0.0"},
        ):
            rejected = _request_review(client, workspace_id, reference)
            assert rejected.status_code == 404, rejected.text
            assert rejected.json()["code"] == "not_found"
        for rejected in (
            _turn(client, base, revision=failed.json()["revision"]),
            _retry(client, base, failed_turn["id"], failed.json()["revision"]),
        ):
            assert rejected.status_code == 409, rejected.text
            assert rejected.json()["code"] == "model_unavailable"
        dialogue = client.get(f"{base}/dialogue").json()
        assert dialogue["revision"] == failed.json()["revision"]
        assert dialogue["turns"] == failed.json()["turns"]
        after = client.get(report_url)
        assert after.content == before.content
        assert after.headers["etag"] == before.headers["etag"]
    assert provider.call_count == 0


def test_availability_and_authentication_failure_are_independent_per_model(
    monkeypatch: pytest.MonkeyPatch, operator_settings: OperatorSettings, tmp_path: Path
) -> None:
    alpha, beta = _configure_two_models(monkeypatch, operator_settings, tmp_path)
    provider = FakeModelProvider(
        [
            ScriptedReply(httpx.Response(401, text="synthetic-secret must not be exposed")),
            ScriptedReply(chat_completion((FIXTURES / "review-response.json").read_text())),
        ]
    )
    app = create_app(composition="ml", model_transport=provider.transport)
    _observe(app, alpha)
    _observe(app, beta, available=False)
    with TestClient(app) as client:
        workspace_id = app.state.platform.workspace_id
        unavailable = _request_review(client, workspace_id, _reference(beta))
        assert unavailable.status_code == 409, unavailable.text
        assert unavailable.json()["code"] == "model_unavailable"
        assert provider.call_count == 0
        failed = _request_review(client, workspace_id, _reference(alpha))
        assert failed.status_code == 202, failed.text
        assert failed.json()["state"] == "failed"
        assert failed.json()["error"]["code"] == "model_unavailable"
        assert "synthetic-secret" not in failed.text
        _observe(app, beta)
        completed = _request_review(client, workspace_id, _reference(beta))
        assert completed.status_code == 202, completed.text
        assert completed.json()["state"] == "completed", completed.text
        catalogue = client.get(f"/v1/workspaces/{workspace_id}/model-profiles").json()["items"]
        assert {item["id"]: item["availability"] for item in catalogue} == {
            alpha.id: "unavailable",
            beta.id: "available",
        }
    assert [json.loads(request.content)["model"] for request in provider.requests] == [
        alpha.model,
        beta.model,
    ]


def test_non_generative_probe_persists_availability_for_each_model(
    monkeypatch: pytest.MonkeyPatch, operator_settings: OperatorSettings, tmp_path: Path
) -> None:
    alpha, beta = _configure_two_models(monkeypatch, operator_settings, tmp_path)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": [{"id": beta.model}]})

    observations = anyio.run(
        partial(
            probe_configured_models,
            settings=OperatorSettings(),  # type: ignore[call-arg]
            transport=httpx.MockTransport(handler),
        )
    )
    assert [(item.profile_id, item.state, item.reason_code) for item in observations] == [
        (alpha.id, "unavailable", "model_not_found"),
        (beta.id, "available", None),
    ]
    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/models"),
        ("GET", "/models"),
    ]

    app = create_app(composition="ml", model_transport=FakeModelProvider([]).transport)
    with TestClient(app) as client:
        workspace_id = app.state.platform.workspace_id
        catalogue = client.get(f"/v1/workspaces/{workspace_id}/model-profiles").json()["items"]
    assert {item["id"]: item["availability"] for item in catalogue} == {
        alpha.id: "unavailable",
        beta.id: "available",
    }


@pytest.mark.asyncio
async def test_concurrency_budget_is_shared_across_distinct_model_profiles(
    monkeypatch: pytest.MonkeyPatch, operator_settings: OperatorSettings, tmp_path: Path
) -> None:
    profiles = _configure_two_models(monkeypatch, operator_settings, tmp_path)
    policy = json.loads(Path(operator_settings.runtime_config_path).read_text())
    policy["budgets"]["max_parallel_model_calls"] = 1
    policy_path = tmp_path / "runtime-config.json"
    policy_path.write_text(json.dumps(policy))
    monkeypatch.setenv("REVIEW_RUNTIME_CONFIG_PATH", str(policy_path))
    replies = [
        ScriptedReply(
            chat_completion((FIXTURES / "review-response.json").read_text()),
            release=asyncio.Event(),
        )
        for _ in profiles
    ]
    provider = FakeModelProvider(replies)
    app = create_app(composition="ml", model_transport=provider.transport)
    for profile in profiles:
        _observe(app, profile)
    workspace_id = app.state.platform.workspace_id
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            review_profile = (await client.get(f"/v1/workspaces/{workspace_id}/profiles")).json()["items"][0]
            documents = []
            for ordinal in range(2):
                uploaded = await client.post(
                    f"/v1/workspaces/{workspace_id}/documents",
                    files={
                        "file": (
                            f"synthetic-{ordinal}.md",
                            (FIXTURES / "primary.md").read_bytes(),
                            "text/markdown",
                        )
                    },
                )
                assert uploaded.status_code == 201, uploaded.text
                documents.append(uploaded.json()["id"])

            async def run(index: int) -> httpx.Response:
                return await client.post(
                    f"/v1/workspaces/{workspace_id}/review-runs",
                    headers={"Idempotency-Key": f"multi-model-concurrent-{uuid4().hex}"},
                    json={
                        "document_id": documents[index],
                        "context_document_ids": [],
                        "profile": {"id": review_profile["id"], "version": review_profile["version"]},
                        "model_profile": _reference(profiles[index]),
                        "locale": "en-US",
                    },
                )

            tasks = [asyncio.create_task(run(index)) for index in range(2)]
            try:
                await asyncio.wait_for(replies[0].entered.wait(), timeout=5)
                with pytest.raises(TimeoutError):
                    await asyncio.wait_for(replies[1].entered.wait(), timeout=0.2)
                assert provider.call_count == 1
                assert (await client.get("/health/live")).status_code == 200
                assert replies[0].release is not None
                replies[0].release.set()
                await asyncio.wait_for(replies[1].entered.wait(), timeout=5)
                assert replies[1].release is not None
                replies[1].release.set()
                responses = await asyncio.wait_for(asyncio.gather(*tasks), timeout=5)
                for response in responses:
                    assert response.status_code == 202, response.text
                    assert response.json()["state"] == "completed", response.text
            finally:
                for reply in replies:
                    assert reply.release is not None
                    reply.release.set()
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
    assert {json.loads(request.content)["model"] for request in provider.requests} == {
        profile.model for profile in profiles
    }
