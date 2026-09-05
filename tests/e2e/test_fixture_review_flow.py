from pathlib import Path

from httpx import ASGITransport, AsyncClient
from review_api.app import create_app

ROOT = Path(__file__).parents[2]


async def test_fixture_flow_requires_exact_digest_not_marker_text(monkeypatch) -> None:
    import socket

    attempts = []

    def deny_connect(sock, address):
        attempts.append(("connect", address))
        raise AssertionError(f"unexpected outbound connect: {address}")

    def deny_dns(*args, **kwargs):
        attempts.append(("dns", args[0]))
        raise AssertionError(f"unexpected DNS resolution: {args[0]}")

    monkeypatch.setattr(socket.socket, "connect", deny_connect)
    monkeypatch.setattr(socket, "getaddrinfo", deny_dns)
    app = create_app(composition="fixture")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bootstrap = (await client.get("/v1/bootstrap")).json()
        workspace = bootstrap["workspace"]["id"]
        trusted = (ROOT / "tests/fixtures/synthetic-review/synthetic-spec.md").read_bytes()
        copied = trusted + b"\n# copied marker but different digest\n"
        ids = []
        for index, data in enumerate((trusted, copied)):
            response = await client.post(
                f"/v1/workspaces/{workspace}/documents",
                files={"file": (f"input-{index}.md", data, "text/markdown")},
            )
            ids.append(response.json()["id"])
        profile = (await client.get(f"/v1/workspaces/{workspace}/profiles")).json()["items"][0]
        model = (await client.get(f"/v1/workspaces/{workspace}/model-profiles")).json()["items"][0]
        reports = []
        for index, document_id in enumerate(ids):
            run = await client.post(
                f"/v1/workspaces/{workspace}/review-runs",
                headers={"Idempotency-Key": f"run-key-{index}"},
                json={
                    "document_id": document_id,
                    "context_document_ids": [],
                    "profile": {"id": profile["id"], "version": profile["version"]},
                    "model_profile": {"id": model["id"], "version": model["version"]},
                    "locale": "en-US",
                },
            )
            reports.append(
                (await client.get(f"/v1/workspaces/{workspace}/review-runs/{run.json()['id']}/report")).json()
            )
    assert len(reports[0]["findings"]) == 1
    assert reports[1]["findings"] == []
    assert attempts == []
