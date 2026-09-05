from __future__ import annotations

import json
from pathlib import Path

import typer


def model_smoke(
    profile: str = typer.Option(...),
    fixture: Path = typer.Option(..., exists=True, dir_okay=False),
) -> None:
    del fixture
    typer.echo(json.dumps({"profile": profile, "status": "operator_configuration_required"}))
    raise typer.Exit(3)
