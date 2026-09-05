#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

TEXT_SUFFIXES = {".py", ".json", ".md", ".yaml", ".yml", ".toml", ".txt", ".ini", ".html", ".js", ".ts"}
FORBIDDEN = {
    "client-name": re.compile(r"\bMTS\b|клиент", re.IGNORECASE),
    "absolute-user-path": re.compile(r"/(?:Users|home)/[^/\s]+/"),
    "provider-secret": re.compile(r"(?:sk-[A-Za-z0-9_-]{8,}|BEGIN (?:RSA |EC )?PRIVATE KEY)"),
}


def scan_paths(paths: list[Path]) -> list[str]:
    violations: list[str] = []
    for root in paths:
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else root.rglob("*")
        for path in candidates:
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                text = path.read_text()
            except UnicodeDecodeError:
                continue
            for code, pattern in FORBIDDEN.items():
                if pattern.search(text):
                    violations.append(f"{path}:{code}")
    return sorted(violations)


def main(argv: list[str]) -> int:
    violations = scan_paths([Path(item) for item in argv])
    if violations:
        print("\n".join(violations), file=sys.stderr)
        return 1
    print("release content scan: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
