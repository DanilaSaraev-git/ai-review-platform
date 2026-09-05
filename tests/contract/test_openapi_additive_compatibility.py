from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).parents[2]
OPENAPI = ROOT / "contracts/review-platform/v1/openapi.yaml"
COMPATIBILITY = ROOT / "tools/contracts/orval/compatibility.mjs"


def _check(candidate: Path) -> subprocess.CompletedProcess[str]:
    baseline_source = subprocess.run(
        ["git", "show", "review-platform-contract-v1.0.1:contracts/review-platform/v1/openapi.yaml"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    with tempfile.NamedTemporaryFile("w", suffix=".yaml") as baseline:
        baseline.write(baseline_source)
        baseline.flush()
        return subprocess.run(
            ["node", str(COMPATIBILITY), baseline.name, str(candidate)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )


def test_exact_candidate_is_additive() -> None:
    assert _check(OPENAPI).returncode == 0


def test_mutated_required_or_enum_shape_is_rejected(tmp_path: Path) -> None:
    candidate = tmp_path / "breaking.yaml"
    candidate.write_text(
        OPENAPI.read_text().replace(
            "extraction_state: {enum: [pending, completed, partial, failed]}",
            "extraction_state: {enum: [completed, partial, failed]}",
        )
    )
    # Current formatting is multiline; mutate a required field in a stable way as well.
    candidate.write_text(
        candidate.read_text().replace(
            (
                "required: [id, workspace_id, filename, media_type, size_bytes, sha256, "
                "extraction_state, created_by, created_at]"
            ),
            (
                "required: [id, workspace_id, filename, media_type, size_bytes, sha256, "
                "created_by, created_at]"
            ),
        )
    )
    result = _check(candidate)
    assert result.returncode != 0
    assert "breaking shape" in result.stderr


def test_duplicate_json_example_keys_are_rejected(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"id":"first","id":"second"}')
    script = (
        "import YAML from 'yaml'; import fs from 'node:fs'; "
        "const d=YAML.parseDocument(fs.readFileSync(process.argv[1],'utf8'),"
        "{uniqueKeys:true}); if(d.errors.length) process.exit(23)"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script, str(duplicate)],
        cwd=ROOT / "tools/contracts/orval",
    )
    assert result.returncode == 23
