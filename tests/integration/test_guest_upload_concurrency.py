"""Synthetic HTTP uploads with real PostgreSQL and deterministic overlap barriers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Event
from types import SimpleNamespace

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from review_runtime.artifacts.posix import PosixArtifactStore
from review_runtime.documents.text import TextDocumentParser
from review_runtime.postgres.document_cycles import PostgresDocumentCycles
from review_runtime.postgres.platform import PostgresReviewPlatform
from review_runtime.security.guest_storage import GuestStorageLimits

from tests.integration import test_guest_access
from tests.integration.test_guest_access import BASE_URL, _bootstrap

guest_app = test_guest_access.guest_app
operator_settings = test_guest_access.operator_settings

SLOW = b"# Synthetic slow upload\n"
FAST = b"# Synthetic fast upload\n"


def _post(client: TestClient, workspace: str, content: bytes):
    return client.post(
        f"/v1/workspaces/{workspace}/documents",
        files={"file": ("synthetic.md", content, "text/markdown")},
    )


def _reservations(app: FastAPI):
    with psycopg.connect(app.state.platform.database_url) as connection:
        return connection.execute(
            "SELECT id,size_bytes FROM guest_upload_reservations WHERE organization_id=%s",
            (app.state.platform.organization_id,),
        ).fetchall()


def _block_slow_upload(monkeypatch: pytest.MonkeyPatch, stage: str) -> tuple[Event, Event]:
    entered, release = Event(), Event()
    owner, method = (TextDocumentParser, "parse") if stage == "parse" else (PosixArtifactStore, "stage")
    original = getattr(owner, method)

    def blocked(self, *args, **kwargs):
        content = args[0] if stage == "parse" else args[1]
        if content == SLOW:
            entered.set()
            if not release.wait(15):
                raise RuntimeError("Synthetic upload barrier timed out")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(owner, method, blocked)
    return entered, release


@pytest.mark.parametrize("stage", ["parse", "persist"])
@pytest.mark.parametrize("same_guest", [False, True], ids=["two-guests", "one-guest"])
def test_other_upload_completes_while_first_is_blocked(
    guest_app: FastAPI, monkeypatch: pytest.MonkeyPatch, stage: str, same_guest: bool,
) -> None:
    entered, release = _block_slow_upload(monkeypatch, stage)
    with TestClient(guest_app, base_url=BASE_URL) as first, closing(
        TestClient(guest_app, base_url=BASE_URL)
    ) as second:
        workspace = _bootstrap(first)["workspace"]["id"]
        other = workspace if same_guest else _bootstrap(second)["workspace"]["id"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            slow = pool.submit(_post, first, workspace, SLOW)
            try:
                assert entered.wait(5), "First upload never reached its barrier"
                assert len(_reservations(guest_app)) == 1
                fast = pool.submit(_post, first if same_guest else second, other, FAST).result(timeout=5)
                assert fast.status_code == 201, fast.text
                assert not slow.done(), "First upload must still be blocked"
                assert len(_reservations(guest_app)) == 1  # Only the slow upload remains reserved.
                assert second.get("/health/live").status_code == 200
                reader = first if same_guest else second
                assert reader.get(
                    f"/v1/workspaces/{other}/documents/{fast.json()['id']}/content"
                ).content == FAST
            finally:
                release.set()
            assert slow.result(timeout=5).status_code == 201
        assert _reservations(guest_app) == []


@pytest.mark.parametrize("quota", ["bytes", "documents", "total", "disk"])
def test_inflight_upload_counts_toward_quota_before_it_is_saved(
    guest_app: FastAPI, monkeypatch: pytest.MonkeyPatch, quota: str,
) -> None:
    entered, release = _block_slow_upload(monkeypatch, "parse")
    guest_app.state.guest_storage_limits = GuestStorageLimits(
        per_guest_bytes=len(SLOW) if quota == "bytes" else 4096,
        per_guest_documents=1 if quota == "documents" else 20,
        total_bytes=len(SLOW) if quota == "total" else 8192,
        reserve_bytes=100,
    )
    if quota == "disk":
        monkeypatch.setattr(
            "review_runtime.security.guest_storage.shutil.disk_usage",
            lambda _: SimpleNamespace(free=100 + 3 * len(SLOW)),
        )
    with TestClient(guest_app, base_url=BASE_URL) as first, closing(
        TestClient(guest_app, base_url=BASE_URL)
    ) as second:
        workspace = _bootstrap(first)["workspace"]["id"]
        shared = quota in {"total", "disk"}
        other = _bootstrap(second)["workspace"]["id"] if shared else workspace
        with ThreadPoolExecutor(max_workers=2) as pool:
            slow = pool.submit(_post, first, workspace, SLOW)
            try:
                assert entered.wait(5)
                denied = pool.submit(_post, second if shared else first, other, FAST).result(timeout=5)
                assert denied.status_code == (503 if shared else 413), denied.text
                assert len(_reservations(guest_app)) == 1
            finally:
                release.set()
            assert slow.result(timeout=5).status_code == 201
        assert _reservations(guest_app) == []


@pytest.mark.parametrize("stage", ["parse", "stage", "promote", "commit"])
def test_failed_upload_releases_capacity_and_rolls_back_document(
    guest_app: FastAPI, monkeypatch: pytest.MonkeyPatch, stage: str,
) -> None:
    guest_app.state.guest_storage_limits = GuestStorageLimits(per_guest_documents=1)
    owner, method = {
        "parse": (TextDocumentParser, "parse"),
        "stage": (PosixArtifactStore, "stage"),
        "promote": (PosixArtifactStore, "promote"),
        "commit": (PostgresDocumentCycles, "finish_upload"),
    }[stage]
    original = getattr(owner, method)

    def fail(self, *args, **kwargs):
        if stage == "commit":
            original(self, *args, **kwargs)
        raise RuntimeError("Synthetic upload failure")

    with TestClient(guest_app, base_url=BASE_URL, raise_server_exceptions=False) as client:
        workspace = _bootstrap(client)["workspace"]["id"]
        with monkeypatch.context() as patch:
            patch.setattr(owner, method, fail)
            assert _post(client, workspace, SLOW).status_code == 500
        assert _reservations(guest_app) == []
        assert client.get(f"/v1/workspaces/{workspace}/documents").json()["items"] == []
        assert _post(client, workspace, FAST).status_code == 201
        assert _reservations(guest_app) == []


def test_lost_owner_connection_is_reclaimed_and_cannot_publish_late(
    guest_app: FastAPI, monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered, release = _block_slow_upload(monkeypatch, "parse")
    guest_app.state.guest_storage_limits = GuestStorageLimits(total_bytes=len(SLOW))
    original = PostgresReviewPlatform.upload
    owner_pids: list[int] = []

    def capture_owner(self, workspace_id, filename, media_type, content, **kwargs):
        if content == SLOW:
            owner_pids.append(kwargs["reservation"].connection.info.backend_pid)
        return original(self, workspace_id, filename, media_type, content, **kwargs)

    monkeypatch.setattr(PostgresReviewPlatform, "upload", capture_owner)
    with TestClient(guest_app, base_url=BASE_URL, raise_server_exceptions=False) as first, closing(
        TestClient(guest_app, base_url=BASE_URL)
    ) as second:
        workspace = _bootstrap(first)["workspace"]["id"]
        other = _bootstrap(second)["workspace"]["id"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            slow = pool.submit(_post, first, workspace, SLOW)
            try:
                assert entered.wait(5)
                assert len(_reservations(guest_app)) == 1
                with psycopg.connect(guest_app.state.platform.database_url) as connection:
                    assert connection.execute(
                        "SELECT pg_terminate_backend(%s,5000)", (owner_pids[0],)
                    ).fetchone() == (True,)
                fast = pool.submit(_post, second, other, FAST).result(timeout=5)
                assert fast.status_code == 201, fast.text
                assert _reservations(guest_app) == []
            finally:
                release.set()
            assert slow.result(timeout=5).status_code == 500
        assert first.get(f"/v1/workspaces/{workspace}/documents").json()["items"] == []
        assert len(second.get(f"/v1/workspaces/{other}/documents").json()["items"]) == 1
