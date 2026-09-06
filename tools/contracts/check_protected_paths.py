#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

PROTECTED = (
    "apps/web",
    "client",
    "implementation/poc",
    "specs/001-review-data-spec-poc",
    "specs/002-target-review-platform",
)
PINNED_BASELINE = "004c8b63020612f8aff70ecade8f9789476e5939"


def main() -> int:
    parser = argparse.ArgumentParser()
    # Baseline includes accepted Numbat and demo UI; other protected paths are unchanged.
    parser.add_argument("--baseline", default=PINNED_BASELINE)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--allow-path", action="append", default=[],
        help="Explicitly approved repository-relative file; exact match, no directory/glob expansion.",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["git", "diff", "--name-only", args.baseline, "--", *PROTECTED],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    changed = [line for line in result.stdout.splitlines() if line]
    allowed = set(args.allow_path)
    unexpected = [path for path in changed if path not in allowed]
    payload = {
        "changed": changed,
        "allowed_changes": [path for path in changed if path in allowed],
        "unexpected_changes": unexpected,
        "status": "ok" if not unexpected else "failed",
    }
    print(json.dumps(payload, sort_keys=True) if args.json else payload["status"])
    return 0 if not unexpected else 1


if __name__ == "__main__":
    raise SystemExit(main())
