from __future__ import annotations

from httpx import AsyncClient


async def test_bootstrap_upload_download_and_distinct_same_bytes(client: AsyncClient) -> None:
    bootstrap = (await client.get("/v1/bootstrap")).json()
    workspace = bootstrap["workspace"]["id"]
    content = b"# Requirement\n\nThe daily load has no exact schedule.\n"
    first = await client.post(
        f"/v1/workspaces/{workspace}/documents",
        files={"file": ("first.md", content, "text/markdown")},
    )
    second = await client.post(
        f"/v1/workspaces/{workspace}/documents",
        files={"file": ("second.md", content, "text/markdown")},
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["sha256"] == second.json()["sha256"]
    downloaded = await client.get(f"/v1/workspaces/{workspace}/documents/{first.json()['id']}/content")
    assert downloaded.content == content
    assert downloaded.headers["etag"].startswith('"')


async def test_upload_rejects_empty_mismatch_large_and_foreign_namespace(client: AsyncClient) -> None:
    workspace = (await client.get("/v1/bootstrap")).json()["workspace"]["id"]
    empty = await client.post(
        f"/v1/workspaces/{workspace}/documents", files={"file": ("empty.md", b"", "text/markdown")}
    )
    mismatch = await client.post(
        f"/v1/workspaces/{workspace}/documents", files={"file": ("wrong.pdf", b"plain", "application/pdf")}
    )
    foreign = await client.post(
        "/v1/workspaces/00000000-0000-4000-8000-000000000099/documents",
        files={"file": ("a.md", b"a", "text/markdown")},
    )
    assert empty.status_code == mismatch.status_code == 400
    assert foreign.status_code == 404


async def test_oversize_is_413_and_malformed_profile_is_400(client: AsyncClient) -> None:
    platform = client._transport.app.state.platform  # type: ignore[attr-defined]
    workspace = platform.workspace_id
    platform.max_upload_bytes = 4
    too_large = await client.post(
        f"/v1/workspaces/{workspace}/documents", files={"file": ("large.md", b"12345", "text/markdown")}
    )
    malformed = await client.post(f"/v1/workspaces/{workspace}/profiles", json={})
    assert too_large.status_code == 413
    assert malformed.status_code == 400


async def test_profiles_and_model_profiles_use_canonical_projection(client: AsyncClient) -> None:
    workspace = (await client.get("/v1/bootstrap")).json()["workspace"]["id"]
    profiles = await client.get(f"/v1/workspaces/{workspace}/profiles")
    models = await client.get(f"/v1/workspaces/{workspace}/model-profiles")
    assert profiles.status_code == models.status_code == 200
    assert profiles.json()["items"][0]["scope"] == "system"
    assert models.json()["items"][0]["availability"] == "available"
