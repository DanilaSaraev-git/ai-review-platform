"""Real PostgreSQL/browser-session boundary tests using synthetic documents only."""

from __future__ import annotations

import asyncio
import hashlib
from contextlib import closing
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import httpx
import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from review_api.app import create_app
from review_runtime.config.settings import OperatorSettings
from review_runtime.security.guest_storage import GuestStorageLimits

from tests.integration.fake_model_provider import FakeModelProvider, ScriptedReply, chat_completion
from tests.integration.run_helpers import wait_for_run_terminal_async
from tests.integration.test_ml_review_http import FIXTURES, _configure_ml
from tests.integration.test_mvp_review_http import create_run, upload

COOKIE = "review_guest"
COOKIE_DOMAIN = "guest.example.test"
BASE_URL = f"https://{COOKIE_DOMAIN}"
PROFILE_BODY = {
    "name": "Synthetic guest checks",
    "role": "Synthetic analyst",
    "goal": "Review the synthetic schedule",
    "checks": ["Schedule is explicit"],
}


@pytest.fixture
def operator_settings(operator_settings: OperatorSettings) -> OperatorSettings:
    """Each test owns its deployment and artifact directory, including legacy data."""
    return operator_settings.model_copy(
        update={
            "deployment_id": uuid4(),
            "organization_id": uuid4(),
            "workspace_id": uuid4(),
            "actor_id": uuid4(),
            "system_profile_id": str(uuid4()),
            "dialogue_policy_id": f"guest-test-{uuid4().hex}",
        }
    )


@pytest.fixture
def guest_app(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> FastAPI:
    monkeypatch.setenv("REVIEW_GUEST_ACCESS", "true")
    monkeypatch.setenv("REVIEW_COMPOSITION", "durable")
    return request.getfixturevalue("durable_app")


def _bootstrap(client: TestClient) -> dict[str, Any]:
    response = client.get("/v1/bootstrap")
    assert response.status_code == 200, response.text
    assert client.cookies.get(COOKIE)
    return response.json()


def _profile(client: TestClient, workspace: str) -> dict[str, Any]:
    response = client.post(f"/v1/workspaces/{workspace}/profiles", json=PROFILE_BODY)
    assert response.status_code == 201, response.text
    return response.json()


def _finding_base(client: TestClient, workspace: str, run: dict[str, Any]) -> str:
    base = f"/v1/workspaces/{workspace}/review-runs/{run['id']}"
    report = client.get(f"{base}/report")
    assert report.status_code == 200, report.text
    return f"{base}/findings/{report.json()['findings'][0]['id']}"


def test_guest_bootstrap_keeps_identity_and_sets_protected_persistent_cookie(guest_app: FastAPI) -> None:
    with TestClient(guest_app, base_url=BASE_URL) as first:
        response = first.get("/v1/bootstrap")
        assert response.status_code == 200, response.text
        identity = response.json()
        cookie: SimpleCookie = SimpleCookie()
        cookie.load(response.headers["set-cookie"])
        session = cookie[COOKIE]
        assert session["httponly"]
        assert session["secure"]
        assert session["samesite"].lower() == "lax"
        assert session["path"] == "/"
        assert int(session["max-age"]) == 30 * 24 * 60 * 60
        assert "no-store" in response.headers["cache-control"]
        token = first.cookies[COOKIE]
        repeated = first.get("/v1/bootstrap")
        assert repeated.status_code == 200
        assert repeated.json()["workspace"] == identity["workspace"]
        assert repeated.json()["actor"] == identity["actor"]
        assert first.cookies[COOKIE] == token
        assert COOKIE in repeated.headers["set-cookie"]
        with closing(TestClient(guest_app, base_url=BASE_URL)) as second:
            other = _bootstrap(second)
            assert other["workspace"]["id"] != identity["workspace"]["id"]
            assert other["actor"]["id"] != identity["actor"]["id"]
            assert second.cookies[COOKIE] != token


def test_missing_or_tampered_cookie_cannot_access_workspace(guest_app: FastAPI) -> None:
    with TestClient(guest_app, base_url=BASE_URL) as client:
        identity = _bootstrap(client)
        workspace = identity["workspace"]["id"]
        document = upload(client, workspace, "synthetic-spec.md")
        token = client.cookies[COOKIE]
        for invalid in (None, token[:-1] + ("A" if token[-1] != "A" else "B"), "invalid"):
            client.cookies.clear()
            if invalid is not None:
                client.cookies.set(COOKIE, invalid, domain=COOKIE_DOMAIN, path="/")
            for url in (
                f"/v1/workspaces/{workspace}/documents",
                f"/v1/workspaces/{workspace}/documents/{document['id']}/content",
                f"/v1/workspaces/{workspace}/review-runs",
            ):
                denied = client.get(url)
                assert denied.status_code == 401, denied.text
                assert document["filename"] not in denied.text
                assert COOKIE not in denied.headers.get("set-cookie", "")
            denied_upload = client.post(
                f"/v1/workspaces/{workspace}/documents",
                files={"file": ("forged.md", b"# Forged upload", "text/markdown")},
            )
            assert denied_upload.status_code == 401, denied_upload.text
        assert client.get("/health/live").status_code == 200
        recovered = _bootstrap(client)
        assert recovered["workspace"]["id"] != workspace
        assert client.get(f"/v1/workspaces/{recovered['workspace']['id']}/documents").json()["items"] == []


def test_guests_cannot_read_write_or_download_foreign_resources(guest_app: FastAPI) -> None:
    with TestClient(guest_app, base_url=BASE_URL) as owner:
        owner_workspace = _bootstrap(owner)["workspace"]["id"]
        document = upload(owner, owner_workspace, "synthetic-spec.md")
        run, _ = create_run(owner, owner_workspace, document["id"], f"guest-owner-{uuid4()}")
        finding = _finding_base(owner, owner_workspace, run).rsplit("/", 1)[1]
        with closing(TestClient(guest_app, base_url=BASE_URL)) as stranger:
            stranger_workspace = _bootstrap(stranger)["workspace"]["id"]
            for namespace in (owner_workspace, stranger_workspace):
                prefix = f"/v1/workspaces/{namespace}"
                review = f"{prefix}/review-runs/{run['id']}"
                finding_base = f"{review}/findings/{finding}"
                for url in (
                    f"{prefix}/documents/{document['id']}",
                    f"{prefix}/documents/{document['id']}/content",
                    review,
                    f"{review}/report",
                    f"{review}/finding-states",
                    f"{finding_base}/dialogue",
                ):
                    response = stranger.get(url)
                    assert response.status_code == 404, (url, response.text)
                    assert document["filename"] not in response.text
                for method, url, body in (
                    ("POST", f"{review}/cancel", None),
                    (
                        "POST",
                        f"{finding_base}/dialogue/turns",
                        {
                            "message": "Change another guest's discussion.",
                            "expected_revision": 0,
                        },
                    ),
                    (
                        "POST",
                        f"{finding_base}/dialogue/turns/{uuid4()}/retry",
                        {
                            "expected_revision": 0,
                        },
                    ),
                    (
                        "PUT",
                        f"{finding_base}/decision",
                        {
                            "status": "confirmed",
                            "reason": "Forged decision",
                            "resolution": None,
                            "expected_revision": 0,
                        },
                    ),
                ):
                    response = stranger.request(
                        method, url, headers={"Idempotency-Key": str(uuid4())}, json=body
                    )
                    assert response.status_code == 404, (url, response.text)
            for resource in ("documents", "review-runs", "profiles", "model-profiles"):
                response = stranger.get(f"/v1/workspaces/{owner_workspace}/{resource}")
                assert response.status_code == 404, response.text
            denied_upload = stranger.post(
                f"/v1/workspaces/{owner_workspace}/documents",
                files={"file": ("forged.md", b"# Forged document", "text/markdown")},
            )
            assert denied_upload.status_code == 404, denied_upload.text
            denied_profile = stranger.post(f"/v1/workspaces/{owner_workspace}/profiles", json=PROFILE_BODY)
            assert denied_profile.status_code == 404, denied_profile.text
            assert stranger.get(f"/v1/workspaces/{stranger_workspace}/documents").json()["items"] == []
            assert stranger.get(f"/v1/workspaces/{stranger_workspace}/review-runs").json()["items"] == []
        assert (
            owner.get(f"/v1/workspaces/{owner_workspace}/review-runs/{run['id']}").json()["state"]
            == "completed"
        )
        assert (
            owner.get(
                f"/v1/workspaces/{owner_workspace}/review-runs/{run['id']}/findings/{finding}/dialogue"
            ).json()["turns"]
            == []
        )


def test_foreign_document_context_and_custom_profile_ids_are_rejected(guest_app: FastAPI) -> None:
    with TestClient(guest_app, base_url=BASE_URL) as owner:
        workspace = _bootstrap(owner)["workspace"]["id"]
        foreign_document = upload(owner, workspace, "synthetic-spec.md")
        foreign_profile = _profile(owner, workspace)
        with closing(TestClient(guest_app, base_url=BASE_URL)) as stranger:
            other = _bootstrap(stranger)["workspace"]["id"]
            document = upload(stranger, other, "synthetic-spec.md")
            _, body = create_run(stranger, other, document["id"], f"guest-local-{uuid4()}")
            foreign_ref = {"id": foreign_profile["id"], "version": foreign_profile["version"]}
            for replacement in (
                {"document_id": foreign_document["id"]},
                {"context_document_ids": [foreign_document["id"]]},
                {"profile": foreign_ref},
            ):
                rejected = stranger.post(
                    f"/v1/workspaces/{other}/review-runs",
                    headers={"Idempotency-Key": str(uuid4())},
                    json=body | replacement,
                )
                assert rejected.status_code == 404, rejected.text
            supersede = stranger.post(
                f"/v1/workspaces/{other}/profiles", json=PROFILE_BODY | {"supersedes": foreign_ref}
            )
            assert supersede.status_code == 404, supersede.text
            assert foreign_profile["id"] not in {
                profile["id"] for profile in stranger.get(f"/v1/workspaces/{other}/profiles").json()["items"]
            }
            assert len(stranger.get(f"/v1/workspaces/{other}/review-runs").json()["items"]) == 1


def test_guest_cookie_restores_documents_review_dialogue_and_decision_after_restart(
    guest_app: FastAPI,
) -> None:
    with TestClient(guest_app, base_url=BASE_URL) as original:
        identity = _bootstrap(original)
        workspace = identity["workspace"]["id"]
        document = upload(original, workspace, "synthetic-spec.md")
        custom_profile = _profile(original, workspace)
        run, _ = create_run(original, workspace, document["id"], f"guest-restart-{uuid4()}")
        run_url = f"/v1/workspaces/{workspace}/review-runs/{run['id']}"
        report = original.get(f"{run_url}/report")
        finding = _finding_base(original, workspace, run)
        dialogue = original.get(f"{finding}/dialogue").json()
        sent = original.post(
            f"{finding}/dialogue/turns",
            headers={"Idempotency-Key": str(uuid4())},
            json={"message": "Explain this synthetic finding.", "expected_revision": dialogue["revision"]},
        )
        assert sent.status_code == 202, sent.text
        decision = original.put(
            f"{finding}/decision",
            json={
                "status": "confirmed",
                "reason": "Synthetic finding checked.",
                "resolution": "Clarify the retry boundary.",
                "expected_revision": 0,
            },
        )
        assert decision.status_code == 200, decision.text
        history = original.get(f"{finding}/dialogue").json()
        states = original.get(f"{run_url}/finding-states").json()
        token = original.cookies[COOKIE]

    restarted = create_app(composition="durable")
    with TestClient(restarted, base_url=BASE_URL) as returning:
        returning.cookies.set(COOKIE, token, domain=COOKIE_DOMAIN, path="/")
        restored = _bootstrap(returning)
        assert restored["workspace"] == identity["workspace"]
        assert restored["actor"] == identity["actor"]
        documents = returning.get(f"/v1/workspaces/{workspace}/documents").json()["items"]
        assert [item["id"] for item in documents] == [document["id"]]
        downloaded = returning.get(f"/v1/workspaces/{workspace}/documents/{document['id']}/content")
        assert downloaded.status_code == 200
        assert (
            downloaded.content
            == (Path(__file__).parents[2] / "tests/fixtures/synthetic-review/synthetic-spec.md").read_bytes()
        )
        assert returning.get(run_url).json()["state"] == "completed"
        restored_report = returning.get(f"{run_url}/report")
        assert restored_report.content == report.content
        assert restored_report.headers["etag"] == report.headers["etag"]
        assert returning.get(f"{finding}/dialogue").json() == history
        assert returning.get(f"{run_url}/finding-states").json() == states
        assert custom_profile["id"] in {
            profile["id"] for profile in returning.get(f"/v1/workspaces/{workspace}/profiles").json()["items"]
        }


def test_legacy_configured_workspace_remains_available_when_guest_mode_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    monkeypatch.setenv("REVIEW_GUEST_ACCESS", "false")
    monkeypatch.setenv("REVIEW_COMPOSITION", "durable")
    app = request.getfixturevalue("durable_app")
    with TestClient(app) as client:
        response = client.get("/v1/bootstrap")
        assert response.status_code == 200, response.text
        assert response.json()["workspace"]["id"] == app.state.platform.workspace_id
        assert COOKIE not in client.cookies
        assert client.get(f"/v1/workspaces/{app.state.platform.workspace_id}/documents").status_code == 200


def test_session_storage_hashes_credentials_renews_expiry_and_rejects_expired_cookie(
    guest_app: FastAPI,
    database_url: str,
) -> None:
    database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    with TestClient(guest_app, base_url=BASE_URL) as client:
        identity = _bootstrap(client)
        workspace = identity["workspace"]["id"]
        document = upload(client, workspace, "synthetic-spec.md")
        token = client.cookies[COOKIE]
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        with psycopg.connect(database_url) as connection:
            row = connection.execute(
                "SELECT row_to_json(s) FROM guest_sessions s WHERE workspace_id=%s", (workspace,)
            ).fetchone()
            assert row is not None
            assert row[0]["token_sha256"] == digest
            assert token not in str(row[0])
            connection.execute(
                "UPDATE guest_sessions SET last_seen_at=now()-interval '2 days', "
                "expires_at=now()+interval '1 day' WHERE token_sha256=%s",
                (digest,),
            )
        renewed = client.get(f"/v1/workspaces/{workspace}/documents")
        assert renewed.status_code == 200, renewed.text
        assert COOKIE in renewed.headers["set-cookie"]
        assert "no-store" in renewed.headers["cache-control"]
        with psycopg.connect(database_url) as connection:
            row = connection.execute(
                "SELECT last_seen_at, expires_at FROM guest_sessions WHERE token_sha256=%s", (digest,)
            ).fetchone()
            assert row is not None
            assert row[0] > datetime.now(UTC) - timedelta(minutes=1)
            assert row[1] > datetime.now(UTC) + timedelta(days=29)
            connection.execute(
                "UPDATE guest_sessions SET expires_at=now()-interval '1 second' WHERE token_sha256=%s",
                (digest,),
            )
        expired = client.get(f"/v1/workspaces/{workspace}/documents/{document['id']}/content")
        assert expired.status_code == 401, expired.text
        fresh = _bootstrap(client)
        assert fresh["workspace"]["id"] != workspace
        assert client.cookies[COOKIE] != token
        with psycopg.connect(database_url) as connection:
            assert connection.execute(
                "SELECT id FROM document_versions WHERE workspace_id=%s AND id=%s",
                (workspace, document["id"]),
            ).fetchone() == (document["id"],)


@pytest.mark.parametrize("headers", [{"Origin": "https://another.invalid"}, {"Sec-Fetch-Site": "cross-site"}])
def test_cross_origin_requests_cannot_create_session_or_modify_guest_data(
    guest_app: FastAPI,
    headers: dict[str, str],
) -> None:
    with TestClient(guest_app, base_url=BASE_URL) as client:
        rejected = client.get("/v1/bootstrap", headers=headers)
        assert rejected.status_code == 403, rejected.text
        assert COOKIE not in client.cookies
        workspace = _bootstrap(client)["workspace"]["id"]
        rejected_upload = client.post(
            f"/v1/workspaces/{workspace}/documents",
            headers=headers,
            files={"file": ("synthetic.md", b"# Cross-origin document", "text/markdown")},
        )
        assert rejected_upload.status_code == 403, rejected_upload.text
        assert client.get(f"/v1/workspaces/{workspace}/documents").json()["items"] == []
        same_origin = client.post(
            f"/v1/workspaces/{workspace}/documents",
            headers={"Origin": BASE_URL, "Sec-Fetch-Site": "same-origin"},
            files={"file": ("synthetic.md", b"# Same-origin document", "text/markdown")},
        )
        assert same_origin.status_code == 201, same_origin.text


def test_existing_team_documents_are_inaccessible_to_guests(guest_app: FastAPI) -> None:
    platform = guest_app.state.platform
    team_document = platform.upload(
        platform.workspace_id, "synthetic-team.md", "text/markdown", b"# Synthetic team-only material"
    )
    with TestClient(guest_app, base_url=BASE_URL) as guest:
        workspace = _bootstrap(guest)["workspace"]["id"]
        assert workspace != platform.workspace_id
        for namespace in (workspace, platform.workspace_id):
            response = guest.get(f"/v1/workspaces/{namespace}/documents/{team_document['id']}/content")
            assert response.status_code == 404, response.text
        assert guest.get(f"/v1/workspaces/{workspace}/documents").json()["items"] == []


@pytest.mark.parametrize("quota", ["bytes", "documents"])
def test_guest_upload_quota_rejects_extra_files_and_preserves_saved_documents(
    guest_app: FastAPI,
    quota: str,
) -> None:
    content = b"# Synthetic saved document\n"
    guest_app.state.guest_storage_limits = GuestStorageLimits(
        per_guest_bytes=len(content) if quota == "bytes" else 1024,
        per_guest_documents=1 if quota == "documents" else 20,
        total_bytes=4096,
        reserve_bytes=1,
    )
    with TestClient(guest_app, base_url=BASE_URL) as client:
        workspace = _bootstrap(client)["workspace"]["id"]
        url = f"/v1/workspaces/{workspace}/documents"
        saved = client.post(url, files={"file": ("saved.md", content, "text/markdown")})
        assert saved.status_code == 201, saved.text
        artifact_root = guest_app.state.platform.settings.artifact_root
        files_before = {path for path in artifact_root.rglob("*") if path.is_file()}
        rejected = client.post(url, files={"file": ("extra.md", b"# Extra", "text/markdown")})
        assert rejected.status_code == 413, rejected.text
        assert rejected.json()["code"] == "guest_storage_limit"
        assert {path for path in artifact_root.rglob("*") if path.is_file()} == files_before
        assert client.get(f"{url}/{saved.json()['id']}/content").content == content
        assert [item["id"] for item in client.get(url).json()["items"]] == [saved.json()["id"]]


def test_total_guest_upload_quota_preserves_other_guests_files(guest_app: FastAPI) -> None:
    content = b"# Synthetic shared-capacity fixture\n"
    guest_app.state.guest_storage_limits = GuestStorageLimits(
        per_guest_bytes=1024,
        per_guest_documents=20,
        total_bytes=len(content),
        reserve_bytes=1,
    )
    with TestClient(guest_app, base_url=BASE_URL) as first:
        workspace = _bootstrap(first)["workspace"]["id"]
        url = f"/v1/workspaces/{workspace}/documents"
        saved = first.post(url, files={"file": ("saved.md", content, "text/markdown")})
        assert saved.status_code == 201, saved.text
        with closing(TestClient(guest_app, base_url=BASE_URL)) as second:
            other = _bootstrap(second)["workspace"]["id"]
            other_url = f"/v1/workspaces/{other}/documents"
            rejected = second.post(other_url, files={"file": ("extra.md", content, "text/markdown")})
            assert rejected.status_code == 503, rejected.text
            assert rejected.json()["code"] == "storage_unavailable"
            assert second.get(other_url).json()["items"] == []
        assert first.get(f"{url}/{saved.json()['id']}/content").content == content


def test_disk_reserve_blocks_new_upload_without_staging_and_preserves_downloads(
    guest_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = b"# Synthetic disk-reserve fixture\n"
    guest_app.state.guest_storage_limits = GuestStorageLimits(
        per_guest_bytes=1024,
        per_guest_documents=20,
        total_bytes=4096,
        reserve_bytes=100,
    )
    with TestClient(guest_app, base_url=BASE_URL) as client:
        workspace = _bootstrap(client)["workspace"]["id"]
        url = f"/v1/workspaces/{workspace}/documents"
        saved = client.post(url, files={"file": ("saved.md", content, "text/markdown")})
        assert saved.status_code == 201, saved.text
        artifact_root = guest_app.state.platform.settings.artifact_root
        files_before = {path for path in artifact_root.rglob("*") if path.is_file()}
        monkeypatch.setattr(
            "review_runtime.security.guest_storage.shutil.disk_usage",
            lambda _path: SimpleNamespace(free=100 + 3 * len(content) - 1),
        )
        rejected = client.post(url, files={"file": ("extra.md", content, "text/markdown")})
        assert rejected.status_code == 503, rejected.text
        assert rejected.json()["code"] == "storage_unavailable"
        assert {path for path in artifact_root.rglob("*") if path.is_file()} == files_before
        assert client.get(f"{url}/{saved.json()['id']}/content").content == content


@pytest.mark.parametrize("shared", [False, True], ids=["one-guest", "two-guests"])
async def test_concurrent_uploads_cannot_overdraw_guest_or_total_quota(
    guest_app: FastAPI,
    shared: bool,
) -> None:
    content = b"# Synthetic concurrent quota fixture\n"
    guest_app.state.guest_storage_limits = GuestStorageLimits(
        per_guest_bytes=1024 if shared else len(content),
        per_guest_documents=20,
        total_bytes=len(content) if shared else 4096,
        reserve_bytes=1,
    )
    async with guest_app.router.lifespan_context(guest_app):
        async with (
            httpx.AsyncClient(transport=httpx.ASGITransport(app=guest_app), base_url=BASE_URL) as first,
            httpx.AsyncClient(transport=httpx.ASGITransport(app=guest_app), base_url=BASE_URL) as second,
        ):
            first_bootstrap = await first.get("/v1/bootstrap")
            workspace = first_bootstrap.json()["workspace"]["id"]
            other = (await second.get("/v1/bootstrap")).json()["workspace"]["id"]
            url = f"/v1/workspaces/{workspace}/documents"
            second_client = second if shared else first
            second_url = f"/v1/workspaces/{other}/documents" if shared else url
            responses = await asyncio.gather(
                first.post(url, files={"file": ("first.md", content, "text/markdown")}),
                second_client.post(second_url, files={"file": ("second.md", content, "text/markdown")}),
            )
            assert sorted(response.status_code for response in responses) == [201, 503 if shared else 413]
            first_items = (await first.get(url)).json()["items"]
            second_items = (await second.get(f"/v1/workspaces/{other}/documents")).json()["items"]
            assert len(first_items) + len(second_items) == 1
            with psycopg.connect(guest_app.state.platform.database_url) as connection:
                row = connection.execute(
                    "SELECT count(*), sum(size_bytes) FROM document_versions WHERE organization_id=%s",
                    (guest_app.state.platform.organization_id,),
                ).fetchone()
            assert row == (1, len(content))


async def test_two_guests_share_the_model_concurrency_limit_and_keep_separate_results(
    monkeypatch: pytest.MonkeyPatch,
    operator_settings,
    tmp_path: Path,  # type: ignore[no-untyped-def]
) -> None:
    reference = _configure_ml(monkeypatch, operator_settings, tmp_path)
    monkeypatch.setenv("REVIEW_GUEST_ACCESS", "true")
    response_text = (FIXTURES / "review-response.json").read_text()
    replies = [ScriptedReply(chat_completion(response_text), release=asyncio.Event()) for _ in range(3)]
    provider = FakeModelProvider(replies)
    app = create_app(composition="ml", model_transport=provider.transport)
    app.state.platform.observe_model_profile(
        reference,
        state="available",
        reason_code=None,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    async with app.router.lifespan_context(app):
        async with (
            httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE_URL) as first,
            httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE_URL) as second,
        ):
            identities = await asyncio.gather(first.get("/v1/bootstrap"), second.get("/v1/bootstrap"))
            assert all(response.status_code == 200 for response in identities)
            workspaces = [response.json()["workspace"]["id"] for response in identities]
            assert workspaces[0] != workspaces[1]
            requests = []
            for ordinal, client in enumerate((first, second, second)):
                workspace = workspaces[0 if ordinal == 0 else 1]
                document = await client.post(
                    f"/v1/workspaces/{workspace}/documents",
                    files={"file": ("primary.md", (FIXTURES / "primary.md").read_bytes(), "text/markdown")},
                )
                assert document.status_code == 201, document.text
                profiles = await client.get(f"/v1/workspaces/{workspace}/profiles")
                profile = profiles.json()["items"][0]
                requests.append(
                    (
                        client,
                        workspace,
                        {
                            "document_id": document.json()["id"],
                            "context_document_ids": [],
                            "profile": {"id": profile["id"], "version": profile["version"]},
                            "model_profile": reference,
                            "locale": "en-US",
                        },
                    )
                )
            tasks = [
                asyncio.create_task(
                    client.post(
                        f"/v1/workspaces/{workspace}/review-runs",
                        headers={"Idempotency-Key": str(uuid4())},
                        json=body,
                    )
                )
                for client, workspace, body in requests
            ]
            try:
                await asyncio.wait_for(
                    asyncio.gather(*(reply.entered.wait() for reply in replies[:2])), timeout=10
                )
                assert provider.call_count == 2
                with pytest.raises(TimeoutError):
                    await asyncio.wait_for(replies[2].entered.wait(), timeout=0.15)
                assert (await first.get("/health/live")).status_code == 200
                assert replies[0].release is not None
                replies[0].release.set()
                await asyncio.wait_for(replies[2].entered.wait(), timeout=10)
                assert provider.call_count == 3
            finally:
                for reply in replies:
                    assert reply.release is not None
                    reply.release.set()
                responses = await asyncio.wait_for(asyncio.gather(*tasks), timeout=20)
            assert [response.status_code for response in responses] == [202] * 3
            for index, (client, workspace, _) in enumerate(requests):
                run_id = responses[index].json()["id"]
                run = await wait_for_run_terminal_async(client, workspace, run_id)
                assert run["state"] == "completed"
                report = await client.get(f"/v1/workspaces/{workspace}/review-runs/{run_id}/report")
                assert report.status_code == 200, report.text
                other_client = second if client is first else first
                other_workspace = workspaces[1] if client is first else workspaces[0]
                assert (
                    await other_client.get(f"/v1/workspaces/{other_workspace}/review-runs/{run_id}/report")
                ).status_code == 404
            assert len((await first.get(f"/v1/workspaces/{workspaces[0]}/review-runs")).json()["items"]) == 1
            assert len((await second.get(f"/v1/workspaces/{workspaces[1]}/review-runs")).json()["items"]) == 2
