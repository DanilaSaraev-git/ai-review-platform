from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from review_api.app import create_app

ROOT = Path(__file__).parents[2]
CONTENT = (ROOT / "tests/fixtures/synthetic-review/synthetic-spec.md").read_bytes()


@pytest.fixture(params=["fixture", "durable"])
def cycle_client(request: pytest.FixtureRequest):  # type: ignore[no-untyped-def]
    app = create_app() if request.param == "fixture" else request.getfixturevalue("durable_app")
    with TestClient(app) as client:
        yield client


def upload(client: TestClient) -> tuple[str, dict]:
    workspace = client.get("/v1/bootstrap").json()["workspace"]["id"]
    result = client.post(
        f"/v1/workspaces/{workspace}/documents", files={"file": ("synthetic.md", CONTENT, "text/markdown")}
    )
    assert result.status_code == 201, result.text
    return workspace, result.json()


def review(client: TestClient, workspace: str, document: dict, *, contexts: list[str] | None = None) -> dict:
    base = f"/v1/workspaces/{workspace}"
    profile = client.get(base + "/profiles").json()["items"][0]
    model = client.get(base + "/model-profiles").json()["items"][0]
    result = client.post(
        base + "/review-runs",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "document_id": document["id"],
            "context_document_ids": contexts or [],
            "profile": {"id": profile["id"], "version": profile["version"]},
            "model_profile": {"id": model["id"], "version": model["version"]},
            "locale": "ru-RU",
        },
    )
    assert result.status_code == 202, result.text
    assert result.json()["state"] == "completed", result.text
    return result.json()


def test_family_two_versions_three_runs_and_idempotent_upload(cycle_client: TestClient) -> None:
    client = cycle_client
    workspace, original = upload(client)
    base = f"/v1/workspaces/{workspace}"
    initial = client.get(base + f"/documents/{original['id']}/family")
    assert initial.status_code == 200, initial.text
    family_id = initial.json()["family_id"]
    first = review(client, workspace, original)
    report = client.get(base + f"/review-runs/{first['id']}/report")
    key = str(uuid4())
    url = base + f"/document-families/{family_id}/versions"
    request = {
        "headers": {"Idempotency-Key": key},
        "files": {"file": ("synthetic-v2.md", CONTENT, "text/markdown")},
    }
    added = client.post(url, **request)
    assert added.status_code == 201, added.text
    assert client.post(url, **request).json() == added.json()
    version = added.json()
    assert version["version_number"] == 2 and version["unchanged_from_previous"] is True
    second = review(client, workspace, version["document"])
    third = review(client, workspace, version["document"])
    assert client.get(url).json()["items"][0]["version_number"] == 2
    assert len(client.get(base + f"/document-families/{family_id}/review-runs").json()["items"]) == 3
    cycle = client.get(base + f"/review-runs/{third['id']}/review-cycle").json()
    assert cycle["baseline_run_id"] == second["id"]
    assert cycle["entries"][0]["status"] == "persisting"
    assert client.get(base + f"/review-runs/{first['id']}/report").content == report.content
    assert client.get(base + f"/review-runs/{first['id']}/report").headers["etag"] == report.headers["etag"]
    assert client.get(base + f"/documents/{original['id']}/content").content == CONTENT


def test_cycle_resolution_revision_retry_and_pdf_preserve_current_state(cycle_client: TestClient) -> None:
    client = cycle_client
    workspace, document = upload(client)
    base = f"/v1/workspaces/{workspace}"
    run = review(client, workspace, document)
    url = base + f"/review-runs/{run['id']}/review-cycle"
    cycle = client.get(url).json()
    entry = cycle["entries"][0]
    body = {"status": "resolved", "reason": "Синтетическое подтверждение аналитика", "expected_revision": 0}
    updated = client.put(url + f"/issues/{entry['issue_id']}/resolution", json=body)
    assert updated.status_code == 200, updated.text
    assert client.put(url + f"/issues/{entry['issue_id']}/resolution", json=body).status_code == 409
    snapshot = deepcopy(updated.json())
    replay = client.post(url + "/compare", json={"expected_revision": snapshot["revision"]})
    assert replay.status_code == 200 and replay.json() == snapshot
    pdf = client.get(base + f"/review-runs/{run['id']}/report.pdf")
    assert pdf.status_code == 200, pdf.text[:100]
    assert pdf.content.startswith(b"%PDF-")
    assert "attachment" in pdf.headers["content-disposition"]


def test_upload_key_is_workspace_scoped_and_rejects_different_family(cycle_client: TestClient) -> None:
    client = cycle_client
    workspace, first = upload(client)
    _, second = upload(client)
    base = f"/v1/workspaces/{workspace}"
    key = str(uuid4())
    request = {"headers": {"Idempotency-Key": key}, "files": {"file": ("v2.md", CONTENT, "text/markdown")}}
    first_family = client.get(base + f"/documents/{first['id']}/family").json()["family_id"]
    second_family = client.get(base + f"/documents/{second['id']}/family").json()["family_id"]
    result = client.post(base + f"/document-families/{first_family}/versions", **request)
    assert result.status_code == 201, result.text
    rejected = client.post(base + f"/document-families/{second_family}/versions", **request)
    assert rejected.status_code == 409 and rejected.json()["code"] == "idempotency_conflict"
    assert len(client.get(base + f"/document-families/{second_family}/versions").json()["items"]) == 1


def test_comparison_failure_does_not_block_published_report_or_pdf(
    cycle_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = cycle_client
    workspace, document = upload(client)
    platform = client.app.state.platform
    module = (
        "review_runtime.postgres.document_cycles"
        if hasattr(platform, "database_url")
        else "review_core.application.document_cycle_memory"
    )

    calls = 0

    def broken(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise RuntimeError("Synthetic comparison failure")

    from importlib import import_module

    working = import_module(module).build_cycle
    monkeypatch.setattr(module + ".build_cycle", broken)
    run = review(client, workspace, document)
    base = f"/v1/workspaces/{workspace}/review-runs/{run['id']}"
    assert client.get(base + "/report").status_code == 200
    result = client.get(base + "/review-cycle")
    assert result.status_code == 200 and result.json()["status"] == "unavailable"
    assert result.json()["limitations"] == ["comparison_failed"]
    assert client.get(base + "/report.pdf").status_code == 200
    assert calls == 1
    monkeypatch.setattr(module + ".build_cycle", working)
    retried = client.post(base + "/review-cycle/compare", json={"expected_revision": 0})
    assert retried.status_code == 200 and retried.json()["status"] == "ready"


def test_baseline_is_fixed_before_a_parallel_run_finishes() -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from review_core.application.platform import ReviewPlatform
    from review_runtime.fakes.review_executor import TrustedFixtureReviewExecutor

    executor = TrustedFixtureReviewExecutor(ROOT)
    platform = ReviewPlatform(executor)
    document = platform.upload(platform.workspace_id, "synthetic.md", "text/markdown", CONTENT)
    body = {
        "document_id": document["id"],
        "context_document_ids": [],
        "profile": {"id": platform.system_profile.id, "version": platform.system_profile.version},
        "model_profile": {"id": "deterministic-v1", "version": "1.0.0"},
        "locale": "ru-RU",
    }
    initial = platform.create_run(platform.workspace_id, body, "initial-run")
    entered, release = Event(), Event()

    class BlockingExecutor:
        def execute(self, **kwargs):
            entered.set()
            assert release.wait(5)
            return executor.execute(**kwargs)

    platform.executor = BlockingExecutor()
    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(platform.create_run, platform.workspace_id, body, "slow-run")
        assert entered.wait(5)
        platform.executor = executor
        parallel = platform.create_run(platform.workspace_id, body, "parallel")
        release.set()
        slow = running.result(5)
    assert parallel["id"] != initial["id"]
    assert platform.cycles.get(platform.workspace_id, slow["id"])["baseline_run_id"] == initial["id"]


def test_guest_versions_replay_at_quota_and_foreign_cycle_pdf_are_isolated(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import closing

    from review_runtime.security.guest_storage import GuestStorageLimits

    monkeypatch.setenv("REVIEW_GUEST_ACCESS", "true")
    app = request.getfixturevalue("durable_app")
    app.state.guest_storage_limits = GuestStorageLimits(per_guest_documents=2)
    with TestClient(app, base_url="https://cycle.example.test") as owner:
        workspace, document = upload(owner)
        base = f"/v1/workspaces/{workspace}"
        family = owner.get(base + f"/documents/{document['id']}/family").json()["family_id"]
        url = base + f"/document-families/{family}/versions"
        key = str(uuid4())

        def add():
            return owner.post(
                url, headers={"Idempotency-Key": key}, files={"file": ("v2.md", CONTENT, "text/markdown")}
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: add(), range(2)))
        assert [result.status_code for result in results] == [201, 201]
        assert results[0].json() == results[1].json()
        assert add().json() == results[0].json()
        assert len(owner.get(url).json()["items"]) == 2
        denied = owner.post(
            url,
            headers={"Idempotency-Key": str(uuid4())},
            files={"file": ("v3.md", CONTENT, "text/markdown")},
        )
        assert denied.status_code == 413 and denied.json()["code"] == "guest_storage_limit"
        run = review(owner, workspace, document)
        with closing(TestClient(app, base_url="https://cycle.example.test")) as other:
            stranger = other.get("/v1/bootstrap").json()["workspace"]["id"]
            for scope in (workspace, stranger):
                prefix = f"/v1/workspaces/{scope}"
                for suffix in (
                    f"/document-families/{family}",
                    f"/document-families/{family}/versions",
                    f"/documents/{document['id']}/family",
                    f"/review-runs/{run['id']}/review-cycle",
                    f"/review-runs/{run['id']}/report.pdf",
                ):
                    response = other.get(prefix + suffix)
                    assert response.status_code == 404, (suffix, response.text)
                result = other.post(
                    prefix + f"/document-families/{family}/versions",
                    headers={"Idempotency-Key": str(uuid4())},
                    files={"file": ("v4.md", CONTENT, "text/markdown")},
                )
                assert result.status_code == 404
        assert owner.get(base + f"/documents/{document['id']}/content").content == CONTENT


def test_postgres_export_uses_one_snapshot_during_a_concurrent_decision(
    durable_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(durable_app) as client:
        workspace, document = upload(client)
        run = review(client, workspace, document)
        platform = durable_app.state.platform
        report = client.get(f"/v1/workspaces/{workspace}/review-runs/{run['id']}/report").json()
        finding_id = report["findings"][0]["id"]
        original = platform.cycles._report
        changed = False

        def read_and_change(connection, identifier):
            nonlocal changed
            value = original(connection, identifier)
            isolation = connection.execute("SHOW transaction_isolation").fetchone()["transaction_isolation"]
            if isolation == "repeatable read" and not changed:
                changed = True
                platform.put_decision(
                    workspace,
                    run["id"],
                    finding_id,
                    {
                        "status": "confirmed",
                        "reason": "Concurrent decision",
                        "resolution": None,
                        "expected_revision": 0,
                    },
                )
            return value

        monkeypatch.setattr(platform.cycles, "_report", read_and_change)
        snapshot = platform.cycles.export_snapshot(workspace, run["id"])
        assert changed
        assert snapshot["finding_states"]["items"][0]["decision"]["revision"] == 0
        assert platform.states(workspace, run["id"])["items"][0]["decision"]["revision"] == 1
        assert snapshot["cycle"]["run_id"] == run["id"]


def test_changed_context_preserves_limitations_and_does_not_carry_decision(cycle_client: TestClient) -> None:
    client = cycle_client
    workspace, document = upload(client)
    base = f"/v1/workspaces/{workspace}"
    contexts = [
        client.post(
            base + "/documents",
            files={"file": ("context.md", content, "text/markdown")},
        ).json()["id"]
        for content in (b"# Synthetic context\nDaily schedule", b"# Synthetic context\nWeekly schedule")
    ]
    first = review(client, workspace, document, contexts=contexts[:1])
    finding = client.get(base + f"/review-runs/{first['id']}/report").json()["findings"][0]
    client.app.state.platform.put_decision(
        workspace,
        first["id"],
        finding["id"],
        {"status": "confirmed", "reason": "Previous context", "resolution": None, "expected_revision": 0},
    )
    second = review(client, workspace, document, contexts=contexts[1:])
    url = base + f"/review-runs/{second['id']}/review-cycle"
    cycle = client.get(url).json()
    assert "review_conditions_changed" in cycle["limitations"]
    assert cycle["entries"][0]["previous_decision"]["status"] == "confirmed"
    assert cycle["entries"][0]["decision_carried"] is False
    assert client.post(url + "/compare", json={"expected_revision": cycle["revision"]}).json() == cycle


def test_previous_decision_snapshot_and_manual_links_survive_retry(cycle_client: TestClient) -> None:
    client = cycle_client
    workspace, document = upload(client)
    platform = client.app.state.platform
    base = f"/v1/workspaces/{workspace}"
    first = review(client, workspace, document)
    finding = client.get(base + f"/review-runs/{first['id']}/report").json()["findings"][0]
    decision = {
        "status": "confirmed",
        "reason": "Original reason",
        "resolution": None,
        "expected_revision": 0,
    }
    platform.put_decision(workspace, first["id"], finding["id"], decision)
    second = review(client, workspace, document)
    url = base + f"/review-runs/{second['id']}/review-cycle"
    initial = client.get(url).json()
    entry = initial["entries"][0]
    assert entry["decision_carried"] is True
    platform.put_decision(
        workspace, first["id"], finding["id"], decision | {"expected_revision": 1, "reason": "Later"}
    )
    assert client.get(url).json()["entries"][0]["previous_decision"]["reason"] == "Original reason"
    unlinked = client.put(
        url + f"/links/{entry['current_finding_id']}",
        json={"previous_issue_id": None, "expected_revision": initial["revision"]},
    )
    assert unlinked.status_code == 200, unlinked.text
    snapshot = unlinked.json()
    assert client.post(url + "/compare", json={"expected_revision": snapshot["revision"]}).json() == snapshot
    assert all(not item["decision_carried"] for item in snapshot["entries"])


def test_partial_extraction_never_carries_old_decision(
    cycle_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = cycle_client
    workspace, document = upload(client)
    platform = client.app.state.platform
    first = review(client, workspace, document)
    base = f"/v1/workspaces/{workspace}"
    finding = client.get(base + f"/review-runs/{first['id']}/report").json()["findings"][0]
    platform.put_decision(
        workspace,
        first["id"],
        finding["id"],
        {"status": "confirmed", "reason": "Synthetic finding", "resolution": None, "expected_revision": 0},
    )
    if hasattr(platform, "database_url"):
        original_sources = platform.cycles._sources

        def incomplete_sources(connection, run_id):
            return [source | {"state": "partial"} for source in original_sources(connection, run_id)]

        monkeypatch.setattr(platform.cycles, "_sources", incomplete_sources)
    else:
        original_execute = platform.executor.execute

        def incomplete_execution(**kwargs):
            result = original_execute(**kwargs)
            kwargs["document"].extraction_state = "partial"
            return result

        monkeypatch.setattr(platform.executor, "execute", incomplete_execution)
    second = review(client, workspace, document)
    cycle = client.get(base + f"/review-runs/{second['id']}/review-cycle").json()
    assert cycle["entries"][0]["previous_decision"]["status"] == "confirmed"
    assert cycle["entries"][0]["decision_carried"] is False
    assert platform.states(workspace, second["id"])["items"][0]["decision"]["status"] == "unreviewed"


def test_active_extraction_has_pending_public_version_state(durable_app) -> None:
    with TestClient(durable_app) as client:
        workspace, document = upload(client)
        platform = durable_app.state.platform
        with platform._connect() as connection:
            connection.execute(
                "UPDATE document_extractions SET state='extracting' WHERE document_id=%s",
                (document["id"],),
            )
        base = f"/v1/workspaces/{workspace}"
        version = client.get(base + f"/documents/{document['id']}/family").json()
        assert version["document"]["extraction_state"] == "pending"
        assert (
            client.get(base + f"/document-families/{version['family_id']}/versions").json()["items"][0]
            == version
        )
