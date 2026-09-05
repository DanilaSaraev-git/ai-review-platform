from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

ROOT = Path(__file__).parents[2]


async def _upload(client: AsyncClient, workspace: str, path: Path) -> str:
    response = await client.post(
        f"/v1/workspaces/{workspace}/documents",
        files={"file": (path.name, path.read_bytes(), "text/markdown")},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_create_run_replay_conflict_and_context_limit(client: AsyncClient) -> None:
    bootstrap = (await client.get("/v1/bootstrap")).json()
    workspace = bootstrap["workspace"]["id"]
    document_id = await _upload(client, workspace, ROOT / "tests/fixtures/synthetic-review/synthetic-spec.md")
    profile = (await client.get(f"/v1/workspaces/{workspace}/profiles")).json()["items"][0]
    model = (await client.get(f"/v1/workspaces/{workspace}/model-profiles")).json()["items"][0]
    body = {
        "document_id": document_id,
        "context_document_ids": [],
        "profile": {"id": profile["id"], "version": profile["version"]},
        "model_profile": {"id": model["id"], "version": model["version"]},
        "locale": "ru-RU",
    }
    first = await client.post(
        f"/v1/workspaces/{workspace}/review-runs", json=body, headers={"Idempotency-Key": "same-key"}
    )
    replay = await client.post(
        f"/v1/workspaces/{workspace}/review-runs", json=body, headers={"Idempotency-Key": "same-key"}
    )
    conflict = await client.post(
        f"/v1/workspaces/{workspace}/review-runs",
        json=body | {"locale": "en-US"},
        headers={"Idempotency-Key": "same-key"},
    )
    assert first.status_code == replay.status_code == 202
    assert first.json()["id"] == replay.json()["id"]
    assert first.headers["location"] == (
        f"/v1/workspaces/{workspace}/review-runs/{first.json()['id']}"
    )
    assert replay.headers["location"] == first.headers["location"]
    assert conflict.status_code == 409
    short_key = await client.post(
        f"/v1/workspaces/{workspace}/review-runs",
        json=body,
        headers={"Idempotency-Key": "short"},
    )
    assert short_key.status_code == 400
    assert short_key.json()["code"] == "invalid_idempotency_key"
    too_many = body | {"context_document_ids": [document_id] * 51}
    assert (
        await client.post(
            f"/v1/workspaces/{workspace}/review-runs",
            json=too_many,
            headers={"Idempotency-Key": "many-keys"},
        )
    ).status_code == 400


async def test_malformed_run_is_safe_400_and_attempt_outbox_is_exact(client: AsyncClient) -> None:
    workspace = (await client.get("/v1/bootstrap")).json()["workspace"]["id"]
    malformed = await client.post(
        f"/v1/workspaces/{workspace}/review-runs", json={}, headers={"Idempotency-Key": "bad"}
    )
    assert malformed.status_code == 400
    assert malformed.headers["content-type"].startswith("application/problem+json")
    platform = client._transport.app.state.platform  # type: ignore[attr-defined]
    # Successful run in the preceding test is not shared across fixture instances; create one here.
    document_id = await _upload(client, workspace, ROOT / "tests/fixtures/synthetic-review/synthetic-spec.md")
    profile = (await client.get(f"/v1/workspaces/{workspace}/profiles")).json()["items"][0]
    body = {
        "document_id": document_id,
        "context_document_ids": [],
        "profile": {"id": profile["id"], "version": profile["version"]},
        "model_profile": {"id": "deterministic-v1", "version": "1.0.0"},
        "locale": "en-US",
    }
    await client.post(
        f"/v1/workspaces/{workspace}/review-runs",
        json=body,
        headers={"Idempotency-Key": "outbox-key"},
    )
    assert len(platform.review_executions) == len(platform.outbox) == 1
    execution = next(iter(platform.review_executions.values()))
    outbox = next(iter(platform.outbox.values()))
    assert outbox["payload"]["review_execution_id"] == execution["id"]
