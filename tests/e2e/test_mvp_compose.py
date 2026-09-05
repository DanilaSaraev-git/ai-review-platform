from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import httpx

ROOT = Path(__file__).parents[2]


def test_running_compose_is_healthy_and_preserves_smoke_state() -> None:
    base_url = os.environ.get("REVIEW_MVP_BASE_URL", "http://127.0.0.1:8080")

    with httpx.Client(base_url=base_url, timeout=10) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")

    result = subprocess.run(
        [
            "docker",
            "compose",
            "--project-name",
            os.environ.get(
                "REVIEW_MVP_PROJECT", os.environ.get("MVP_PROJECT", "review-platform-mvp")
            ),
            "-f",
            "deploy/compose/compose.yaml",
            "exec",
            "-T",
            "api",
            "python",
            "tools/mvp_smoke.py",
            "--base-url",
            "http://proxy:8080",
            "--state-file",
            "/var/lib/review/mvp-smoke-state.json",
            "verify-restart",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    state = json.loads(result.stdout)

    assert live.status_code == 200
    assert ready.status_code == 200
    assert ready.json()["checks"] == {
        "database": True,
        "business_schema": True,
        "exact_seed": True,
        "artifact_store": True,
    }
    assert len(state["report_sha256"]) == 64
    assert state["report_etag"] == f'"{state["report_sha256"]}"'
