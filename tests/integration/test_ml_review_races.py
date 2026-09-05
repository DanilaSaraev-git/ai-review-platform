from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest
from review_api.app import create_app

from tests.integration.fake_model_provider import FakeModelProvider, ScriptedReply, chat_completion
from tests.integration.test_ml_review_http import FIXTURES, _configure_ml


async def _prepared_client(app):  # type: ignore[no-untyped-def]
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    workspace_id = app.state.platform.workspace_id
    document = await client.post(
        f"/v1/workspaces/{workspace_id}/documents",
        files={"file": ("primary.md", (FIXTURES / "primary.md").read_bytes(), "text/markdown")},
    )
    profile = (await client.get(f"/v1/workspaces/{workspace_id}/profiles")).json()["items"][0]
    return client, workspace_id, document.json()["id"], profile


def _body(document_id: str, profile: dict, reference: dict[str, str]) -> dict:  # type: ignore[type-arg]
    return {
        "document_id": document_id,
        "context_document_ids": [],
        "profile": {"id": profile["id"], "version": profile["version"]},
        "model_profile": reference,
        "locale": "en-US",
    }


@pytest.mark.asyncio
async def test_concurrent_same_key_has_one_execution_and_different_body_conflicts(
    monkeypatch: pytest.MonkeyPatch, operator_settings, tmp_path: Path  # type: ignore[no-untyped-def]
) -> None:
    reference = _configure_ml(monkeypatch, operator_settings, tmp_path)
    reply = ScriptedReply(
        chat_completion((FIXTURES / "review-response.json").read_text()),
        release=asyncio.Event(),
    )
    provider = FakeModelProvider([reply])
    app = create_app(composition="ml", model_transport=provider.transport)
    app.state.platform.observe_model_profile(
        reference,
        state="available",
        reason_code=None,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    async with app.router.lifespan_context(app):
        client, workspace_id, document_id, profile = await _prepared_client(app)
        try:
            body = _body(document_id, profile, reference)
            url = f"/v1/workspaces/{workspace_id}/review-runs"
            headers = {"Idempotency-Key": f"same-key-{uuid4().hex}"}
            first = asyncio.create_task(client.post(url, headers=headers, json=body))
            await asyncio.wait_for(reply.entered.wait(), timeout=5)
            replay = asyncio.create_task(client.post(url, headers=headers, json=body))
            changed = await client.post(url, headers=headers, json=body | {"locale": "ru-RU"})
            assert changed.status_code == 409
            assert changed.json()["code"] == "idempotency_conflict"
            assert reply.release is not None
            reply.release.set()
            first_response, replay_response = await asyncio.gather(first, replay)
            assert first_response.status_code == replay_response.status_code == 202
            assert first_response.json()["id"] == replay_response.json()["id"]
            assert provider.call_count == 1
        finally:
            await client.aclose()


@pytest.mark.asyncio
async def test_cancel_during_model_call_wins_over_late_result(
    monkeypatch: pytest.MonkeyPatch, operator_settings, tmp_path: Path  # type: ignore[no-untyped-def]
) -> None:
    reference = _configure_ml(monkeypatch, operator_settings, tmp_path)
    reply = ScriptedReply(
        chat_completion((FIXTURES / "review-response.json").read_text()),
        release=asyncio.Event(),
    )
    provider = FakeModelProvider([reply])
    app = create_app(composition="ml", model_transport=provider.transport)
    app.state.platform.observe_model_profile(
        reference,
        state="available",
        reason_code=None,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    async with app.router.lifespan_context(app):
        client, workspace_id, document_id, profile = await _prepared_client(app)
        try:
            url = f"/v1/workspaces/{workspace_id}/review-runs"
            pending = asyncio.create_task(
                client.post(
                    url,
                    headers={"Idempotency-Key": f"cancel-late-{uuid4().hex}"},
                    json=_body(document_id, profile, reference),
                )
            )
            await asyncio.wait_for(reply.entered.wait(), timeout=5)
            with psycopg.connect(app.state.platform.database_url) as connection:
                run_id = connection.execute(
                    """SELECT id FROM review_runs
                       WHERE organization_id=%s AND workspace_id=%s AND document_id=%s""",
                    (app.state.platform.organization_id, workspace_id, document_id),
                ).fetchone()[0]
            cancelled = await client.post(f"{url}/{run_id}/cancel")
            assert cancelled.status_code == 202
            assert cancelled.json()["state"] == "cancelled"
            assert reply.release is not None
            reply.release.set()
            response = await pending
            assert response.status_code == 202
            assert response.json()["state"] == "cancelled"
            assert (await client.get(f"{url}/{run_id}/report")).status_code == 409
        finally:
            await client.aclose()
