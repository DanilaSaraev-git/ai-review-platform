from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_protected_paths_unchanged_from_docs_commit() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/contracts/check_protected_paths.py"),
            "--baseline",
            "7e91364579834c75e48d55cb168ba86b563bb3e1",
            "--json",
            *shlex.split(os.environ.get("PROTECTED_PATH_ARGS", "")),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["unexpected_changes"] == []
