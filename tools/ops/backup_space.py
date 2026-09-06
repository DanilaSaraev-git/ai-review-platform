"""Reject a new full backup before writing when its filesystem lacks headroom."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

DEFAULT_RESERVE_BYTES = 2 * 1024**3
ARCHIVE_OVERHEAD_BYTES = 64 * 1024**2


def required_free_bytes(database_bytes: int, artifact_bytes: int, reserve_bytes: int) -> int:
    if database_bytes < 0 or artifact_bytes < 0 or reserve_bytes <= 0:
        raise ValueError("backup sizes must be nonnegative and reserve must be positive")
    # Do not count on compression. Allow headroom for archive/dump metadata and growth.
    return 2 * (database_bytes + artifact_bytes) + ARCHIVE_OVERHEAD_BYTES + reserve_bytes


def check_backup_space(
    backup_dir: Path,
    database_bytes: int,
    artifact_bytes: int,
    reserve_bytes: int = DEFAULT_RESERVE_BYTES,
) -> None:
    required = required_free_bytes(database_bytes, artifact_bytes, reserve_bytes)
    free = shutil.disk_usage(backup_dir).free
    if free < required:
        raise ValueError(
            f"backup refused: {free} bytes free, {required} required including {reserve_bytes} reserve; "
            "existing backups are unchanged"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup_dir", type=Path)
    parser.add_argument("database_bytes", type=int)
    parser.add_argument("artifact_bytes", type=int)
    parser.add_argument("reserve_bytes", type=int)
    args = parser.parse_args()
    try:
        check_backup_space(args.backup_dir, args.database_bytes, args.artifact_bytes, args.reserve_bytes)
    except (OSError, ValueError) as error:
        parser.exit(1, f"error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
