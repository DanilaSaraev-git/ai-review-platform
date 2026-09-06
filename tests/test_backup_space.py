from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.ops import backup_space

ROOT = Path(__file__).parents[1]


def test_backup_requires_room_for_uncompressed_data_and_preserves_reserve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_bytes = 3 * 1024**3
    artifact_bytes = 5 * 1024**3
    reserve = 2 * 1024**3
    required = 18 * 1024**3 + backup_space.ARCHIVE_OVERHEAD_BYTES
    assert backup_space.required_free_bytes(data_bytes, artifact_bytes, reserve) == required
    monkeypatch.setattr(backup_space.shutil, "disk_usage", lambda path: SimpleNamespace(free=required))
    backup_space.check_backup_space(tmp_path, data_bytes, artifact_bytes, reserve)
    monkeypatch.setattr(backup_space.shutil, "disk_usage", lambda path: SimpleNamespace(free=required - 1))
    with pytest.raises(ValueError, match="backup refused"):
        backup_space.check_backup_space(tmp_path, data_bytes, artifact_bytes, reserve)


@pytest.mark.parametrize("sizes", [(-1, 0, 1), (0, -1, 1), (0, 0, 0), (0, 0, -1)])
def test_backup_rejects_invalid_size_or_disabled_reserve(sizes: tuple[int, int, int]) -> None:
    with pytest.raises(ValueError, match="nonnegative"):
        backup_space.required_free_bytes(*sizes)


def test_cli_refuses_insufficient_space_without_modifying_existing_backups(tmp_path: Path) -> None:
    existing = tmp_path / "20260906T000000Z"
    existing.mkdir()
    dump = existing / "database.dump"
    dump.write_bytes(b"synthetic existing backup")
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/ops/backup_space.py"), str(tmp_path), str(10**18), "0", "1"],
        capture_output=True, text=True, check=False, timeout=5,
    )
    assert result.returncode == 1
    assert "backup refused" in result.stderr
    assert dump.read_bytes() == b"synthetic existing backup"
    assert list(tmp_path.iterdir()) == [existing]


def test_backup_script_checks_space_before_creating_new_copy() -> None:
    script = (ROOT / "tools/ops/backup.sh").read_text()
    preflight = script.index('python3 "$SCRIPT_DIR/backup_space.py"')
    assert preflight < script.index('tmp_dir="$(mktemp -d')
    assert preflight < script.index("pg_dump --username")
    assert 'trap cleanup_backup EXIT' in script[:preflight]
