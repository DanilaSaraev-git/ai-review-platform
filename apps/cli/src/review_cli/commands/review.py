from __future__ import annotations

import json
from pathlib import Path

import typer
from review_core.application.platform import ReviewPlatform
from review_runtime.fakes.review_executor import TrustedFixtureReviewExecutor


def review(
    primary: Path = typer.Option(..., exists=True, dir_okay=False),
    context: list[Path] | None = typer.Option(None),
    profile: str = typer.Option("base-data-spec"),
    model_profile: str = typer.Option("deterministic-v1"),
    output: Path = typer.Option(...),
) -> None:
    root = Path(__file__).resolve().parents[5]
    platform = ReviewPlatform(TrustedFixtureReviewExecutor(root))
    workspace = platform.workspace_id
    media = "text/markdown" if primary.suffix.lower() in {".md", ".markdown"} else "text/plain"
    document = platform.upload(workspace, primary.name, media, primary.read_bytes())
    context_ids = []
    for path in context or []:
        context_media = "text/markdown" if path.suffix.lower() in {".md", ".markdown"} else "text/plain"
        context_ids.append(platform.upload(workspace, path.name, context_media, path.read_bytes())["id"])
    selected = platform.system_profile
    if profile not in {"base-data-spec", selected.id}:
        raise typer.BadParameter("unknown review profile")
    if model_profile != "deterministic-v1":
        raise typer.BadParameter("unknown model profile")
    run = platform.create_run(
        workspace,
        {
            "document_id": document["id"],
            "context_document_ids": context_ids,
            "profile": {"id": selected.id, "version": selected.version},
            "model_profile": {"id": model_profile, "version": "1.0.0"},
            "locale": "en-US",
        },
        "direct-cli",
    )
    report, etag = platform.report(workspace, run["id"])
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_bytes(report)
    (output / "evidence.json").write_text(
        json.dumps(
            {
                "run_id": run["id"],
                "etag": etag,
                "report_sha256": __import__("hashlib").sha256(report).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    typer.echo(json.dumps({"run_id": run["id"], "report": str(output / "report.json")}))
