from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from review_api.app import create_app

from tests.integration.fake_model_provider import FakeModelProvider, ScriptedReply, chat_completion
from tests.integration.run_helpers import wait_for_run_terminal_async
from tests.integration.test_ml_review_http import FIXTURES, _configure_ml


@pytest.mark.asyncio
async def test_model_calls_respect_the_runtime_concurrency_limit(
    monkeypatch: pytest.MonkeyPatch, operator_settings, tmp_path: Path  # type: ignore[no-untyped-def]
) -> None:
    reference = _configure_ml(monkeypatch, operator_settings, tmp_path)
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
    workspace_id = app.state.platform.workspace_id
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            profile = (await client.get(f"/v1/workspaces/{workspace_id}/profiles")).json()["items"][0]
            documents = []
            for ordinal in range(3):
                response = await client.post(
                    f"/v1/workspaces/{workspace_id}/documents",
                    files={
                        "file": (
                            f"primary-{ordinal}.md",
                            (FIXTURES / "primary.md").read_bytes(),
                            "text/markdown",
                        )
                    },
                )
                assert response.status_code == 201
                documents.append(response.json()["id"])

            async def run(document_id: str, ordinal: int) -> httpx.Response:
                return await client.post(
                    f"/v1/workspaces/{workspace_id}/review-runs",
                    headers={"Idempotency-Key": f"concurrent-review-{request_set}-{ordinal}"},
                    json={
                        "document_id": document_id,
                        "context_document_ids": [],
                        "profile": {"id": profile["id"], "version": profile["version"]},
                        "model_profile": reference,
                        "locale": "en-US",
                    },
                )

            request_set = uuid4().hex
            tasks = [asyncio.create_task(run(document, index)) for index, document in enumerate(documents)]
            await asyncio.wait_for(
                asyncio.gather(*(reply.entered.wait() for reply in replies[:2])), timeout=5
            )
            assert provider.call_count == 2
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(replies[2].entered.wait(), timeout=0.1)
            assert (await client.get("/health/live")).status_code == 200
            assert (
                await client.get(f"/v1/workspaces/{workspace_id}/review-runs")
            ).status_code == 200
            assert replies[0].release is not None
            replies[0].release.set()
            await asyncio.wait_for(replies[2].entered.wait(), timeout=5)
            assert provider.call_count == 3
            for reply in replies[1:]:
                assert reply.release is not None
                reply.release.set()
            responses = await asyncio.gather(*tasks)
            runs = [
                await wait_for_run_terminal_async(client, workspace_id, response.json()["id"])
                for response in responses
            ]
            assert [run["state"] for run in runs] == ["completed"] * 3
