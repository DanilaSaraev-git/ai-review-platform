from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

ROOT = Path(__file__).parents[2]


async def _run(client: AsyncClient, fixture: str, key: str) -> tuple[str, str]:
    bootstrap = (await client.get("/v1/bootstrap")).json()
    workspace = bootstrap["workspace"]["id"]
    path = ROOT / "tests/fixtures/synthetic-review" / fixture
    document = await client.post(
        f"/v1/workspaces/{workspace}/documents",
        files={"file": (path.name, path.read_bytes(), "text/markdown")},
    )
    profile = (await client.get(f"/v1/workspaces/{workspace}/profiles")).json()["items"][0]
    model = (await client.get(f"/v1/workspaces/{workspace}/model-profiles")).json()["items"][0]
    run = await client.post(
        f"/v1/workspaces/{workspace}/review-runs",
        headers={"Idempotency-Key": key},
        json={
            "document_id": document.json()["id"],
            "context_document_ids": [],
            "profile": {"id": profile["id"], "version": profile["version"]},
            "model_profile": {"id": model["id"], "version": model["version"]},
            "locale": "en-US",
        },
    )
    return workspace, run.json()["id"]


async def test_trusted_report_has_finding_and_stable_exact_etag(client: AsyncClient) -> None:
    workspace, run_id = await _run(client, "synthetic-spec.md", "trusted-report")
    first = await client.get(f"/v1/workspaces/{workspace}/review-runs/{run_id}/report")
    second = await client.get(f"/v1/workspaces/{workspace}/review-runs/{run_id}/report")
    assert first.status_code == 200
    assert first.content == second.content
    assert first.headers["etag"] == second.headers["etag"]
    assert len(first.json()["findings"]) == 1


async def test_unbound_document_is_honest_fragment_partition(client: AsyncClient) -> None:
    workspace, run_id = await _run(client, "synthetic-arbitrary.md", "arbitrary")
    report = (await client.get(f"/v1/workspaces/{workspace}/review-runs/{run_id}/report")).json()
    assert report["findings"] == []
    assert report["coverage"]["status"] == "partial"
    assert report["coverage"]["reviewed_fragment_ids"] == []
    assert set(report["coverage"]["target_fragment_ids"]) == {
        gap["fragment_id"] for gap in report["coverage"]["gaps"]
    }
    assert {gap["reason"] for gap in report["coverage"]["gaps"]} == {"semantic_analysis_not_performed"}
    assert "deterministic_mode_no_semantic_analysis" in report["limitations"]
