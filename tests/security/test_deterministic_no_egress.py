from __future__ import annotations

import socket
from pathlib import Path

from review_core.application.platform import ReviewPlatform
from review_runtime.fakes.review_executor import TrustedFixtureReviewExecutor


def test_mandatory_deterministic_flow_attempts_no_network(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    attempts: list[object] = []

    def reject(*args, **kwargs):  # type: ignore[no-untyped-def]
        attempts.append((args, kwargs))
        raise AssertionError("deterministic execution attempted network access")

    monkeypatch.setattr(socket, "create_connection", reject)
    root = Path(__file__).parents[2]
    platform = ReviewPlatform(TrustedFixtureReviewExecutor(root))
    document = platform.upload(
        platform.workspace_id,
        "synthetic-spec.md",
        "text/markdown",
        (root / "tests/fixtures/synthetic-review/synthetic-spec.md").read_bytes(),
    )
    run = platform.create_run(
        platform.workspace_id,
        {
            "document_id": document["id"],
            "context_document_ids": [],
            "profile": {
                "id": platform.system_profile.id,
                "version": platform.system_profile.version,
            },
            "model_profile": {"id": "deterministic-v1", "version": "1.0.0"},
            "locale": "en-US",
        },
        "no-egress",
    )

    assert run["state"] == "completed"
    assert attempts == []


def test_default_compose_keeps_worker_deferred_and_proxy_loopback_only() -> None:
    compose = (Path(__file__).parents[2] / "deploy/compose/compose.yaml").read_text()
    assert 'profiles: ["deferred-queue"]' in compose
    assert '"127.0.0.1:${REVIEW_PROXY_PORT:-8080}:8080"' in compose
    assert "procrastinate_jobs" not in compose
