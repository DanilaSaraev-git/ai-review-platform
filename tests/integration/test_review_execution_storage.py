from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from review_core.application.execution import CommitOutcomeUnknown, ExecutionClaim, ExecutionFailure
from review_core.domain.errors import Conflict
from review_runtime.fakes.review_executor import TrustedFixtureReviewExecutor
from review_runtime.postgres.platform import (
    PostgresReviewExecutionStorage,
    PostgresReviewPlatform,
    ReviewStorageRequest,
)

ROOT = Path(__file__).parents[2]


def _storage_request(
    platform: PostgresReviewPlatform,
    document_id: str,
    *,
    key: str,
    locale: str = "en-US",
) -> ReviewStorageRequest:
    profile = platform.list_profiles(platform.workspace_id)["items"][0]
    body = {
        "document_id": document_id,
        "context_document_ids": [],
        "profile": {"id": profile["id"], "version": profile["version"]},
        "model_profile": {"id": platform.model_profile["id"], "version": "1.0.0"},
        "locale": locale,
    }
    run_id = str(uuid4())
    now = datetime.now(UTC)
    snapshot = platform.snapshot_for_profile_reference(body["profile"])
    return ReviewStorageRequest(
        workspace_id=platform.workspace_id,
        idempotency_key=key,
        request_body=body,
        run_id=run_id,
        snapshot_id=str(uuid4()),
        snapshot=snapshot,
        run_value={
            "id": run_id,
            "workspace_id": platform.workspace_id,
            "state": "queued",
            "progress": {"percent": 0, "message": "Review queued"},
            "document_id": document_id,
            "context_document_ids": [],
            "execution_snapshot": snapshot,
            "created_by": platform.actor,
            "created_at": now.isoformat(),
            "started_at": None,
            "finished_at": None,
            "cancel_requested_at": None,
            "report_available": False,
            "error": None,
        },
        sources=(
            {
                "source_id": "source-main",
                "document_id": document_id,
                "role": "document",
                "ordinal": 1,
            },
        ),
    )


@pytest.fixture
def review_storage(operator_settings):  # type: ignore[no-untyped-def]
    platform = PostgresReviewPlatform(TrustedFixtureReviewExecutor(ROOT), operator_settings)
    document = platform.upload(
        platform.workspace_id,
        f"storage-{uuid4()}.md",
        "text/markdown",
        b"Synthetic storage boundary document.",
    )
    return platform, platform.review_storage, document["id"]


def test_admission_serializes_same_key_and_rejects_different_body(review_storage) -> None:  # type: ignore[no-untyped-def]
    platform, storage, document_id = review_storage
    key = f"storage-{uuid4()}"
    first = _storage_request(platform, document_id, key=key)
    second = _storage_request(platform, document_id, key=key)
    deadline = datetime.now(UTC) + timedelta(minutes=5)

    with ThreadPoolExecutor(max_workers=2) as executor:
        admissions = list(executor.map(lambda request: storage.admit(request, deadline), (first, second)))

    assert {item.resource_id for item in admissions} == {admissions[0].resource_id}
    assert sorted(item.replay for item in admissions) == [False, True]
    with pytest.raises(Conflict, match="different request"):
        storage.admit(_storage_request(platform, document_id, key=key, locale="ru-RU"), deadline)


def test_claim_has_a_single_owner(review_storage) -> None:  # type: ignore[no-untyped-def]
    platform, storage, document_id = review_storage
    request = _storage_request(platform, document_id, key=f"claim-{uuid4()}")
    admission = storage.admit(request, datetime.now(UTC) + timedelta(minutes=5))

    first = storage.claim(admission, "owner-a")
    second = storage.claim(admission, "owner-b")

    assert first is not None
    assert first.owner_token == "owner-a"
    assert second is None
    with storage.connect() as connection:
        row = connection.execute(
            """SELECT e.state AS execution_state, e.lease_token,
                      w.fragment_id, w.state AS work_item_state
               FROM review_run_executions e
               JOIN review_work_items w
                 ON (w.organization_id, w.workspace_id, w.execution_id) =
                    (e.organization_id, e.workspace_id, e.id)
               WHERE e.organization_id = %s AND e.workspace_id = %s AND e.id = %s""",
            (platform.organization_id, platform.workspace_id, admission.execution_id),
        ).fetchone()
    assert row == {
        "execution_state": "running",
        "lease_token": "owner-a",
        "fragment_id": None,
        "work_item_state": "running",
    }


def _prepared() -> dict[str, object]:
    return {
        "prepared_input_digest": "d" * 64,
        "sources": {"source-main": {"content_digest": "e" * 64}},
        "work_item": {"target_fragment_ids": []},
    }


def _valid_report(platform: PostgresReviewPlatform, request: ReviewStorageRequest) -> dict:  # type: ignore[type-arg]
    document = platform.get_document(platform.workspace_id, request.request_body["document_id"])
    return platform.executor.execute(
        run_id=request.run_id,
        report_id=str(uuid4()),
        document=document,
        context=[],
        snapshot=request.snapshot,
        created_at=datetime.now(UTC).isoformat(),
    )


def test_prepared_review_publishes_once_with_owner_and_deadline_guards(review_storage) -> None:  # type: ignore[no-untyped-def]
    platform, storage, document_id = review_storage
    request = _storage_request(platform, document_id, key=f"publish-{uuid4()}")
    deadline = datetime.now(UTC) + timedelta(minutes=5)
    admission = storage.admit(request, deadline)
    claim = storage.claim(admission, "publisher")
    assert claim is not None
    storage.save_prepared(claim, _prepared())

    terminal = storage.publish(claim, _valid_report(platform, request), deadline)

    assert terminal.state == "completed"
    assert storage.read_terminal(request.run_id) == terminal
    report_bytes, etag = platform.report(platform.workspace_id, request.run_id)
    assert report_bytes
    assert etag.startswith('"')
    with storage.connect() as connection:
        row = connection.execute(
            """SELECT e.state AS execution_state, e.checkpoint, e.value->>'prepared_input_digest' AS digest,
                      w.state AS work_item_state, s.prepared->>'content_digest' AS source_digest
               FROM review_run_executions e
               JOIN review_work_items w
                 ON (w.organization_id,w.workspace_id,w.execution_id) =
                    (e.organization_id,e.workspace_id,e.id)
               JOIN review_run_sources s
                 ON (s.organization_id,s.workspace_id,s.run_id) =
                    (e.organization_id,e.workspace_id,e.run_id)
               WHERE e.organization_id=%s AND e.workspace_id=%s AND e.id=%s""",
            (platform.organization_id, platform.workspace_id, claim.execution_id),
        ).fetchone()
    assert row == {
        "execution_state": "completed",
        "checkpoint": "published",
        "digest": "d" * 64,
        "work_item_state": "completed",
        "source_digest": "e" * 64,
    }


@pytest.mark.parametrize("boundary", ["stale_owner", "cancelled", "deadline", "invalid_report"])
def test_late_or_invalid_result_never_publishes(review_storage, boundary: str) -> None:  # type: ignore[no-untyped-def]
    platform, storage, document_id = review_storage
    request = _storage_request(platform, document_id, key=f"guard-{uuid4()}")
    deadline = datetime.now(UTC) + timedelta(minutes=5)
    admission = storage.admit(request, deadline)
    claim = storage.claim(admission, "owner")
    assert claim is not None
    storage.save_prepared(claim, _prepared())
    published_claim = claim
    published_deadline = deadline
    report = _valid_report(platform, request)
    if boundary == "stale_owner":
        published_claim = ExecutionClaim(claim.resource_id, claim.execution_id, "stale")
    elif boundary == "cancelled":
        cancelled = platform.cancel_run(platform.workspace_id, request.run_id)
        assert cancelled["state"] == "cancelled"
    elif boundary == "deadline":
        published_deadline = datetime.now(UTC) - timedelta(microseconds=1)
    else:
        report["unexpected"] = True

    if boundary == "cancelled":
        assert storage.publish(published_claim, report, published_deadline).state == "cancelled"
    elif boundary == "deadline":
        with pytest.raises(TimeoutError):
            storage.publish(published_claim, report, published_deadline)
        failed = storage.fail(
            claim,
            ExecutionFailure("deadline_exceeded", "The operation deadline expired.", True),
        )
        assert failed.state == "failed"
    elif boundary == "invalid_report":
        with pytest.raises(ValueError):
            storage.publish(published_claim, report, published_deadline)
    else:
        with pytest.raises(Conflict, match="owner"):
            storage.publish(published_claim, report, published_deadline)

    with storage.connect() as connection:
        assert connection.execute(
            """SELECT count(*) FROM review_reports
               WHERE organization_id=%s AND workspace_id=%s AND run_id=%s""",
            (platform.organization_id, platform.workspace_id, request.run_id),
        ).fetchone()["count"] == 0


def test_unknown_publish_commit_is_resolved_from_durable_terminal(review_storage) -> None:  # type: ignore[no-untyped-def]
    platform, storage, document_id = review_storage
    request = _storage_request(platform, document_id, key=f"commit-{uuid4()}")
    deadline = datetime.now(UTC) + timedelta(minutes=5)
    admission = storage.admit(request, deadline)
    claim = storage.claim(admission, "owner")
    assert claim is not None
    storage.save_prepared(claim, _prepared())

    def commit_then_disconnect(connection) -> None:  # type: ignore[no-untyped-def]
        connection.commit()
        raise __import__("psycopg").OperationalError("synthetic connection loss after commit")

    uncertain_storage = PostgresReviewExecutionStorage(
        database_url=storage.database_url,
        organization_id=storage.organization_id,
        workspace_id=storage.workspace_id,
        artifacts=storage.artifacts,
        report_validator=storage.report_validator,
        dialogue_policy=storage.dialogue_policy,
        terminal_committer=commit_then_disconnect,
    )
    with pytest.raises(CommitOutcomeUnknown):
        uncertain_storage.publish(claim, _valid_report(platform, request), deadline)

    terminal = storage.read_terminal(request.run_id)
    assert terminal is not None
    assert terminal.state == "completed"
    assert platform.report(platform.workspace_id, request.run_id)[0]
