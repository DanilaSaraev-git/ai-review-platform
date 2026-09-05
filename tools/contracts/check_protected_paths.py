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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default="280ab87e22ed02c2e16ccb1baa53d74ab64d5542")
    parser.add_argument("--json", action="store_true")
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
    payload = {"changed": changed, "status": "ok" if not changed else "failed"}
    print(json.dumps(payload, sort_keys=True) if args.json else payload["status"])
    return 0 if not changed else 1


if __name__ == "__main__":
    raise SystemExit(main())
