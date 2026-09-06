import pytest
from fastapi.testclient import TestClient
from review_api.app import create_app
from test_document_cycle import review, upload


@pytest.fixture(params=["fixture", "durable"])
def unified_client(request):
    app = create_app() if request.param == "fixture" else request.getfixturevalue("durable_app")
    return TestClient(app)


def test_explicit_completion_persists_and_decision_edit_invalidates_it(unified_client):
    client = unified_client
    workspace, document = upload(client)
    run = review(client, workspace, document)
    base = f"/v1/workspaces/{workspace}/review-runs/{run['id']}"
    report_bytes = client.get(base + "/report").content
    report = client.get(base + "/report").json()
    cycle = client.get(base + "/review-cycle").json()
    assert (
        client.post(
            base + "/review-cycle/complete", json={"expected_revision": cycle["revision"]}
        ).status_code
        == 409
    )
    for finding in report["findings"]:
        result = client.put(
            base + f"/findings/{finding['id']}/decision",
            json={
                "status": "rejected",
                "reason": "Already specified in the synthetic requirements.",
                "resolution": None,
                "expected_revision": 0,
            },
        )
        assert result.status_code == 200, result.text
    cycle = client.get(base + "/review-cycle").json()
    done = client.post(base + "/review-cycle/complete", json={"expected_revision": cycle["revision"]})
    assert done.status_code == 200, done.text
    assert done.json()["completion"]["actor"]
    assert client.get(base + "/review-cycle").json()["completion"] == done.json()["completion"]
    finding = report["findings"][0]
    client.put(
        base + f"/findings/{finding['id']}/decision",
        json={
            "status": "needs_context",
            "reason": "Clarify the schedule.",
            "resolution": None,
            "expected_revision": 1,
        },
    )
    assert client.get(base + "/review-cycle").json()["completion"] is None
    assert client.get(base + f"/findings/{finding['id']}/dialogue").json()["can_send_message"] is True
    assert client.get(base + "/report").content == report_bytes


def test_dialogue_attachment_is_retained_in_turn(unified_client):
    client = unified_client
    workspace, document = upload(client)
    run = review(client, workspace, document)
    base = f"/v1/workspaces/{workspace}/review-runs/{run['id']}"
    finding = client.get(base + "/report").json()["findings"][0]
    _, attachment = upload(client)
    review(client, workspace, attachment)
    path = base + f"/findings/{finding['id']}/dialogue"
    dialogue = client.get(path).json()
    response = client.post(
        path + "/turns",
        headers={"Idempotency-Key": "unified-attachment"},
        json={
            "message": "See the attached requirements.",
            "expected_revision": dialogue["revision"],
            "attachment_document_ids": [attachment["id"]],
        },
    )
    assert response.status_code == 202, response.text
    assert response.json()["turns"][-1]["attachment_document_ids"] == [attachment["id"]]
    platform = client.app.state.platform
    if hasattr(platform, "dialogue_preparation"):
        prepared = platform.dialogue_preparation(
            workspace, run["id"], finding["id"], response.json()["turns"][-1]["id"]
        )
        assert attachment["id"] in {source["document_id"] for source in prepared["sources"]}
    invalid = client.post(
        path + "/turns",
        headers={"Idempotency-Key": "unknown-attachment"},
        json={
            "message": "Missing file",
            "expected_revision": response.json()["revision"],
            "attachment_document_ids": ["99999999-0000-4000-8000-000000000001"],
        },
    )
    assert invalid.status_code == 404
