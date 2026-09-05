from __future__ import annotations

import hashlib

import pytest
from review_runtime.artifacts.posix import PosixArtifactStore


def test_stage_promote_hash_and_exact_read(tmp_path) -> None:
    store = PosixArtifactStore(tmp_path)
    data = b"immutable artifact"
    staged = store.stage("workspace-1", data, expected_sha256=hashlib.sha256(data).hexdigest())
    assert staged.path.exists()
    key = store.promote(staged)
    assert not staged.path.exists()
    assert store.get(key) == data


def test_hash_mismatch_rolls_back_staging(tmp_path) -> None:
    store = PosixArtifactStore(tmp_path)
    with pytest.raises(ValueError, match="digest"):
        store.stage("workspace-1", b"bytes", expected_sha256="0" * 64)
    assert list((tmp_path / "staging").iterdir()) == []


@pytest.mark.parametrize("key", ["../secret", "/absolute", "workspace/../../secret", "workspace\\secret"])
def test_opaque_keys_reject_path_traversal(tmp_path, key: str) -> None:
    store = PosixArtifactStore(tmp_path)
    with pytest.raises(ValueError):
        store.get(key)


def test_collector_keeps_referenced_and_removes_unreferenced(tmp_path) -> None:
    store = PosixArtifactStore(tmp_path)
    keep = store.put("workspace-1", b"keep")
    remove = store.put("workspace-1", b"remove")
    removed = store.collect_promoted(lambda key, digest: key == keep, older_than_seconds=0)
    assert removed == [remove]
    assert store.get(keep) == b"keep"
