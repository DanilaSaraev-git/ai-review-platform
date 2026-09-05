from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from review_core.application.platform import DocumentRecord
from review_core.domain.errors import Conflict
from review_runtime.fakes.review_executor import TrustedFixtureReviewExecutor
from review_runtime.postgres.platform import PostgresReviewPlatform

ROOT = Path(__file__).parents[2]


class MalformedReportExecutor(TrustedFixtureReviewExecutor):
    def execute(
        self,
        *,
        run_id: str,
        report_id: str,
        document: DocumentRecord,
        context: list[DocumentRecord],
        snapshot: dict[str, Any],
        created_at: str,
    ) -> dict[str, Any]:
        report = super().execute(
            run_id=run_id,
            report_id=report_id,
            document=document,
            context=context,
            snapshot=snapshot,
            created_at=created_at,
        )
        report["unexpected"] = True
        return report


def upload(durable_client, workspace_id: str, fixture: str) -> dict:  # type: ignore[no-untyped-def,type-arg]
    content = (ROOT / "tests/fixtures/synthetic-review" / fixture).read_bytes()
    response = durable_client.post(
        f"/v1/workspaces/{workspace_id}/documents",
        files={"file": (fixture, content, "text/markdown")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_run(durable_client, workspace_id: str, document_id: str, key: str) -> tuple[dict, dict]:  # type: ignore[no-untyped-def,type-arg]
    profiles = durable_client.get(f"/v1/workspaces/{workspace_id}/profiles").json()["items"]
    model = durable_client.get(f"/v1/workspaces/{workspace_id}/model-profiles").json()["items"][0]
    body = {
        "document_id": document_id,
        "context_document_ids": [],
        "profile": {"id": profiles[0]["id"], "version": profiles[0]["version"]},
        "model_profile": {"id": model["id"], "version": model["version"]},
        "locale": "en-US",
    }
    response = durable_client.post(
        f"/v1/workspaces/{workspace_id}/review-runs",
        headers={"Idempotency-Key": key},
        json=body,
    )
    assert response.status_code == 202, response.text
    value = response.json()
    assert response.headers["location"] == (
        f"/v1/workspaces/{workspace_id}/review-runs/{value['id']}"
    )
    return value, body


def test_exact_synthetic_http_flow_and_sequential_idempotency(durable_client) -> None:  # type: ignore[no-untyped-def]
    workspace_id = durable_client.get("/v1/bootstrap").json()["workspace"]["id"]
    document = upload(durable_client, workspace_id, "synthetic-spec.md")
    key = f"review-{uuid4()}"

    run, body = create_run(durable_client, workspace_id, document["id"], key)
    replay = durable_client.post(
        f"/v1/workspaces/{workspace_id}/review-runs",
        headers={"Idempotency-Key": key},
        json=body,
    )

    assert run["state"] == "completed"
    assert replay.status_code == 202
    assert replay.json()["id"] == run["id"]
    report_response = durable_client.get(
        f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/report"
    )
    assert report_response.status_code == 200
    report = report_response.json()
    assert len(report["findings"]) == 1
    assert report["findings"][0]["title"] == "Retry boundary is not defined"
    assert report["coverage"]["status"] == "complete"
    assert report_response.headers["etag"].startswith('"')

    conflicting = body | {"locale": "ru-RU"}
    conflict = durable_client.post(
        f"/v1/workspaces/{workspace_id}/review-runs",
        headers={"Idempotency-Key": key},
        json=conflicting,
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"


def test_arbitrary_document_has_honest_per_fragment_gaps(durable_client) -> None:  # type: ignore[no-untyped-def]
    workspace_id = durable_client.get("/v1/bootstrap").json()["workspace"]["id"]
    document = upload(durable_client, workspace_id, "synthetic-arbitrary.md")
    run, _ = create_run(durable_client, workspace_id, document["id"], f"arbitrary-{uuid4()}")

    response = durable_client.get(
        f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/report"
    )
    assert response.status_code == 200
    report = response.json()
    assert report["findings"] == []
    assert report["coverage"]["status"] == "partial"
    assert report["coverage"]["reviewed_fragment_ids"] == []
    assert len(report["coverage"]["gaps"]) == len(report["coverage"]["target_fragment_ids"])
    assert {
        (gap["code"], gap["reason"]) for gap in report["coverage"]["gaps"]
    } == {("other", "semantic_analysis_not_performed")}


def test_malformed_executor_report_is_not_published(operator_settings) -> None:  # type: ignore[no-untyped-def]
    platform = PostgresReviewPlatform(MalformedReportExecutor(ROOT), operator_settings)
    document = platform.upload(
        platform.workspace_id,
        "synthetic-spec.md",
        "text/markdown",
        (ROOT / "tests/fixtures/synthetic-review/synthetic-spec.md").read_bytes(),
    )
    profile = platform.list_profiles(platform.workspace_id)["items"][0]

    run = platform.create_run(
        platform.workspace_id,
        {
            "document_id": document["id"],
            "context_document_ids": [],
            "profile": {"id": profile["id"], "version": profile["version"]},
            "model_profile": {"id": "deterministic-v1", "version": "1.0.0"},
            "locale": "en-US",
        },
        f"invalid-report-{uuid4()}",
    )

    assert run["state"] == "failed"
    assert run["error"]["code"] == "validation_failed"
    with pytest.raises(Conflict, match="not published"):
        platform.report(platform.workspace_id, run["id"])
