from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import typer
from review_runtime.poc_adapter import PocReadError, read_poc_v1


def read_poc(
    run_directory: Path = typer.Argument(..., exists=True, file_okay=False),
    output: Path | None = typer.Option(None),
) -> None:
    try:
        view = read_poc_v1(run_directory)
    except (PocReadError, ValueError) as error:
        typer.echo(json.dumps({"code": "invalid_poc_v1", "message": str(error)}), err=True)
        raise typer.Exit(2) from None
    encoded = json.dumps(view, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{output.name}-", dir=output.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, output)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
    typer.echo(encoded.decode())
