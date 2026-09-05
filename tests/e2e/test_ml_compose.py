from __future__ import annotations

import os
import subprocess
from pathlib import Path

import httpx

ROOT = Path(__file__).parents[2]
COMPOSE = [
    "-f",
    "deploy/compose/compose.yaml",
    "-f",
    "deploy/compose/compose.external-model.yaml",
    "-f",
    "tests/fixtures/ml-integration/compose.external-model.test.yaml",
]


def _compose(project: str, env: dict[str, str], *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "--project-name", project, *COMPOSE, *arguments],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_opt_in_compose_reaches_only_synthetic_provider_and_publishes_report() -> None:
    project = f"review-platform-ml-e2e-{os.getpid()}"
    port = os.environ.get("REVIEW_ML_E2E_PORT", "18087")
    env = os.environ | {
        "REVIEW_PROXY_PORT": port,
        "REVIEW_MODEL_PROFILE_FILE": str(
            ROOT / "tests/fixtures/ml-integration/model-profile.compose.json"
        ),
        "REVIEW_MODEL_CREDENTIAL_FILE": str(
            ROOT / "tests/fixtures/ml-integration/synthetic-credential.txt"
        ),
    }
    try:
        started = _compose(project, env, "up", "--build", "--detach", "--wait", "proxy")
        assert started.returncode == 0, started.stderr
        observed = _compose(
            project,
            env,
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "review",
            "-d",
            "review",
            "-c",
            (
                "UPDATE model_profile_availability SET state='available', "
                "expires_at=clock_timestamp() + interval '5 minutes' "
                "WHERE model_profile_id='synthetic-compose-fake';"
            ),
        )
        assert observed.returncode == 0, observed.stderr
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=30) as client:
            workspace = client.get("/v1/bootstrap").raise_for_status().json()["workspace"]["id"]
            document = client.post(
                f"/v1/workspaces/{workspace}/documents",
                files={
                    "file": (
                        "primary.md",
                        (ROOT / "tests/fixtures/ml-integration/primary.md").read_bytes(),
                        "text/markdown",
                    )
                },
            ).raise_for_status().json()
            profile = client.get(f"/v1/workspaces/{workspace}/profiles").raise_for_status().json()[
                "items"
            ][0]
            run = client.post(
                f"/v1/workspaces/{workspace}/review-runs",
                headers={"Idempotency-Key": "compose-fake-review"},
                json={
                    "document_id": document["id"],
                    "context_document_ids": [],
                    "profile": {"id": profile["id"], "version": profile["version"]},
                    "model_profile": {"id": "synthetic-compose-fake", "version": "1.0.0"},
                    "locale": "en-US",
                },
            ).raise_for_status().json()
            assert run["state"] == "completed"
            report = client.get(
                f"/v1/workspaces/{workspace}/review-runs/{run['id']}/report"
            ).raise_for_status().json()
            assert report["provenance"]["model"]["provider"] == "synthetic-compose-provider"
    finally:
        _compose(project, env, "down", "--volumes", "--remove-orphans")
