from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from review_runtime.poc_adapter import read_poc_v1

ROOT = Path(__file__).parents[2]
LEGACY_SCRIPTS = ROOT / "implementation/poc/review-data-spec/scripts"


def hashes(path: Path) -> dict[str, str]:
    return {
        item.relative_to(path).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in path.rglob("*")
        if item.is_file()
    }


@pytest.fixture
def legacy_run(tmp_path: Path) -> Path:
    sys.path.insert(0, str(LEGACY_SCRIPTS))
    try:
        from review_data_spec.demo import run_demo

        run, _ = run_demo(tmp_path, run_id="synthetic-compat")
        return run
    finally:
        sys.path.remove(str(LEGACY_SCRIPTS))


def test_mapping_is_stable_schema_valid_and_read_only(legacy_run: Path) -> None:
    before = hashes(legacy_run)
    first = read_poc_v1(legacy_run)
    second = read_poc_v1(legacy_run)
    assert first == second
    assert hashes(legacy_run) == before
    assert first["mapping_status"] == "complete"
    assert first["coverage"]["target_fragment_ids"] == first["coverage"]["reviewed_fragment_ids"]
    encoded = json.dumps(first)
    assert "original_path" not in encoded and str(legacy_run) not in encoded


def test_invalid_anchor_fails_whole_mapping(legacy_run: Path) -> None:
    report_path = legacy_run / "report.json"
    report = json.loads(report_path.read_text())
    report["findings"][0]["anchors"][0]["quote"] = "not present"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="legacy_quote_not_found"):
        read_poc_v1(legacy_run)


def test_path_traversal_and_available_without_sha_are_rejected(legacy_run: Path) -> None:
    manifest_path = legacy_run / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["sources"][0]["snapshot"] = "../escape.md"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        read_poc_v1(legacy_run)
