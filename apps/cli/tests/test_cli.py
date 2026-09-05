from __future__ import annotations

import json
from pathlib import Path

from review_cli.main import app
from typer.testing import CliRunner

ROOT = Path(__file__).parents[3]


def test_direct_review_writes_safe_local_output(tmp_path: Path) -> None:
    output = tmp_path / "review"
    result = CliRunner().invoke(
        app,
        [
            "review",
            "--primary",
            str(ROOT / "tests/fixtures/synthetic-review/synthetic-spec.md"),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    report = json.loads((output / "report.json").read_text())
    assert len(report["findings"]) == 1
    assert "/Users/" not in (output / "report.json").read_text()


def test_read_poc_failure_is_safe_and_leaves_no_output(tmp_path: Path) -> None:
    run = tmp_path / "bad"
    run.mkdir()
    output = tmp_path / "view.json"
    result = CliRunner().invoke(app, ["read-poc-v1", str(run), "--output", str(output)])
    assert result.exit_code == 2
    assert not output.exists()
    assert str(tmp_path) not in result.output


def test_model_probe_refuses_non_ml_composition_without_traceback(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("REVIEW_COMPOSITION", "unconfigured")

    result = CliRunner().invoke(app, ["model-probe"])

    assert result.exit_code == 2
    assert json.loads(result.output) == {
        "action": "check the declared probe and mounted model files",
        "code": "invalid_configuration",
        "status": "failed",
    }
    assert "Traceback" not in result.output
