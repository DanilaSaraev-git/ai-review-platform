from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

EXPECTED_TITLE = "Retry boundary is not defined"


def request(client: httpx.Client, method: str, path: str, **kwargs: Any) -> httpx.Response:
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response


def run_flow(client: httpx.Client, state_path: Path) -> dict[str, Any]:
    workspace_id = request(client, "GET", "/v1/bootstrap").json()["workspace"]["id"]
    root = Path(__file__).parents[1]
    fixture = root / "tests/fixtures/synthetic-review/synthetic-spec.md"
    document = request(
        client,
        "POST",
        f"/v1/workspaces/{workspace_id}/documents",
        files={"file": (fixture.name, fixture.read_bytes(), "text/markdown")},
    ).json()
    profile = request(client, "GET", f"/v1/workspaces/{workspace_id}/profiles").json()["items"][0]
    model = request(client, "GET", f"/v1/workspaces/{workspace_id}/model-profiles").json()["items"][0]
    run = request(
        client,
        "POST",
        f"/v1/workspaces/{workspace_id}/review-runs",
        headers={"Idempotency-Key": f"mvp-run-{uuid4()}"},
        json={
            "document_id": document["id"],
            "context_document_ids": [],
            "profile": {"id": profile["id"], "version": profile["version"]},
            "model_profile": {"id": model["id"], "version": model["version"]},
            "locale": "en-US",
        },
    ).json()
    if run["state"] != "completed":
        raise RuntimeError(f"review did not complete synchronously: {run['state']}")
    report_path = f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/report"
    report_response = request(client, "GET", report_path)
    report = report_response.json()
    if len(report["findings"]) != 1 or report["findings"][0]["title"] != EXPECTED_TITLE:
        raise RuntimeError("synthetic fixture did not produce the exact expected finding")
    finding_id = report["findings"][0]["id"]
    finding_path = f"/v1/workspaces/{workspace_id}/review-runs/{run['id']}/findings/{finding_id}"
    dialogue = request(client, "GET", f"{finding_path}/dialogue").json()
    dialogue = request(
        client,
        "POST",
        f"{finding_path}/dialogue/turns",
        headers={"Idempotency-Key": f"mvp-turn-{uuid4()}"},
        json={"message": "Explain the implementation risk.", "expected_revision": dialogue["revision"]},
    ).json()
    if len(dialogue["turns"]) != 1 or dialogue["turns"][0]["state"] != "completed":
        raise RuntimeError("dialogue turn did not complete synchronously")
    decision = request(
        client,
        "PUT",
        f"{finding_path}/decision",
        json={
            "status": "confirmed",
            "reason": "Confirmed by the local MVP smoke.",
            "resolution": "Clarify the retry boundary.",
            "expected_revision": 0,
        },
    ).json()
    if decision["status"] != "confirmed":
        raise RuntimeError("Human Decision was not persisted")
    after = request(client, "GET", report_path)
    if after.content != report_response.content or after.headers["etag"] != report_response.headers["etag"]:
        raise RuntimeError("dialogue or decision mutated the published report")
    state = {
        "workspace_id": workspace_id,
        "run_id": run["id"],
        "finding_id": finding_id,
        "report_bytes_base64": base64.b64encode(report_response.content).decode("ascii"),
        "report_sha256": hashlib.sha256(report_response.content).hexdigest(),
        "report_etag": report_response.headers["etag"],
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n")
    return state


def verify_restart(client: httpx.Client, state_path: Path) -> dict[str, Any]:
    state = json.loads(state_path.read_text())
    report_path = (
        f"/v1/workspaces/{state['workspace_id']}/review-runs/{state['run_id']}/report"
    )
    response = request(client, "GET", report_path)
    expected = base64.b64decode(state["report_bytes_base64"])
    if response.content != expected:
        raise RuntimeError("report bytes changed after restart")
    if hashlib.sha256(response.content).hexdigest() != state["report_sha256"]:
        raise RuntimeError("report SHA-256 changed after restart")
    if response.headers["etag"] != state["report_etag"]:
        raise RuntimeError("report ETag changed after restart")
    finding_path = (
        f"/v1/workspaces/{state['workspace_id']}/review-runs/{state['run_id']}"
        f"/findings/{state['finding_id']}"
    )
    dialogue = request(client, "GET", f"{finding_path}/dialogue").json()
    states = request(
        client,
        "GET",
        f"/v1/workspaces/{state['workspace_id']}/review-runs/{state['run_id']}/finding-states",
    ).json()
    if dialogue["turns"][0]["state"] != "completed":
        raise RuntimeError("dialogue history was not restored")
    if states["items"][0]["decision"]["status"] != "confirmed":
        raise RuntimeError("Human Decision was not restored")
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Exercise the local Review Platform MVP")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("mode", choices=("run", "verify-restart"))
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        request(client, "GET", "/health/live")
        request(client, "GET", "/health/ready")
        state = run_flow(client, args.state_file) if args.mode == "run" else verify_restart(
            client, args.state_file
        )
    print(
        json.dumps(
            {
                "status": "ok",
                "mode": args.mode,
                "run_id": state["run_id"],
                "report_sha256": state["report_sha256"],
                "report_etag": state["report_etag"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
