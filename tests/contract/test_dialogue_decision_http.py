from __future__ import annotations

from pathlib import Path

from httpx import ASGITransport, AsyncClient
from review_api.app import create_app

ROOT = Path(__file__).parents[2]


async def _flow() -> tuple[AsyncClient, str, str, str]:
    client = AsyncClient(transport=ASGITransport(app=create_app(composition="real")), base_url="http://test")
    workspace = (await client.get("/v1/bootstrap")).json()["workspace"]["id"]
    path = ROOT / "tests/fixtures/synthetic-review/synthetic-spec.md"
    document = (
        await client.post(
            f"/v1/workspaces/{workspace}/documents",
            files={"file": (path.name, path.read_bytes(), "text/markdown")},
        )
    ).json()
    profile = (await client.get(f"/v1/workspaces/{workspace}/profiles")).json()["items"][0]
    model = (await client.get(f"/v1/workspaces/{workspace}/model-profiles")).json()["items"][0]
    run = (
        await client.post(
            f"/v1/workspaces/{workspace}/review-runs",
            headers={"Idempotency-Key": "dialogue-run"},
            json={
                "document_id": document["id"],
                "context_document_ids": [],
                "profile": {"id": profile["id"], "version": profile["version"]},
                "model_profile": {"id": model["id"], "version": model["version"]},
                "locale": "en-US",
            },
        )
    ).json()
    finding = (await client.get(f"/v1/workspaces/{workspace}/review-runs/{run['id']}/report")).json()[
        "findings"
    ][0]
    return client, workspace, run["id"], finding["id"]


async def test_dialogue_turn_replay_decision_cas_and_report_immutability() -> None:
    client, workspace, run_id, finding_id = await _flow()
    try:
        base = f"/v1/workspaces/{workspace}/review-runs/{run_id}/findings/{finding_id}"
        before = await client.get(f"/v1/workspaces/{workspace}/review-runs/{run_id}/report")
        dialogue = (await client.get(base + "/dialogue")).json()
        assert dialogue["turn_count"] == 0
        body = {"message": "Propose a testable retry rule.", "expected_revision": 0}
        turn = await client.post(
            base + "/dialogue/turns", headers={"Idempotency-Key": "turn-key-1"}, json=body
        )
        replay = await client.post(
            base + "/dialogue/turns", headers={"Idempotency-Key": "turn-key-1"}, json=body
        )
        assert turn.status_code == replay.status_code == 202
        assert turn.headers["location"] == base + "/dialogue"
        assert replay.headers["location"] == turn.headers["location"]
        assert turn.json()["turns"][0]["id"] == replay.json()["turns"][0]["id"]
        changed = await client.post(
            base + "/dialogue/turns",
            headers={"Idempotency-Key": "turn-key-1"},
            json=body | {"message": "Different"},
        )
        assert changed.status_code == 409
        short_key = await client.post(
            base + "/dialogue/turns", headers={"Idempotency-Key": "short"}, json=body
        )
        assert short_key.status_code == 400
        assert short_key.json()["code"] == "invalid_idempotency_key"
        decision = await client.put(
            base + "/decision",
            json={
                "status": "confirmed",
                "reason": "Needs a boundary.",
                "resolution": "Use three attempts.",
                "expected_revision": 0,
            },
        )
        stale = await client.put(
            base + "/decision",
            json={"status": "rejected", "reason": "No.", "resolution": None, "expected_revision": 0},
        )
        assert decision.status_code == 200
        assert stale.status_code == 409
        after = await client.get(f"/v1/workspaces/{workspace}/review-runs/{run_id}/report")
        assert before.content == after.content
        assert before.headers["etag"] == after.headers["etag"]
        assert (await client.get(base + "/dialogue")).json()["blocked_reason"] == "human_decision_recorded"
    finally:
        await client.aclose()
