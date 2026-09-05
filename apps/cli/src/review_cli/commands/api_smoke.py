from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import httpx
import typer


def _client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url.rstrip("/") + "/", timeout=30, follow_redirects=False)


def api_smoke(
    base_url: str = typer.Option(...),
    primary: Path = typer.Option(..., exists=True, dir_okay=False),
    context: list[Path] | None = typer.Option(None),
    model_profile: str = typer.Option("deterministic-v1"),
    assert_offline: bool = typer.Option(False),
    evidence_dir: Path = typer.Option(...),
) -> None:
    with _client(base_url) as client:
        bootstrap = client.get("v1/bootstrap").raise_for_status().json()
        workspace = bootstrap["workspace"]["id"]
        documents = []
        for path in [primary, *(context or [])]:
            media = "text/markdown" if path.suffix.lower() in {".md", ".markdown"} else "text/plain"
            response = client.post(
                f"v1/workspaces/{workspace}/documents",
                files={"file": (path.name, path.read_bytes(), media)},
            )
            documents.append(response.raise_for_status().json())
        profile = client.get(f"v1/workspaces/{workspace}/profiles").raise_for_status().json()["items"][0]
        body = {
            "document_id": documents[0]["id"],
            "context_document_ids": [item["id"] for item in documents[1:]],
            "profile": {"id": profile["id"], "version": profile["version"]},
            "model_profile": {"id": model_profile, "version": "1.0.0"},
            "locale": "en-US",
        }
        headers = {"Idempotency-Key": "cli-smoke-v1"}
        run_response = client.post(f"v1/workspaces/{workspace}/review-runs", json=body, headers=headers)
        run = run_response.raise_for_status().json()
        replay = client.post(f"v1/workspaces/{workspace}/review-runs", json=body, headers=headers)
        if replay.raise_for_status().json()["id"] != run["id"]:
            raise RuntimeError("idempotent replay changed the review run")
        for _ in range(120):
            run = client.get(f"v1/workspaces/{workspace}/review-runs/{run['id']}").raise_for_status().json()
            if run["state"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.1)
        if run["state"] != "completed":
            raise RuntimeError("review run did not complete")
        report_response = client.get(f"v1/workspaces/{workspace}/review-runs/{run['id']}/report")
        report_response.raise_for_status()
        report = report_response.content
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "report.json").write_bytes(report)
        evidence = {
            "workspace_id": workspace,
            "run_id": run["id"],
            "etag": report_response.headers["etag"],
            "report_sha256": hashlib.sha256(report).hexdigest(),
            "assert_offline": assert_offline,
        }
        (evidence_dir / "evidence.json").write_text(json.dumps(evidence, sort_keys=True), encoding="utf-8")
        typer.echo(json.dumps(evidence))


def verify_evidence(base_url: str = typer.Option(...), evidence_dir: Path = typer.Option(...)) -> None:
    evidence = json.loads((evidence_dir / "evidence.json").read_text())
    with _client(base_url) as client:
        response = client.get(
            f"v1/workspaces/{evidence['workspace_id']}/review-runs/{evidence['run_id']}/report"
        )
        response.raise_for_status()
    valid = (
        hashlib.sha256(response.content).hexdigest() == evidence["report_sha256"]
        and response.headers["etag"] == evidence["etag"]
    )
    if not valid:
        raise RuntimeError("durable report evidence changed")
    typer.echo(json.dumps({"valid": True, "run_id": evidence["run_id"]}))
