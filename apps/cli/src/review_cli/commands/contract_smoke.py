from __future__ import annotations

import json
from pathlib import Path

import typer


def contract_smoke(path: Path = typer.Argument(..., exists=True)) -> None:
    files = sorted(path.rglob("*.json")) if path.is_dir() else [path]
    if not files:
        raise typer.BadParameter("no JSON contract examples found")
    for item in files:
        json.loads(item.read_text(encoding="utf-8"))
    typer.echo(json.dumps({"valid": True, "files": len(files)}))
