from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_protected_paths_unchanged_from_approved_web_baseline() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/contracts/check_protected_paths.py"),
            "--json",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["unexpected_changes"] == []
