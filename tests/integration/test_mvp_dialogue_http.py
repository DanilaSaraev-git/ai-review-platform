from __future__ import annotations

import hashlib
from uuid import uuid4

import psycopg

from tests.integration.test_mvp_review_http import create_run, upload


def _deferred_row_counts(durable_app) -> tuple[int, int, int]:  # type: ignore[no-untyped-def]
    with psycopg.connect(durable_app.state.platform.database_url) as connection:
        row = connection.execute(
            "SELECT (SELECT count(*) FROM job_outbox),"
            "(SELECT count(*) FROM review_run_executions),"
            "(SELECT count(*) FROM generation_attempts)"
        ).fetchone()
    assert row is not None
    return row


def test_dialogue_and_human_decision_do_not_mutate_report(
    durable_client, durable_app  # type: ignore[no-untyped-def]
) -> None:
    deferred_before = _deferred_row_counts(durable_app)
    workspace_id = durable_client.get("/v1/bootstrap").json()["workspace"]["id"]
    document = upload(durable_client, workspace_id, "synthetic-spec.md")
    run, _ = create_run(durable_client, workspace_id, document["id"], f"dialogue-run-{uuid4()}")
    report_url = f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/report"
    before = durable_client.get(report_url)
    finding_id = before.json()["findings"][0]["id"]
    base = f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/findings/{finding_id}"
    dialogue = durable_client.get(f"{base}/dialogue").json()
    body = {"message": "Explain the implementation risk.", "expected_revision": dialogue["revision"]}
    key = f"turn-{uuid4()}"

    created = durable_client.post(
        f"{base}/dialogue/turns", headers={"Idempotency-Key": key}, json=body
    )
    replay = durable_client.post(
        f"{base}/dialogue/turns", headers={"Idempotency-Key": key}, json=body
    )

    assert created.status_code == 202, created.text
    assert created.headers["location"] == f"{base}/dialogue"
    assert replay.status_code == 202, replay.text
    assert len(created.json()["turns"]) == 1
    assert len(replay.json()["turns"]) == 1
    assert created.json()["turns"][0]["state"] == "completed"
    assert created.json()["turns"][0]["assistant_response"]

    mismatch = durable_client.post(
        f"{base}/dialogue/turns",
        headers={"Idempotency-Key": key},
        json=body | {"message": "Different body."},
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "idempotency_conflict"

    decision = durable_client.put(
        f"{base}/decision",
        json={
            "status": "confirmed",
            "reason": "Confirmed by the analyst.",
            "resolution": "Clarify the retry boundary.",
            "expected_revision": 0,
        },
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["status"] == "confirmed"
    state = durable_client.get(
        f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/finding-states"
    ).json()["items"][0]
    assert state["dialogue"]["can_send_message"] is False
    assert state["dialogue"]["blocked_reason"] == "human_decision_recorded"

    stale = durable_client.put(
        f"{base}/decision",
        json={
            "status": "rejected",
            "reason": "stale",
            "resolution": None,
            "expected_revision": 0,
        },
    )
    assert stale.status_code == 409

    after = durable_client.get(report_url)
    assert after.content == before.content
    assert hashlib.sha256(after.content).digest() == hashlib.sha256(before.content).digest()
    assert after.headers["etag"] == before.headers["etag"]
    deferred_after = _deferred_row_counts(durable_app)
    assert deferred_after == (deferred_before[0], deferred_before[1] + 1, deferred_before[2])
